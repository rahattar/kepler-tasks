#!/usr/bin/env python3
"""Bending fatigue damage of crane hoist ropes to RS-4 (issue 3).

Usage: python3 ropes.py WORKS_DIR OUT_CSV

Reads cranes.csv, sheaves.csv, movements.csv and surveys.csv from WORKS_DIR (format of
works_package.md) and writes OUT_CSV with header `row,damage`: one row per station of each
crane's last rope survey, named <crane>-<NNN>, stations numbered from the drum anchorage.

RS-4 model
  * contact point of a sheave (the drum with p = n) at hook height h:  x = L - a - p (H - h),
    x measured along the rope from the drum anchorage;
  * a movement h1 -> h2 bends once, with weight w, every rope element between x(h1) and x(h2);
  * rope tension S = (m_h + m_b) g / (n e);
  * lg N = b0 + (b1 + b3 lg(D/d)) lg(S/d^2) + b2 lg(D/d), d the element's diameter at the last
    survey on or before the movement;
  * damage of an element = sum of w / N over all its bendings since the rope was put on (day 0),
    reported for the elements at the stations of the last survey, at the end of the log.

Ropes turned end for end
  Damage belongs to the rope element, not to the place on the crane. When a rope is turned end
  for end, the element that the last survey finds at x lay at L - x before. Every survey and
  every movement is mapped to the elements in the frame of the last survey.

  Turns are found from the surveys. A caliper that repeats to ~0.02 mm cannot show an element
  growing by tenths of a millimetre, so a survey whose profile matches the previous one mirrored
  (x -> L - x) far better than as it stands marks a turn in that interval. Weaker evidence (an
  early turn, before much wear has built up) is sought with a model of the wear: the diameter
  loss of element e over survey interval k is taken as
      loss_k(e) = b_k + F_k * A_e * dX_k(e)
  (b_k background wear, F_k wear per unit damage in interval k, A_e the element's own factor,
  dX_k(e) the RS-4 damage the element took in interval k). A turn is added where it lowers the
  misfit by far more than the caliper's noise allows by chance.

  The day of a turn inside its interval is not recorded. With a uniform prior over the interval
  and the same wear model, with a deliberately widened likelihood, the damage reported is the
  posterior expectation over the day of the turn; with weak evidence it tends to the damage for a
  turn at mid-interval.
"""
import os
import sys
import time

import numpy as np
import pandas as pd

G = 9.80665
COEF = {  # construction: (b0, b1, b2, b3)
    "8x36": (-1.214, 0.887, 7.432, -2.103),
    "6x36": (-1.371, 0.934, 7.518, -2.146),
}
EPS = 1e-9            # m: a station this close to the end of a travel counts half a bending
NOISE_MM = 0.02       # caliper repeatability
N_GRID = 81           # candidate days of a turn inside its survey interval
MAX_TURNS = 4         # turns looked for on one rope by the wear model
TURN_STAT = 40.0      # misfit reduction (in noise variances) needed for a turn
LIK_WIDEN = 2.0       # widening of the dating likelihood (correlated noise, model error)
CPU_BUDGET = 15.0     # s of CPU for the search; past it, turns not dated go to mid-interval
DEBUG = bool(os.environ.get("ROPES_DEBUG"))
_T0 = time.process_time()


def over_budget():
    return time.process_time() - _T0 > CPU_BUDGET


# ----------------------------------------------------------------------------------- input
def read_csv(path):
    df = pd.read_csv(path, skipinitialspace=True, encoding="utf-8-sig")
    df.columns = [str(c).strip().lower() for c in df.columns]
    for c in df.columns:
        if not pd.api.types.is_numeric_dtype(df[c]):
            df[c] = df[c].astype(str).str.strip()
    return df


def num(series):
    return pd.to_numeric(series, errors="coerce")


def construction_key(s):
    k = str(s).strip().lower().replace(" ", "").replace("×", "x")
    if k in COEF:
        return k
    for key in COEF:
        if key in k:
            return key
    raise KeyError("unknown rope construction %r" % s)


# --------------------------------------------------------------------------------- surveys
class Survey:
    def __init__(self, day, xs, ds):
        self.day = day
        self.xs = xs   # station positions, ascending, in the machine frame of that day
        self.ds = ds   # diameters

    def at(self, x):
        return np.interp(x, self.xs, self.ds)


def load_surveys(surv):
    surv = surv.dropna(subset=["day", "station_m", "diameter_mm"])
    surv = surv[(surv["day"] >= 0) & (surv["diameter_mm"] > 0)]
    out = []
    for dd, g in surv.groupby("day", sort=True):
        g = g.groupby("station_m", sort=True)["diameter_mm"].mean()
        out.append(Survey(float(dd), g.index.values.astype(float), g.values.astype(float)))
    return out


def spread(r):
    """robust residual spread about the median (mm)"""
    if len(r) == 0:
        return 0.0
    med = np.median(r)
    return float(np.sqrt(np.mean((r - med) ** 2)))


def detect_turns(surveys, L):
    """turned[k] is True when the rope was turned end for end between surveys k-1 and k."""
    turned = [False] * len(surveys)
    for k in range(1, len(surveys)):
        a, b = surveys[k - 1], surveys[k]
        if len(b.xs) < 4 or len(a.xs) < 4:
            continue
        x = b.xs
        ok_id = (x >= a.xs[0] - 1e-6) & (x <= a.xs[-1] + 1e-6)
        ok_rv = (L - x >= a.xs[0] - 1e-6) & (L - x <= a.xs[-1] + 1e-6)
        ok = ok_id & ok_rv
        if ok.sum() < 4:
            continue
        r_id = b.ds[ok] - a.at(x[ok])
        r_rv = b.ds[ok] - a.at(L - x[ok])
        s_id, s_rv = spread(r_id), spread(r_rv)
        # growth beyond the caliper's repeatability is impossible for one and the same element
        g_id = np.sort(r_id - np.median(r_id))[-max(1, len(r_id) // 10):].mean()
        g_rv = np.sort(r_rv - np.median(r_rv))[-max(1, len(r_rv) // 10):].mean()
        if s_rv < 0.6 * s_id and s_id > 1.75 * NOISE_MM and g_id > 2 * NOISE_MM and g_rv < g_id:
            turned[k] = True
    return turned


# -------------------------------------------------------------------------------- bendings
def bending_pairs(lo, hi, pts):
    """(movement index, point index, factor) for points of the sorted array `pts` passed by the
    travels [lo, hi]: 1 strictly inside, 0.5 at an end."""
    moving = (hi - lo) > EPS
    a_in = np.searchsorted(pts, lo + EPS, side="left")
    b_in = np.searchsorted(pts, hi - EPS, side="right")
    a_lo = np.searchsorted(pts, lo - EPS, side="left")
    b_hi = np.searchsorted(pts, hi + EPS, side="right")
    I, J, F = [], [], []
    for st0, st1, fac in ((a_in, b_in, 1.0), (a_lo, a_in, 0.5), (b_in, b_hi, 0.5)):
        cnt = np.where(moving, np.maximum(st1 - st0, 0), 0)
        tot = int(cnt.sum())
        if tot == 0:
            continue
        im = np.repeat(np.arange(len(cnt)), cnt)
        offs = np.arange(tot) - np.repeat(np.cumsum(cnt) - cnt, cnt)
        I.append(im)
        J.append(st0[im] + offs)
        F.append(np.full(tot, fac))
    if not I:
        z = np.zeros(0, dtype=np.int64)
        return z, z, np.zeros(0)
    return np.concatenate(I), np.concatenate(J), np.concatenate(F)


class Rope:
    """Geometry, reeving and endurance of one crane's rope."""

    def __init__(self, c, sheaves):
        self.n = float(c["falls"])
        self.H = float(c["upper_block_height_m"])
        self.L = float(c["rope_length_m"])
        self.mb = float(c["block_mass_t"]) * 1000.0
        self.e = float(c["reeving_efficiency"])
        self.b = COEF[construction_key(c["rope_construction"])]
        self.sheaves = []
        for _, r in sheaves.iterrows():
            is_drum = str(r["sheave"]).strip().lower() == "drum"
            p = r["parts"]
            p = float(self.n if (pd.isna(p) and is_drum) else p)
            a = float(r["offset_m"]) if not pd.isna(r["offset_m"]) else 0.0
            D = float(r["diameter_mm"])
            w = r["bend_weight"]
            w = float((0.5 if is_drum else 1.0) if pd.isna(w) else w)
            if np.isfinite(D) and D > 0 and w != 0 and np.isfinite(p):
                self.sheaves.append((p, a, D, w))

    def contributions(self, h1, h2, lgS, dsel, elem_pos):
        """Damage contributions of movements to elements.

        h1, h2, lgS: per movement; dsel(im, je) -> diameters for (movement, element) pairs;
        elem_pos: machine-frame positions of the elements (any order).
        Returns (movement index, element index, w/N) triples.
        """
        b0, b1, b2, b3 = self.b
        order = np.argsort(elem_pos, kind="stable")
        pts = elem_pos[order]
        IM, JE, V = [], [], []
        for p, a, D, w in self.sheaves:
            x1 = self.L - a - p * (self.H - h1)
            x2 = self.L - a - p * (self.H - h2)
            im, jp, fac = bending_pairs(np.minimum(x1, x2), np.maximum(x1, x2), pts)
            if len(im) == 0:
                continue
            je = order[jp]
            d = dsel(im, je)
            lgd = np.log10(d)
            u = np.log10(D) - lgd
            lgN = b0 + (b1 + b3 * u) * (lgS[im] - 2.0 * lgd) + b2 * u
            IM.append(im)
            JE.append(je)
            V.append(w * fac * np.power(10.0, -lgN))
        if not IM:
            z = np.zeros(0, dtype=np.int64)
            return z, z, np.zeros(0)
        return np.concatenate(IM), np.concatenate(JE), np.concatenate(V)


# ------------------------------------------------------------------------------ wear model
def rank1_fit(inc, dX, A0=None, iters=12):
    """Least squares fit of inc[k,e] = b_k + F_k A_e dX[k,e] by alternating least squares.
    Returns (residual sum of squares, A)."""
    K, P = inc.shape
    A = np.ones(P) if A0 is None else A0.copy()
    ym = inc.mean(1, keepdims=True)
    yc = inc - ym

    def fit_F(A):
        x = A[None, :] * dX
        xm = x.mean(1, keepdims=True)
        xc = x - xm
        sxx = (xc * xc).sum(1)
        F = np.where(sxx > 0, (xc * yc).sum(1) / np.where(sxx > 0, sxx, 1.0), 0.0)
        return F, ym[:, 0] - F * xm[:, 0]

    for _ in range(iters):
        F, b = fit_F(A)
        z = F[:, None] * dX
        den = (z * z).sum(0)
        A = np.where(den > 0, (z * (inc - b[:, None])).sum(0) / np.where(den > 0, den, 1.0), 0.0)
        nz = A[den > 0]
        sc = np.sqrt(np.mean(nz * nz)) if len(nz) else 0.0
        if sc > 0:
            A = A / sc
    F, b = fit_F(A)
    r = inc - b[:, None] - F[:, None] * (A[None, :] * dX)
    return float((r * r).sum()), A


# ---------------------------------------------------------------------------------- crane
def crane_damage(c, sheaves, movs, surv):
    rope = Rope(c, sheaves)
    L = rope.L
    name = c["crane"]
    surveys = load_surveys(surv)
    elem = surveys[-1].xs.copy() if surveys else np.arange(2.5, L, 5.0)   # last survey's stations
    P = len(elem)
    dmg = np.zeros(P)
    if P == 0:
        return elem, dmg

    # movements of this rope (since it was put on, day 0), in time order
    m = movs.dropna(subset=["day", "from_height_m", "to_height_m", "hook_load_t"])
    m = m[m["day"] >= 0]
    if len(m) == 0 or not rope.sheaves:
        return elem, dmg
    day = m["day"].values.astype(float)
    order = np.argsort(day, kind="stable")
    day = day[order]
    h1 = m["from_height_m"].values.astype(float)[order]
    h2 = m["to_height_m"].values.astype(float)[order]
    S = (m["hook_load_t"].values.astype(float)[order] * 1000.0 + rope.mb) * G / (rope.n * rope.e)
    lgS = np.log10(np.maximum(S, 1e-300))

    if not surveys:   # nothing measured: no better guess than a usual D/d
        dnom = min(D for _, _, D, _ in rope.sheaves) / 20.0
        im, je, v = rope.contributions(h1, h2, lgS, lambda i, j: np.full(len(i), dnom), elem)
        return elem, np.bincount(je, weights=v, minlength=P)

    nS = len(surveys)
    sdays = np.array([s.day for s in surveys])
    pos = (elem, L - elem)            # machine positions of the elements, as laid / turned
    dmach = [np.array([s.at(pos[o]) for s in surveys]) for o in (0, 1)]
    si = np.clip(np.searchsorted(sdays, day, side="right") - 1, 0, nS - 1)   # survey in force
    ivl = np.searchsorted(sdays, day, side="right")   # interval: survey ivl-1 <= day < survey ivl

    # time cells: one before the first survey, NG-1 in each survey interval, one after the last
    NG = N_GRID
    cell = np.zeros(len(day), dtype=np.int64)
    inner = (ivl >= 1) & (ivl <= nS - 1)
    k_in = ivl[inner]
    t0 = sdays[k_in - 1]
    t1 = sdays[k_in]
    frac = (day[inner] - t0) / np.where(t1 > t0, t1 - t0, 1.0)
    cell[inner] = 1 + (k_in - 1) * (NG - 1) + np.clip((frac * (NG - 1)).astype(np.int64), 0, NG - 2)
    ncell = 2 + (nS - 1) * (NG - 1)
    cell[ivl >= nS] = ncell - 1

    def cell_sums(o, dsel):
        im, je, v = rope.contributions(h1, h2, lgS, dsel, pos[o])
        return np.bincount(cell[im] * P + je, weights=v, minlength=ncell * P).reshape(ncell, P)

    def cum_cells(Q):
        """per survey interval k (1..nS-1): cumulative damage over its cells, shape (NG, P)"""
        out = [None]
        for k in range(1, nS):
            blk = Q[1 + (k - 1) * (NG - 1): 1 + k * (NG - 1)]
            out.append(np.vstack([np.zeros(P), np.cumsum(blk, 0)]))
        return out

    def orientations(turns):
        o = np.zeros(nS, dtype=int)
        for k in range(nS - 2, -1, -1):
            o[k] = o[k + 1] ^ (1 if (k + 1) in turns else 0)
        return o

    def interval_damage(Cc, o, k, turns):
        if k in turns:
            g = turns[k]
            return Cc[o[k - 1]][k][g] + Cc[o[k]][k][-1] - Cc[o[k]][k][g]
        return Cc[o[k]][k][-1]

    # ---- turns plain from consecutive surveys
    turns = {}
    weights = {}
    if nS >= 2:
        turned = detect_turns(surveys, L)
        turns = {k: NG // 2 for k in range(1, nS) if turned[k]}
        if DEBUG and turns:
            sys.stderr.write("%s turns seen between surveys: %s\n"
                             % (name, [(sdays[k - 1], sdays[k]) for k in sorted(turns)]))

    # ---- weaker evidence of turns and the days of the turns, from the wear the surveys show
    if nS >= 3 and not over_budget():
        Cd = [cum_cells(cell_sums(o, (lambda oo: lambda i, j: dmach[oo][si[i], j])(o)))
              for o in (0, 1)]

        def model(tr):
            o = orientations(tr)
            dtab = np.array([dmach[o[k]][k] for k in range(nS)])
            inc = dtab[:-1] - dtab[1:]
            dX = np.array([interval_damage(Cd, o, k, tr) for k in range(1, nS)])
            return inc, dX

        inc, dX = model(turns)
        sse_cur, A_cur = rank1_fit(inc, dX, iters=40)
        if turns:   # place the seeded turns at their best day before searching for more
            for k in sorted(turns):
                best = None
                for g in range(0, NG, 4):
                    tr = dict(turns)
                    tr[k] = g
                    sse, _ = rank1_fit(*model(tr), A0=A_cur, iters=10)
                    if best is None or sse < best[0]:
                        best = (sse, g)
                turns[k] = best[1]
            sse_cur, A_cur = rank1_fit(*model(turns), A0=A_cur, iters=40)
        nobs = inc.size
        coarse = sorted(set(np.linspace(0, NG - 1, 11).round().astype(int)))
        for _round in range(MAX_TURNS):
            if over_budget():
                break
            best = None
            for k in range(1, nS):
                if k in turns:
                    continue
                for g in coarse:
                    tr = dict(turns)
                    tr[k] = g
                    sse, _ = rank1_fit(*model(tr), A0=A_cur, iters=10)
                    if best is None or sse < best[0]:
                        best = (sse, k, g)
            if best is None:
                break
            sse_b, kb, gb = best
            tr = dict(turns)
            tr[kb] = gb
            sse_b, A_b = rank1_fit(*model(tr), A0=A_cur, iters=40)
            sig2 = max(sse_b / max(nobs - 2 * P - 2 * len(tr), 1), (0.25 * NOISE_MM) ** 2)
            stat = (sse_cur - sse_b) / sig2
            if DEBUG:
                sys.stderr.write("%s candidate turn in (%.2f, %.2f) stat %.1f\n"
                                 % (name, sdays[kb - 1], sdays[kb], stat))
            if stat < TURN_STAT:
                break
            turns, sse_cur, A_cur = tr, sse_b, A_b

        # posterior over the day of each turn (uniform prior), the other turns held
        for _pass in range(2 if len(turns) > 1 else 1):
            for k in sorted(turns):
                if over_budget():
                    break
                sse = np.empty(NG)
                for g in range(NG):
                    tr = dict(turns)
                    tr[k] = g
                    sse[g], _ = rank1_fit(*model(tr), A0=A_cur, iters=10)
                sig2 = max(sse.min() / max(nobs - 2 * P - 2 * len(turns), 1), (0.25 * NOISE_MM) ** 2)
                ll = -(sse - sse.min()) / (2.0 * LIK_WIDEN * sig2)
                w = np.exp(ll - ll.max())
                w /= w.sum()
                weights[k] = w
                turns[k] = int(np.argmax(w))
                if DEBUG:
                    tg = np.linspace(sdays[k - 1], sdays[k], NG)
                    mu = (w * tg).sum()
                    sys.stderr.write("%s turn in (%.2f, %.2f): mean day %.2f sd %.2f\n" % (
                        name, tg[0], tg[-1], mu, np.sqrt(max((w * tg * tg).sum() - mu * mu, 0))))

    # ---- damage with the diameters of the elements themselves
    o = orientations(turns)
    dtab = np.array([dmach[o[k]][k] for k in range(nS)])
    need = {o[0], 0} | {o[k] for k in range(nS)}
    Qx = {oo: cell_sums(oo, lambda i, j: dtab[si[i], j]) for oo in need}
    Cx = {oo: cum_cells(Qx[oo]) for oo in need}
    dmg += Qx[o[0]][0] + Qx[0][ncell - 1]
    for k in range(1, nS):
        if k in turns:
            g = np.arange(NG)
            a, b = o[k - 1], o[k]
            cand = Cx[a][k][g] + Cx[b][k][-1][None, :] - Cx[b][k][g]
            w = weights.get(k, np.full(NG, 1.0 / NG))
            dmg += (w[:, None] * cand).sum(0)
        else:
            dmg += Cx[o[k]][k][-1]
    return elem, dmg


# ----------------------------------------------------------------------------------- main
def fmt(v):
    if not np.isfinite(v):
        v = 0.0
    return np.format_float_positional(float(v), trim="-")


def run(wd):
    cranes = read_csv(os.path.join(wd, "cranes.csv"))
    sheaves = read_csv(os.path.join(wd, "sheaves.csv"))
    movs = read_csv(os.path.join(wd, "movements.csv"))
    surv = read_csv(os.path.join(wd, "surveys.csv"))
    for col in ("falls", "upper_block_height_m", "block_mass_t", "reeving_efficiency",
                "rope_length_m"):
        cranes[col] = num(cranes[col])
    for col in ("parts", "offset_m", "diameter_mm", "bend_weight"):
        sheaves[col] = num(sheaves[col])
    for col in ("day", "from_height_m", "to_height_m", "hook_load_t"):
        movs[col] = num(movs[col])
    for col in ("day", "station_m", "diameter_mm"):
        surv[col] = num(surv[col])

    sh_g = {k: g for k, g in sheaves.groupby("crane", sort=False)}
    mv_g = {k: g for k, g in movs.groupby("crane", sort=False)}
    sv_g = {k: g for k, g in surv.groupby("crane", sort=False)}
    empty_sh, empty_mv, empty_sv = sheaves.iloc[0:0], movs.iloc[0:0], surv.iloc[0:0]

    rows = []
    seen = set()
    for _, c in cranes.iterrows():
        name = c["crane"]
        if name in seen:
            continue
        seen.add(name)
        elem, dmg = crane_damage(c, sh_g.get(name, empty_sh), mv_g.get(name, empty_mv),
                                 sv_g.get(name, empty_sv))
        for i in range(len(elem)):
            rows.append(("%s-%03d" % (name, i + 1), dmg[i]))
    return rows


def main():
    if len(sys.argv) != 3:
        sys.stderr.write("usage: python3 ropes.py WORKS_DIR OUT_CSV\n")
        return 2
    wd, out = sys.argv[1], sys.argv[2]
    rows = run(wd)
    d = os.path.dirname(os.path.abspath(out))
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)
    with open(out, "w") as f:
        f.write("row,damage\n")
        for r, v in rows:
            f.write("%s,%s\n" % (r, fmt(v)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
