#!/usr/bin/env python3
"""Bending fatigue damage of hoist ropes to RS-4, for one works package.

    python3 ropes.py WORKS_DIR OUT_CSV

Reads cranes.csv, sheaves.csv, movements.csv and surveys.csv from WORKS_DIR
(format of works_package.md) and writes OUT_CSV with the header `row,damage`:
one row per station of each crane's last rope survey, named CRANE-NNN with the
stations counted from the drum anchorage from 001.

RS-4 model, per movement and per sheave of sheaves.csv (the drum included):
the sheave's point of touch x = L - a - p (H - h) sweeps along the rope as the
hook goes from one height to the other, and every element it passes takes one
bending of weight w, worth w / N with
    lg N = b0 + (b1 + b3 lg(D/d)) lg(S/d^2) + b2 lg(D/d),
    S = (m_h + m_b) g / (n e).
The damage is reckoned at the points of the rope that sit at the stations of
the last survey, at the end of the log; d is that element's diameter as read
at the last survey on or before the movement.

Damage belongs to a piece of rope, not to a place along it. A rope that has
been turned end for end shows it in the surveys: after the turn the diameter
profile is the mirror image, x -> L - x, of the one before. Turns are found by
fitting the surveys with a wear law
    d = d0 - c t - a D^beta,
D the bending damage the element has had so far, with and without a turn in
each survey interval (and at what time in it). The damage of each element is
then summed over the places it has occupied.
"""

import os
import re
import sys
import time

import numpy as np
import pandas as pd

G_ACC = 9.80665
COEF = {
    "8x36": (-1.214, 0.887, 7.432, -2.103),
    "6x36": (-1.371, 0.934, 7.518, -2.146),
}

SUB = 24            # most candidate turn times per survey interval
SUB_MIN = 8         # least candidate turn times per survey interval
SUB_TOTAL = 480     # candidate turn times aimed at over the whole log
CPU_SOFT = 15.0     # CPU seconds after which the search is made coarse
CPU_HARD = 24.0     # CPU seconds after which no more turns are looked for
MAX_TURNS = 4       # most turns looked for on one rope
ACCEPT = 16.0       # least drop in squared error, in noise variances, to accept a turn
S_REF = 0.015       # mm: scatter of readings about a wear law that fits (caliper repeatability)
PAIR_SPAN = 12      # a turn and a turn back are looked for this many intervals apart at most
PAIR_TOTAL = 240    # pairs of intervals tried at most, about
BETAS = np.round(np.arange(0.30, 1.501, 0.025), 4)
BETAS_COARSE = np.round(np.arange(0.40, 1.001, 0.1), 4)
COARSE_STEP = 4     # coarse scan: every 4th candidate time of an interval
FINE_INTERVALS = 3  # intervals then scanned at every candidate time


def log(*a):
    print(*a, file=sys.stderr)


# --------------------------------------------------------------------------- input

def read_table(path):
    df = pd.read_csv(path, skipinitialspace=True, dtype=str, keep_default_na=True)
    df.columns = [str(c).strip().lower() for c in df.columns]
    for c in df.columns:
        df[c] = df[c].astype(str).str.strip()
        df.loc[df[c].isin(["", "nan", "NaN", "None"]), c] = np.nan
    return df


def num(df, cols):
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def coef_for(construction):
    key = re.sub(r"\s+", "", str(construction).lower()).replace("×", "x").replace("*", "x")
    if key in COEF:
        return COEF[key]
    for k in COEF:
        if k in key:
            return COEF[k]
    k = "8x36" if key.startswith("8") else "6x36"
    log("unknown rope construction %r, taken as %s" % (construction, k))
    return COEF[k]


# --------------------------------------------------------------------------- damage

def damage_sum(moves, sheaves, L, H, coef, Q, lgd_tab, s_of_m, bin_of_m, nbins):
    """Sum w/N over every bending of the rope points at the sorted positions Q.

    moves: dict of arrays h1, h2, lgS (log10 of rope tension, N) per movement.
    lgd_tab[s, q]: log10 of the diameter (mm) to use for survey s at point q.
    s_of_m: survey index per movement; bin_of_m: accumulation bin per movement.
    Returns an array (nbins, len(Q)).
    """
    nQ = len(Q)
    out = np.zeros(nbins * nQ)
    if nQ == 0 or len(moves["h1"]) == 0:
        return out.reshape(nbins, nQ)
    b0, b1, b2, b3 = coef
    h1, h2, lgS = moves["h1"], moves["h2"], moves["lgS"]
    for (p, a, D, w) in sheaves:
        if w == 0:
            continue
        x1 = L - a - p * (H - h1)
        x2 = L - a - p * (H - h2)
        lo = np.minimum(x1, x2)
        hi = np.maximum(x1, x2)
        i0 = np.searchsorted(Q, lo, side="left")
        i1 = np.searchsorted(Q, hi, side="right")
        cnt = i1 - i0
        cnt[(cnt < 0) | (hi <= lo)] = 0
        tot = int(cnt.sum())
        if tot == 0:
            continue
        off = np.cumsum(cnt) - cnt
        mi = np.repeat(np.arange(len(cnt)), cnt)
        qi = np.repeat(i0 - off, cnt) + np.arange(tot)
        lgd = lgd_tab[s_of_m[mi], qi]
        lgDd = np.log10(D) - lgd
        lgSd = lgS[mi] - 2.0 * lgd
        lgN = b0 + (b1 + b3 * lgDd) * lgSd + b2 * lgDd
        val = w * np.power(10.0, -lgN)
        out += np.bincount(bin_of_m[mi] * nQ + qi, weights=val, minlength=nbins * nQ)
    return out.reshape(nbins, nQ)


def interp_survey(st, dia, pos):
    """Diameter read at a survey (stations st, readings dia) at rope points pos."""
    if len(st) == 1:
        return np.full(len(pos), dia[0])
    return np.interp(pos, st, dia)


# --------------------------------------------------------------------------- wear fit

class WearFit:
    """Fits d = d0 - c t - a D^beta to all survey readings of one rope, for a
    given history of end-for-end turns, and scores it by the squared error."""

    def __init__(self, surveys, L, C, es, P):
        self.C = C          # (n_edges, n_P) damage before each time edge, at points P
        pts_s, pts_t, pts_qy, pts_qm, pts_r = [], [], [], [], []
        for s, (t, st, dia) in enumerate(surveys):
            qy = np.clip(np.searchsorted(P, np.round(st, 6)), 0, len(P) - 1)
            qm = np.clip(np.searchsorted(P, np.round(L - st, 6)), 0, len(P) - 1)
            pts_s.append(np.full(len(st), s))
            pts_t.append(np.full(len(st), t))
            pts_qy.append(qy)
            pts_qm.append(qm)
            pts_r.append(dia)
        self.s = np.concatenate(pts_s)
        t = np.concatenate(pts_t)
        y = np.concatenate(pts_r)
        self.qy = np.concatenate(pts_qy)
        self.qm = np.concatenate(pts_qm)
        self.n = len(y)
        self.pt_es = es[self.s]
        # centred, so that the intercept drops out of the normal equations
        self.t = t - t.mean()
        self.y = y - y.mean()
        self.Stt = float(self.t @ self.t)
        self.Sty = float(self.t @ self.y)
        self.Syy = float(self.y @ self.y)

    def elem_damage(self, turns):
        """Damage, at survey time, of the element read at each point, for the
        turns given as a list of (interval i, edge u), sorted: surveys 0..i
        are before the turn, and so are the movements before edge u."""
        C = self.C
        if not turns:
            return C[self.pt_es, self.qy]
        iv = np.array([i for (i, _) in turns])
        us = np.array([u for (_, u) in turns])
        ks = np.searchsorted(iv, self.s, side="left")     # turns made before the survey
        D = np.zeros(self.n)
        K = len(turns)
        for e in range(K + 1):
            act = ks >= e
            if not act.any():
                continue
            a0 = 0 if e == 0 else us[e - 1]
            if e < K:
                a1 = np.where(ks > e, us[e], self.pt_es)
            else:
                a1 = self.pt_es
            q = np.where((ks - e) % 2 == 0, self.qy, self.qm)
            D += np.where(act, C[a1, q] - C[a0, q], 0.0)
        return D

    def sse(self, D, betas=None):
        """Least squared error of the fit, over a grid of beta."""
        if betas is None:
            betas = BETAS
        Dp = np.maximum(D, 0.0)
        with np.errstate(divide="ignore"):
            lD = np.log(Dp)
        f = np.exp(betas[:, None] * lD[None, :])         # (nb, n), 0 where D = 0
        f = f - f.mean(1, keepdims=True)
        Sff = np.einsum("bi,bi->b", f, f)
        Stf = f @ self.t
        Sfy = f @ self.y
        det = self.Stt * Sff - Stf * Stf
        ok = det > 1e-18 * np.maximum(self.Stt * Sff, 1e-300)
        # explained sum of squares of the two-regressor fit
        with np.errstate(divide="ignore", invalid="ignore"):
            ct = (Sff * self.Sty - Stf * Sfy) / det
            cf = (self.Stt * Sfy - Stf * self.Sty) / det
            ess = ct * self.Sty + cf * Sfy
        ess_t = self.Sty ** 2 / self.Stt if self.Stt > 0 else 0.0
        ess = np.where(ok, ess, ess_t)
        k = int(np.argmax(ess))
        return float(self.Syy - ess[k]), float(betas[k])

    def score(self, turns, coarse=False):
        return self.sse(self.elem_damage(turns), BETAS_COARSE if coarse else BETAS)[0]


def _sorted(turns):
    return sorted(turns, key=lambda z: (z[1], z[0]))


def find_turns(fit, surveys, edges_by_interval, crane, fast=False):
    """Search for end-for-end turns: add the best one while it pays, moving
    all of them to their best times after each addition, and drop any that
    no longer pays. Returns a sorted list of (interval i, edge u)."""
    nsurv = len(surveys)
    if nsurv < 2 or fit.n < 8:
        return []
    n_int = nsurv - 1

    def scan(turns, skip=None):
        """Best place for one more turn, the others fixed. Returns
        (sse, i, u, {i: [(sse, u)]})."""
        used = {i for (i, _) in turns}
        # coarse: a few times in each interval, beta on a coarse grid
        rough = []
        for i in range(n_int):
            if i in used:
                continue
            eds = edges_by_interval[i]
            v = min(fit.score(_sorted(turns + [(i, u)]), coarse=True) for u in eds[::COARSE_STEP])
            rough.append((v, i))
        rough.sort()
        best = (np.inf, None, None)
        curve = {}
        # fine: every time in the most promising intervals
        for _, i in rough[:1 if fast else FINE_INTERVALS]:
            row = []
            for u in edges_by_interval[i]:
                v = fit.score(_sorted(turns + [(i, u)]))
                row.append((v, u))
                if v < best[0]:
                    best = (v, i, u)
            curve[i] = row
        return best[0], best[1], best[2], curve

    def noise_var(v, k):
        """Variance of the readings about the fit, as the yardstick of a
        drop in squared error; enlarged when the wear law does not fit the
        readings to within the caliper's scatter, since its misfit is not
        random from point to point."""
        s2 = max(v / max(fit.n - 5 - 2 * k, 1), 1e-10)
        return s2 * max(1.0, s2 / S_REF ** 2)

    def refine(turns):
        for _ in range(4):
            moved = False
            for j in range(len(turns)):
                others = turns[:j] + turns[j + 1:]
                v, i, u, _ = scan(others)
                if i is not None and (i, u) != turns[j] and v < fit.score(_sorted(turns)) - 1e-15:
                    turns = _sorted(others + [(i, u)])
                    moved = True
            if not moved:
                break
        return turns

    def tune_within(turns, ids):
        """Move the given turns to their best times within their own intervals."""
        for _ in range(2):
            for j in ids:
                i = turns[j][0]
                others = turns[:j] + turns[j + 1:]
                cands = [(fit.score(_sorted(others + [(i, uu)]), coarse=True), uu)
                         for uu in edges_by_interval[i]]
                turns = others + [(i, min(cands)[1])]
                turns = turns[:j] + [turns[-1]] + turns[j:-1]
        return turns

    def scan_pairs(turns):
        """Best place for a turn and a turn back, the others fixed."""
        used = {i for (i, _) in turns}
        free = [i for i in range(n_int) if i not in used]
        mid = {i: edges_by_interval[i][len(edges_by_interval[i]) // 2] for i in free}
        span = int(np.clip(PAIR_TOTAL // max(len(free), 1), 2, PAIR_SPAN))
        rough = []
        for a_, i in enumerate(free):
            for j in free[a_ + 1:]:
                if j - i > span:
                    break
                v = fit.score(_sorted(turns + [(i, mid[i]), (j, mid[j])]), coarse=True)
                rough.append((v, i, j))
        if not rough:
            return np.inf, None
        rough.sort()
        best = (np.inf, None)
        for _, i, j in rough[:2]:
            cand = turns + [(i, mid[i]), (j, mid[j])]
            k = len(turns)
            cand = tune_within(cand, [k, k + 1])
            cand = _sorted(cand)
            v = fit.score(cand)
            if v < best[0]:
                best = (v, cand)
        return best

    turns = []
    cur = fit.score(turns)
    for _ in range(MAX_TURNS):
        if len(turns) >= MAX_TURNS:
            break
        if time.process_time() > CPU_HARD:
            log("%s: out of time, no more turns looked for" % crane)
            break
        fast = fast or time.process_time() > CPU_SOFT
        v, i, u, _ = scan(turns)
        if i is None:
            break
        s2 = noise_var(v, len(turns) + 1)
        drop = cur - v
        log("%s: best added turn in interval %d (days %.2f-%.2f) at edge %d: "
            "rms %.4f -> %.4f, drop %.1f noise variances"
            % (crane, i, surveys[i][0], surveys[i + 1][0], u,
               np.sqrt(cur / fit.n), np.sqrt(v / fit.n), drop / s2))
        new = None
        if drop >= ACCEPT * s2:
            new = _sorted(turns + [(i, u)])
        if len(turns) + 2 <= MAX_TURNS and not fast:
            v2, pair = scan_pairs(turns)
            if pair is not None:
                s2p = noise_var(v2, len(turns) + 2)
                log("%s: best added turn and turn back: rms %.4f -> %.4f, drop %.1f noise "
                    "variances" % (crane, np.sqrt(cur / fit.n), np.sqrt(v2 / fit.n), (cur - v2) / s2p))
                if cur - v2 >= 2 * ACCEPT * s2p and (new is None or v - v2 >= ACCEPT * s2p):
                    new = pair
        if new is None:
            break
        turns = refine(new)
        # drop turns that do not pay any more
        while turns:
            v_all = fit.score(turns)
            s2 = noise_var(v_all, len(turns))
            costs = [fit.score(turns[:j] + turns[j + 1:]) - v_all for j in range(len(turns))]
            j = int(np.argmin(costs))
            if costs[j] < ACCEPT * s2:
                log("%s: turn at edge %d dropped" % (crane, turns[j][1]))
                turns = refine(turns[:j] + turns[j + 1:])
                continue
            # a turn and a turn back that do not pay any more
            best_pair = None
            for j in range(len(turns)):
                for k in range(j + 1, len(turns)):
                    rest = [t for m_, t in enumerate(turns) if m_ not in (j, k)]
                    c = fit.score(rest) - v_all
                    if best_pair is None or c < best_pair[0]:
                        best_pair = (c, rest)
            if best_pair is not None and best_pair[0] < 2 * ACCEPT * s2:
                log("%s: a turn and a turn back dropped" % crane)
                turns = refine(best_pair[1])
            else:
                break
        cur = fit.score(turns)

    # the time of each turn: the middle of the times that fit about as well
    final = []
    v_all = fit.score(turns)
    s2 = noise_var(v_all, len(turns))
    for j, (i, u) in enumerate(turns):
        others = turns[:j] + turns[j + 1:]
        row = [(fit.score(_sorted(others + [(i, uu)])), uu) for uu in edges_by_interval[i]]
        vmin = min(vv for vv, _ in row)
        ok = [uu for (vv, uu) in row if vv <= vmin + 4.0 * s2]
        mid = 0.5 * (min(ok) + max(ok))
        pick = min((uu for (_, uu) in row), key=lambda z: abs(z - mid))
        log("%s: turn in interval %d: times that fit span edges %d..%d, best %d, taken %d"
            % (crane, i, min(ok), max(ok), u, pick))
        final.append((i, pick))
    return _sorted(final)


# --------------------------------------------------------------------------- one crane

def crane_damage(cr, sh, mv, sv):
    name = cr["crane"]
    n = float(cr["falls"])
    H = float(cr["upper_block_height_m"])
    mb = float(cr["block_mass_t"])
    eff = float(cr["reeving_efficiency"])
    L = float(cr["rope_length_m"])
    coef = coef_for(cr.get("rope_construction", "6x36"))

    # ---- the stations of the result: those of the last survey
    sv = sv.dropna(subset=["day", "station_m"])
    if not len(sv):
        return [], np.zeros(0)
    x_out = np.unique(sv.loc[sv["day"] == sv["day"].max(), "station_m"].to_numpy(float))
    k_grid = (x_out - 2.5) / 5.0
    if np.all(np.abs(k_grid - np.round(k_grid)) < 0.01) and np.all(np.round(k_grid) >= 0):
        numbers = np.round(k_grid).astype(int) + 1        # stations at 2.5 m + 5 m steps
    else:
        numbers = np.arange(1, len(x_out) + 1)
    rows = ["%s-%03d" % (name, k) for k in numbers]

    # ---- surveys: list of (day, stations sorted, diameters); readings far off
    # the survey's own median (a slip of the pen, not wear) are left out
    sv = sv.dropna(subset=["diameter_mm"])
    sv = sv[sv["diameter_mm"] > 0]
    surveys = []
    for day, g in sv.groupby("day", sort=True):
        g = g.groupby("station_m", as_index=False)["diameter_mm"].mean().sort_values("station_m")
        dia = g["diameter_mm"].to_numpy(float)
        ok = np.abs(dia / np.median(dia) - 1.0) <= 0.35
        if ok.sum() < len(ok):
            log("%s: survey of day %s: %d reading(s) left out" % (name, day, len(ok) - ok.sum()))
        if ok.any():
            surveys.append((float(day), g["station_m"].to_numpy(float)[ok], dia[ok]))
    if not surveys:
        return rows, np.zeros(len(x_out))
    T = np.array([s[0] for s in surveys])

    # ---- reeving
    sheaves = []
    for _, q in sh.iterrows():
        is_drum = str(q.get("sheave", "")).strip().lower() == "drum"
        p = q.get("parts", np.nan)
        if not np.isfinite(p):
            p = n if is_drum else np.nan
        w = q.get("bend_weight", np.nan)
        if not np.isfinite(w):
            w = 0.5 if is_drum else 1.0
        a = q.get("offset_m", np.nan)
        D = q.get("diameter_mm", np.nan)
        if not (np.isfinite(p) and np.isfinite(a) and np.isfinite(D) and D > 0):
            log("%s: sheave row skipped: %s" % (name, dict(q)))
            continue
        sheaves.append((float(p), float(a), float(D), float(w)))

    # ---- movements
    mv = mv.dropna(subset=["day", "from_height_m", "to_height_m"]).copy()
    mv["hook_load_t"] = mv["hook_load_t"].fillna(0.0)
    mv = mv[mv["day"] >= 0]
    mv = mv.drop_duplicates(subset=["day", "from_height_m", "to_height_m", "hook_load_t"])
    mv = mv[mv["from_height_m"] != mv["to_height_m"]]
    day = mv["day"].to_numpy(float)
    S = (mv["hook_load_t"].to_numpy(float) + mb) * 1000.0 * G_ACC / (n * eff)
    S = np.maximum(S, 1e-6)
    moves = {"h1": mv["from_height_m"].to_numpy(float),
             "h2": mv["to_height_m"].to_numpy(float),
             "lgS": np.log10(S)}
    s_of_m = np.clip(np.searchsorted(T, day, side="right") - 1, 0, len(T) - 1)
    if len(day) == 0 or not sheaves:
        return rows, np.zeros(len(x_out))

    # ---- time edges: -inf, then sub steps in each survey interval, the surveys, +inf
    n_int = max(len(T) - 1, 1)
    spent = time.process_time()
    sub_n = int(np.clip(round(SUB_TOTAL / n_int), SUB_MIN, SUB))
    if spent > CPU_SOFT:
        sub_n = SUB_MIN
    edge_t = [-np.inf]
    es = np.zeros(len(T), dtype=int)
    edges_by_interval = []
    for i in range(len(T)):
        es[i] = len(edge_t)
        edge_t.append(T[i])
        if i + 1 < len(T):
            idx = [es[i]]
            for j in range(1, sub_n):
                idx.append(len(edge_t))
                edge_t.append(T[i] + (T[i + 1] - T[i]) * j / sub_n)
            idx.append(len(edge_t))      # = edge of survey i+1
            edges_by_interval.append(idx)
    edge_t.append(np.inf)
    edge_t = np.array(edge_t)
    nb = len(edge_t)                      # bins: b holds edge_t[b] <= day < edge_t[b+1]

    # ---- look for turns (only if there are at least two surveys)
    turns = []
    if len(T) >= 2 and spent < CPU_HARD:
        allst = np.concatenate([s[1] for s in surveys])
        P = np.unique(np.round(np.concatenate([allst, L - allst]), 6))
        lgd_pos = np.log10(np.array([interp_survey(st, dia, P) for (_, st, dia) in surveys]))
        bin_of_m = np.searchsorted(edge_t, day, side="right") - 1
        dmg = damage_sum(moves, sheaves, L, H, coef, P, lgd_pos, s_of_m, bin_of_m, nb)
        C = np.vstack([np.zeros((1, len(P))), np.cumsum(dmg, 0)])[:nb]  # C[e]: day < edge_t[e]
        fit = WearFit(surveys, L, C, es, P)
        try:
            turns = find_turns(fit, surveys, edges_by_interval, name, fast=spent > CPU_SOFT)
        except Exception as exc:  # never fail a run over the search
            log("%s: turn search failed: %r" % (name, exc))
            turns = []
    turn_t = [edge_t[u] for (_, u) in turns]
    turn_i = [i for (i, _) in turns]
    k_tot = len(turns)
    if turns:
        log("%s: rope turned end for end at day(s) %s" % (name, ", ".join("%.2f" % t for t in turn_t)))

    # ---- final damage of the elements at the last survey's stations
    # epoch of movement: number of turns made before it
    ep_m = np.zeros(len(day), dtype=int)
    for t in turn_t:
        ep_m += (day >= t).astype(int)
    # epoch of survey: number of turns in intervals before it
    ep_s = np.array([sum(1 for i in turn_i if i < s) for s in range(len(T))])

    def pos_in_epoch(e):
        return x_out if (k_tot - e) % 2 == 0 else L - x_out

    # diameter of each element as read at each survey (at its place then)
    dtab = np.array([interp_survey(st, dia, pos_in_epoch(ep_s[s]))
                     for s, (_, st, dia) in enumerate(surveys)])
    lgd_elem = np.log10(dtab)
    total = np.zeros(len(x_out))
    for e in range(k_tot + 1):
        sel = ep_m == e
        if not sel.any():
            continue
        pos = pos_in_epoch(e)
        order = np.argsort(pos, kind="stable")
        Q = pos[order]
        sub = {k: v[sel] for k, v in moves.items()}
        res = damage_sum(sub, sheaves, L, H, coef, Q, lgd_elem[:, order], s_of_m[sel],
                         np.zeros(sel.sum(), dtype=int), 1)[0]
        back = np.empty_like(res)
        back[order] = res
        total += back
    return rows, total


# --------------------------------------------------------------------------- main

def fmt(v):
    if not np.isfinite(v):
        v = 0.0
    s = np.format_float_positional(float(v), precision=12, unique=False, fractional=False, trim="0")
    if s.endswith("."):
        s += "0"
    return s


def main():
    if len(sys.argv) < 3:
        print("usage: python3 ropes.py WORKS_DIR OUT_CSV", file=sys.stderr)
        return 0
    wd, out = sys.argv[1], sys.argv[2]
    rows_all, vals_all = [], []
    try:
        cranes = read_table(os.path.join(wd, "cranes.csv"))
        sheaves = num(read_table(os.path.join(wd, "sheaves.csv")),
                      ["parts", "offset_m", "diameter_mm", "bend_weight"])
        moves = num(read_table(os.path.join(wd, "movements.csv")),
                    ["day", "from_height_m", "to_height_m", "hook_load_t"])
        surveys = num(read_table(os.path.join(wd, "surveys.csv")),
                      ["day", "station_m", "diameter_mm"])
        cranes = num(cranes, ["falls", "upper_block_height_m", "block_mass_t",
                              "reeving_efficiency", "rope_length_m"])
        names = list(dict.fromkeys(cranes["crane"].dropna().tolist()))
        mv_g = {k: g for k, g in moves.groupby("crane", sort=False)}
        sv_g = {k: g for k, g in surveys.groupby("crane", sort=False)}
        sh_g = {k: g for k, g in sheaves.groupby("crane", sort=False)}
        empty_mv = moves.iloc[0:0]
        empty_sv = surveys.iloc[0:0]
        empty_sh = sheaves.iloc[0:0]
        for nm in names:
            cr = cranes[cranes["crane"] == nm].iloc[0].to_dict()
            try:
                rows, vals = crane_damage(cr, sh_g.get(nm, empty_sh), mv_g.get(nm, empty_mv),
                                          sv_g.get(nm, empty_sv))
            except Exception as exc:
                log("%s: failed: %r" % (nm, exc))
                g = sv_g.get(nm, empty_sv)
                if len(g):
                    last = g[g["day"] == g["day"].max()]
                    rows = ["%s-%03d" % (nm, k + 1) for k in range(len(last))]
                    vals = np.zeros(len(rows))
                else:
                    rows, vals = [], np.zeros(0)
            rows_all += rows
            vals_all += list(vals)
    except Exception as exc:
        log("package could not be read: %r" % (exc,))
    with open(out, "w") as f:
        f.write("row,damage\n")
        for r, v in zip(rows_all, vals_all):
            f.write("%s,%s\n" % (r, fmt(v)))
    return 0


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # the run must end with status 0
        log("error: %r" % (exc,))
    sys.exit(0)
