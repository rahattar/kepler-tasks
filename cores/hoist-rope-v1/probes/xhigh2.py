#!/usr/bin/env python3
"""Bending fatigue damage of crane hoist ropes to RS-4 (Issue 3).

Usage: python3 ropes.py WORKS_DIR OUT_CSV

Model (RS-4):
  touch point of a sheave or the drum (s.1):  x = L - a - p (H - h)
  rope tension (s.3):                         S = (m_h + m_b) g / (n e)
  endurance (s.4):  lg N = b0 + (b1 + b3 lg(D/d)) lg(S/d^2) + b2 lg(D/d)
  damage (s.5):     sum over every bending of the element of w / N

Damage belongs to rope *elements*.  The result is the damage of the element
that lies at each station of the rope's last survey, stations counted from
the drum anchorage.  Two things that are not in the records are read from
the surveys, with the caliper's repeatability as the noise:

* The rope may have been turned end for end between two surveys: the element
  at x then lies at L - x, and the damage it had is carried with it.
* A survey may have been measured from the dead end, so that its stations
  are mirrored (recorded x is L - x on the rope).

Both mirror the diameter profile between two surveys.  They differ in where
the rope then wears: wear follows the bending at the elements' places on the
rope.  For every pair of consecutive surveys the measured wear is fitted with
wear = c + k * (damage gained in the interval), k >= 0, for each choice of
the two surveys' orientations, with and without a turn (whose time within the
interval is unknown: uniform prior).  The orientations are the most probable
sequence (Viterbi, rare flips); the surveys are then put in rope coordinates
and the turns are taken with their probabilities.  The damage of each
movement in an interval with a turn is shared between the element's two
positions by the probability that the turn came after the movement.

d of a movement is the diameter of the element measured at the last survey
on or before the time of the movement (the earliest survey before that),
read at the element's position at that survey; between stations it is
interpolated linearly along the rope.
"""

import os
import re
import sys

import numpy as np
import pandas as pd

G = 9.80665
COEFFS = {  # construction: (b0, b1, b2, b3), RS-4 section 4
    "8x36": (-1.214, 0.887, 7.432, -2.103),
    "6x36": (-1.371, 0.934, 7.518, -2.146),
}
CHUNK = 8192          # movements handled at once
MAX_SPLITS = 2000     # candidate turn times per survey interval
NOISE_SD = 0.02       # caliper repeatability, mm (works_package.md)
TEMPER = 2.0          # widening of the wear-fit likelihood (turn or not)
TIME_TEMPER = 2.0     # widening of the wear-fit likelihood (time of a turn)
P_TURN = 1.0 / 51.0       # rope turned end for end in a given survey interval
P_FLIP = 1.0 / 50.0       # survey orientation changes between two surveys
P_FIRST_MIRRORED = 1.0 / 50.0   # first survey measured from the dead end


# --------------------------------------------------------------------------
# input

def read_table(path):
    df = pd.read_csv(path, encoding="utf-8-sig", skipinitialspace=True,
                     dtype=str, keep_default_na=False)
    df.columns = [str(c).strip().lower() for c in df.columns]
    for c in df.columns:
        df[c] = df[c].astype(str).str.strip()
    return df


def num(series):
    return pd.to_numeric(series, errors="coerce").to_numpy(dtype=float)


def num1(value):
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return float("nan")


def coeffs_for(construction):
    key = str(construction).strip().lower().replace("\u00d7", "x")
    key = re.sub(r"\s+", "", key)
    if key in COEFFS:
        return COEFFS[key]
    m = re.search(r"(\d+)x(\d+)", key)
    if m and f"{m.group(1)}x{m.group(2)}" in COEFFS:
        return COEFFS[f"{m.group(1)}x{m.group(2)}"]
    # not in the table: take the construction with the same number of strands
    print(f"unknown rope construction {construction!r}", file=sys.stderr)
    return COEFFS["8x36"] if key.startswith("8") else COEFFS["6x36"]


def fmt(v):
    if not np.isfinite(v):
        v = 0.0
    s = np.format_float_positional(float(v), precision=10, unique=False,
                                   fractional=False, trim="-")
    if s.endswith("."):
        s = s[:-1]
    return s if s not in ("-0", "") else "0"


# --------------------------------------------------------------------------
# rope model

class Rope:
    """One crane: reeving, rope, surveys and movements."""

    def __init__(self, crane, sheaves, mv, sv):
        self.n = crane["falls"]
        self.H = crane["H"]
        self.L = crane["L"]
        self.b = coeffs_for(crane["construction"])
        self.sheaves = []
        for p, a, D, w in sheaves:
            if (np.isfinite(p) and p > 0 and np.isfinite(a) and np.isfinite(D)
                    and D > 0 and np.isfinite(w) and w != 0):
                self.sheaves.append((p, a, D, w))

        # surveys: per day, sorted stations and mean diameters
        ok = (np.isfinite(sv["day"]) & np.isfinite(sv["x"]) & np.isfinite(sv["d"])
              & (sv["d"] > 0))
        day, x, d = sv["day"][ok], np.round(sv["x"][ok], 6), sv["d"][ok]
        self.days = np.unique(day)
        self.surveys = []
        for t in self.days:
            k = day == t
            g = pd.Series(d[k]).groupby(x[k]).mean()
            self.surveys.append((g.index.to_numpy(dtype=float), g.to_numpy(dtype=float)))
        self.stations = self.surveys[-1][0]

        # movements, in time order
        t, h1, h2 = mv["day"], mv["h1"], mv["h2"]
        load = np.where(np.isfinite(mv["load"]), mv["load"], 0.0)
        ok = np.isfinite(t) & np.isfinite(h1) & np.isfinite(h2) & (h1 != h2)
        order = np.argsort(t[ok], kind="stable")
        self.t = t[ok][order]
        self.hlo = np.minimum(h1, h2)[ok][order]
        self.hhi = np.maximum(h1, h2)[ok][order]
        S = (load[ok][order] + crane["mb"]) * 1000.0 * G / (self.n * crane["e"])
        self.lgS = np.log10(np.maximum(S, 1e-300))
        # survey in force for each movement
        self.ep = np.clip(np.searchsorted(self.days, self.t, side="right") - 1,
                          0, len(self.days) - 1)

    def diam(self, j, pos):
        xs, ds = self.surveys[j]
        return np.interp(pos, xs, ds)

    def mirror(self, pos):
        return self.L - pos

    def terms_dense(self, sel, pos, dvec):
        """Damage of each movement in `sel` (index array) at element positions
        `pos` with diameters `dvec`: array (len(sel), len(pos))."""
        b0, b1, b2, b3 = self.b
        out = np.zeros((sel.size, pos.size))
        if sel.size == 0 or pos.size == 0:
            return out
        lgd = np.log10(dvec)
        hlo, hhi, lgS = self.hlo[sel], self.hhi[sel], self.lgS[sel]
        hmin, hmax = hlo.min(), hhi.max()
        for p, a, D, w in self.sheaves:
            # hook height at which this sheave's touch point is at the element
            hx = self.H - (self.L - a - pos) / p
            cols = np.nonzero((hx >= hmin) & (hx <= hmax))[0]
            if cols.size == 0:
                continue
            hxc = hx[cols]
            Y = np.log10(D) - lgd[cols]
            slope = b1 + b3 * Y
            base = b0 + b2 * Y - 2.0 * slope * lgd[cols]
            hit = (hlo[:, None] <= hxc[None, :]) & (hhi[:, None] >= hxc[None, :])
            mi, ci = np.nonzero(hit)
            if mi.size:
                out[mi, cols[ci]] += w * np.power(10.0, -(base[ci] + slope[ci] * lgS[mi]))
        return out

    def terms_sum(self, sel, pos, dvec, weight=None):
        """Sum over the movements `sel` (optionally weighted) of terms_dense."""
        tot = np.zeros(pos.size)
        for c0 in range(0, sel.size, CHUNK):
            T = self.terms_dense(sel[c0:c0 + CHUNK], pos, dvec)
            tot += T.sum(0) if weight is None else weight[c0:c0 + CHUNK] @ T
        return tot


def fit_wear(A, dd):
    """Least squares dd = c + k*A with k >= 0, for each row of A.
    A: (m, s), dd: (s,). Returns SSE per row."""
    Am = A.mean(1, keepdims=True)
    dm = dd.mean()
    Ac = A - Am
    dc = dd - dm
    sxx = (Ac * Ac).sum(1)
    sxy = (Ac * dc).sum(1)
    syy = (dc * dc).sum()
    with np.errstate(divide="ignore", invalid="ignore"):
        k = np.where(sxx > 0, sxy / sxx, 0.0)
    k = np.maximum(k, 0.0)
    sse = syy - 2 * k * sxy + k * k * sxx
    return np.maximum(sse, 0.0)


def interval_blocks(rope, j, P, Q, dvec):
    """Movements of survey interval j grouped in blocks (at most MAX_SPLITS),
    with each block's damage at element positions P and at Q.
    Returns sel, bounds, BP (nb, s), BQ (nb, s), prior over the nb+1 splits
    (split b: blocks [0, b) before the turn)."""
    t0, t1 = rope.days[j], rope.days[j + 1]
    sel = np.nonzero((rope.t >= t0) & (rope.t < t1))[0]
    m = sel.size
    if m == 0:
        return sel, np.array([0]), np.zeros((0, P.size)), np.zeros((0, P.size)), np.ones(1)
    bounds = np.unique(np.linspace(0, m, min(m, MAX_SPLITS) + 1).astype(int))
    nb = bounds.size - 1
    BP = np.zeros((nb, P.size))
    BQ = np.zeros((nb, P.size))
    for c0 in range(0, m, CHUNK):
        s_ = sel[c0:c0 + CHUNK]
        blk = np.searchsorted(bounds, np.arange(c0, c0 + s_.size), side="right") - 1
        ub, starts = np.unique(blk, return_index=True)
        BP[ub] += np.add.reduceat(rope.terms_dense(s_, P, dvec), starts, axis=0)
        BQ[ub] += np.add.reduceat(rope.terms_dense(s_, Q, dvec), starts, axis=0)
    tm = rope.t[sel]
    tmid = np.add.reduceat(tm, bounds[:-1]) / np.diff(bounds)
    span = np.maximum(np.diff(np.concatenate([[t0], tmid, [t1]])), 0.0)
    if span.sum() <= 0:
        span = np.ones_like(span)
    return sel, bounds, BP, BQ, span / span.sum()


def _logsumexp_w(v, w):
    top = v.max()
    return top + np.log(np.sum(w * np.exp(v - top)))


def orientation_scores(rope, j):
    """log P(surveys j, j+1 | r_j, r_j+1) for the four orientation pairs
    (0: as recorded, 1: measured from the dead end), each summed over turn /
    no turn.  None when the interval says nothing."""
    y1, d1 = rope.surveys[j + 1]
    if y1.size < 4 or rope.surveys[j][0].size < 2:
        return None
    P, Q = y1, rope.mirror(y1)
    # element recorded at y1[i] in survey j+1 was recorded in survey j at
    # y1[i] (s = 0) or at L - y1[i] (s = 1), s = r_j ^ r_j+1 ^ turn
    dd = (rope.diam(j, P) - d1, rope.diam(j, Q) - d1)
    sel, bounds, BP, BQ, prior = interval_blocks(rope, j, P, Q, d1)
    sumP, sumQ = BP.sum(0), BQ.sum(0)
    cP = np.vstack([np.zeros(P.size), np.cumsum(BP, 0)])
    cQ = np.vstack([np.zeros(P.size), np.cumsum(BQ, 0)])
    # rope wears at the elements' places; for r_j+1 = 0 the elements of
    # survey j+1 are at P (before a turn at Q), for r_j+1 = 1 at Q (before at P)
    nt = {0: sumP[None, :], 1: sumQ[None, :]}
    tu = {0: cQ + (sumP - cP), 1: cP + (sumQ - cQ)}
    fits = {}
    for rn in (0, 1):
        for sflag in (0, 1):
            fits[("nt", rn, sflag)] = fit_wear(nt[rn], dd[sflag])
            fits[("t", rn, sflag)] = fit_wear(tu[rn], dd[sflag])
    low = min(float(v.min()) for v in fits.values())
    s2 = max(NOISE_SD ** 2, low / max(P.size - 3, 1))
    out = {}
    for rj in (0, 1):
        for rn in (0, 1):
            s_nt = rj ^ rn
            a = np.log(1.0 - P_TURN) - fits[("nt", rn, s_nt)][0] / (2.0 * TEMPER * s2)
            b = np.log(P_TURN) + _logsumexp_w(
                -fits[("t", rn, 1 - s_nt)] / (2.0 * TEMPER * s2), prior)
            top = max(a, b)
            out[(rj, rn)] = top + np.log(np.exp(a - top) + np.exp(b - top))
    return out


def survey_orientations(rope):
    """Most probable orientation of every survey (Viterbi)."""
    J = len(rope.days)
    r = [0] * J
    if J < 2 or not rope.sheaves:
        return r
    lp = np.array([np.log(1.0 - P_FIRST_MIRRORED), np.log(P_FIRST_MIRRORED)])
    stay, flip = np.log(1.0 - P_FLIP), np.log(P_FLIP)
    back = []
    for j in range(J - 1):
        sc = orientation_scores(rope, j)
        new = np.empty(2)
        bk = [0, 0]
        for rn in (0, 1):
            cand = [lp[rj] + (stay if rj == rn else flip)
                    + (sc[(rj, rn)] if sc is not None else 0.0) for rj in (0, 1)]
            bk[rn] = int(np.argmax(cand))
            new[rn] = cand[bk[rn]]
        back.append(bk)
        lp = new
    r[-1] = int(np.argmax(lp))
    for j in range(J - 2, -1, -1):
        r[j] = back[j][r[j + 1]]
    return r


def to_rope_coordinates(rope, r):
    """Put the surveys measured from the dead end in rope coordinates."""
    for j, rj in enumerate(r):
        if rj:
            xs, ds = rope.surveys[j]
            xm = rope.mirror(xs)
            o = np.argsort(xm)
            rope.surveys[j] = (xm[o], ds[o])
    rope.stations = rope.surveys[-1][0]


def find_turns(rope):
    """For each survey interval j (survey j -> j+1): None, or a tuple
    (prob, sel, after): prob that the rope was turned end for end in the
    interval, the movements of the interval, and for each the probability,
    given a turn, that the turn came after the movement (so that the movement
    bent the element in its old position)."""
    J = len(rope.days)
    turns = [None] * J
    if not rope.sheaves:
        return turns
    for j in range(J - 1):
        t0, t1 = rope.days[j], rope.days[j + 1]
        x1, d1 = rope.surveys[j + 1]
        x0 = rope.surveys[j][0]
        if x1.size < 4 or x0.size < 2:
            continue
        lo, hi = x0.min(), x0.max()
        xm = rope.mirror(x1)
        # elements must have been measured (not extrapolated) under both frames
        keep = (x1 >= lo - 1e-6) & (x1 <= hi + 1e-6) & (xm >= lo - 1e-6) & (xm <= hi + 1e-6)
        if keep.sum() < 4:
            continue
        x1, d1, xm = x1[keep], d1[keep], xm[keep]
        sel = np.nonzero((rope.t >= t0) & (rope.t < t1))[0]
        if sel.size == 0:
            continue
        # no turn: element at x1 was at x1
        d_same = rope.diam(j, x1)
        dd0 = d_same - d1
        A0 = rope.terms_sum(sel, x1, d_same)
        sse0 = fit_wear(A0[None, :], dd0)[0]
        # turn: element at x1 was at L - x1; bent there before the turn and at
        # x1 after it.  Candidate turn times between blocks of movements.
        d_turn = rope.diam(j, xm)
        dd1 = d_turn - d1
        m = sel.size
        sel, bounds, B_new, B_old, prior = interval_blocks(rope, j, x1, xm, d_turn)
        tot_new = B_new.sum(0)
        # split b: blocks [0, b) before the turn, [b, nb) after
        A1 = tot_new[None, :] + np.vstack([np.zeros(x1.size), np.cumsum(B_old - B_new, 0)])
        sse1 = fit_wear(A1, dd1)
        best = sse1.min()
        nfree = x1.size - 3
        s2 = max(NOISE_SD ** 2, min(best, sse0) / max(nfree, 1))
        # turn time: uniform prior in time over the interval (prior);
        # tempered Gaussian likelihood of the wear fit
        loglik1 = -(sse1 - sse0) / (2.0 * TEMPER * s2)   # relative to no turn
        top = loglik1.max()
        with np.errstate(divide="ignore"):
            log_bf = top + np.log(np.sum(prior * np.exp(loglik1 - top)))
        z = log_bf + np.log(P_TURN / (1.0 - P_TURN))
        prob = 1.0 / (1.0 + np.exp(-z)) if z > -700 else 0.0
        if prob < 1e-6:
            continue
        lt = loglik1 * (TEMPER / TIME_TEMPER)
        post = prior * np.exp(lt - lt.max())
        post /= post.sum()
        # P(turn after movement k | turn): sum of post over splits after
        # the block of movement k
        after_split = np.cumsum(post[::-1])[::-1]  # [b] = sum over splits >= b
        blk = np.searchsorted(bounds, np.arange(m), side="right") - 1
        turns[j] = (prob, sel, after_split[blk + 1])
    return turns


def crane_damage(rope):
    """Damage of the elements at the stations of the last survey (in rope
    coordinates, rope.stations after the call)."""
    to_rope_coordinates(rope, survey_orientations(rope))
    xf = rope.stations
    ns = xf.size
    damage = np.zeros(ns)
    if rope.t.size == 0 or not rope.sheaves or ns == 0:
        return damage
    J = len(rope.days)
    turns = find_turns(rope)
    prob = np.array([t[0] if t is not None else 0.0 for t in turns])
    # q[j]: probability of an odd number of turns in the intervals after
    # interval j (i.e. between survey j+1 and the last survey)
    q = np.zeros(J)
    prod = 1.0
    for j in range(J - 1, -1, -1):
        q[j] = 0.5 * (1.0 - prod)
        prod *= 1.0 - 2.0 * prob[j]
    # given a turn in its interval: probability it came after the movement
    after = np.zeros(rope.t.size)
    after[rope.t < rope.days[0]] = 1.0    # before the first survey
    for t in turns:
        if t is not None:
            after[t[1]] = t[2]
    # An element at xf (last survey) lies at xf ("even") or at L - xf ("odd").
    # A movement in interval j bends it at its position at the time of the
    # movement; its diameter is read at its position at survey j.
    #   no turn in j:               bent at "later" parity, d at the same
    #   turn in j after the move:   bent at 1+later,        d at the same
    #   turn in j before the move:  bent at "later",        d at 1+later
    pos = (xf, rope.mirror(xf))
    for j in range(J):
        sel = np.nonzero(rope.ep == j)[0]
        if sel.size == 0:
            continue
        d = (rope.diam(j, pos[0]), rope.diam(j, pos[1]))
        pj, qj = prob[j], q[j]
        a = after[sel]
        # weights for (bent at parity, d read at parity)
        w = {
            (0, 0): (1 - pj) * (1 - qj) + pj * a * qj,
            (1, 1): (1 - pj) * qj + pj * a * (1 - qj),
            (0, 1): pj * (1 - a) * (1 - qj),
            (1, 0): pj * (1 - a) * qj,
        }
        for (bp, dp), wt in w.items():
            wt = np.broadcast_to(np.asarray(wt, dtype=float), sel.shape)
            if wt.max() <= 1e-12:
                continue
            for c0 in range(0, sel.size, CHUNK):
                s = sel[c0:c0 + CHUNK]
                ww = wt[c0:c0 + CHUNK]
                if ww.max() <= 1e-12:
                    continue
                T = rope.terms_dense(s, pos[bp], d[dp])
                damage += ww @ T
    return damage


def station_numbers(rope):
    """Numbers of the last survey's stations (rope coordinates), counted from
    the drum anchorage from 1 on the survey's grid of stations."""
    xs = rope.stations
    if xs.size < 2:
        return np.arange(1, xs.size + 1)
    step = np.median(np.diff(xs))
    if not step > 0:
        return np.arange(1, xs.size + 1)
    # first station of that grid ever surveyed (a station may be missing)
    allx = np.concatenate([x for x, _ in rope.surveys])
    off = (allx - xs[0]) / step
    on_grid = np.abs(off - np.round(off)) < 0.1
    x0 = allx[on_grid].min() if on_grid.any() else xs[0]
    k = np.round((xs - x0) / step).astype(int) + 1
    if np.unique(k).size != k.size or k.min() < 1:
        return np.arange(1, xs.size + 1)
    return k


# --------------------------------------------------------------------------

def main(argv):
    if len(argv) < 3:
        print("usage: python3 ropes.py WORKS_DIR OUT_CSV", file=sys.stderr)
        return
    wd, out_path = argv[1], argv[2]
    rows = []
    try:
        cr = read_table(os.path.join(wd, "cranes.csv"))
        sh = read_table(os.path.join(wd, "sheaves.csv"))
        mv = read_table(os.path.join(wd, "movements.csv"))
        sv = read_table(os.path.join(wd, "surveys.csv"))

        shd = pd.DataFrame({
            "crane": sh["crane"], "sheave": sh["sheave"].str.lower(),
            "p": num(sh["parts"]), "a": num(sh["offset_m"]),
            "D": num(sh["diameter_mm"]),
            "w": num(sh["bend_weight"]) if "bend_weight" in sh else np.nan,
        })
        mvd = pd.DataFrame({
            "crane": mv["crane"], "day": num(mv["day"]),
            "h1": num(mv["from_height_m"]), "h2": num(mv["to_height_m"]),
            "load": num(mv["hook_load_t"]),
        })
        svd = pd.DataFrame({
            "crane": sv["crane"], "day": num(sv["day"]),
            "x": num(sv["station_m"]), "d": num(sv["diameter_mm"]),
        })
        mv_g = {k: g for k, g in mvd.groupby("crane", sort=False)}
        sv_g = {k: g for k, g in svd.groupby("crane", sort=False)}
        sh_g = {k: g for k, g in shd.groupby("crane", sort=False)}

        seen = set()
        for _, c in cr.iterrows():
            name = c["crane"]
            if name in seen or name == "" or name not in sv_g:
                continue
            seen.add(name)
            s = sv_g[name]
            svc = {k: s[k].to_numpy(dtype=float) for k in ("day", "x", "d")}
            ok = (np.isfinite(svc["day"]) & np.isfinite(svc["x"])
                  & np.isfinite(svc["d"]) & (svc["d"] > 0))
            if not ok.any():
                continue
            last = svc["day"][ok].max()
            stations = np.unique(np.round(svc["x"][ok & (svc["day"] == last)], 6))
            numbers = np.arange(1, stations.size + 1)
            try:
                crane = {
                    "falls": num1(c.get("falls")),
                    "H": num1(c.get("upper_block_height_m")),
                    "mb": num1(c.get("block_mass_t")),
                    "e": num1(c.get("reeving_efficiency")),
                    "L": num1(c.get("rope_length_m")),
                    "construction": c.get("rope_construction", ""),
                }
                if not np.isfinite(crane["mb"]):
                    crane["mb"] = 0.0
                sheaves = []
                g = sh_g.get(name)
                if g is not None:
                    for _, r in g.iterrows():
                        drum = r["sheave"] == "drum"
                        p = r["p"] if np.isfinite(r["p"]) else (crane["falls"] if drum else np.nan)
                        w = r["w"] if np.isfinite(r["w"]) else (0.5 if drum else 1.0)
                        sheaves.append((p, r["a"], r["D"], w))
                m = mv_g.get(name)
                mvc = {k: (m[k].to_numpy(dtype=float) if m is not None else np.zeros(0))
                       for k in ("day", "h1", "h2", "load")}
                rope = Rope(crane, sheaves, mvc, svc)
                dmg = crane_damage(rope)
                numbers = station_numbers(rope)
            except Exception as exc:  # keep the other cranes' results
                print(f"crane {name}: {exc!r}", file=sys.stderr)
                dmg = np.zeros(stations.size)
            for k, v in zip(numbers, dmg):
                rows.append((f"{name}-{int(k):03d}", v))
    except Exception as exc:
        print(f"error: {exc!r}", file=sys.stderr)

    d = os.path.dirname(os.path.abspath(out_path))
    os.makedirs(d, exist_ok=True)
    with open(out_path, "w", newline="") as f:
        f.write("row,damage\n")
        for r, v in rows:
            f.write(f"{r},{fmt(v)}\n")


if __name__ == "__main__":
    try:
        main(sys.argv)
    except Exception as exc:  # never fail the run
        print(f"error: {exc!r}", file=sys.stderr)
    sys.exit(0)
