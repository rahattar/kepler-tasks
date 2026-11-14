#!/usr/bin/env python3
"""Bending fatigue damage along crane hoist ropes to RS-4 (Issue 3).

    python3 ropes.py WORKS_DIR OUT_CSV

WORKS_DIR is a works package (cranes.csv, sheaves.csv, movements.csv, surveys.csv) as described in
works_package.md. OUT_CSV gets the table `row,damage`: one row for every station of the last survey of
every crane's rope, named `<crane>-<station number from 001, counted from the drum anchorage>`.

Model (RS-4). A station at x on the rope is passed by the point of touch of a sheave (parts p, offset a)
when the hook passes the height  h = H - (L - a - x)/p  (s.1), so a movement bends the station over that
sheave once if its height range holds h (s.2). The damage of an element is the sum of w/N over its
bendings (s.5), N from s.4 with the tension of s.3 and d the element's diameter at the last survey not
later than the movement.

Ropes turned end for end. Damage belongs to the rope element, not to the place on the crane. A rope
turned end for end between two surveys shows it in the surveys: each survey is recorded from the drum
anchorage of its day, so the later profile is the earlier one mirrored (x -> L - x), far beyond the
gauge's repeatability. For every interval between surveys the program weighs "not turned" against
"turned on day tau" by how well each element's diameter decrease over the interval follows the
damage the element took in it (wear goes with bending), and takes a turn only on strong evidence; the
day of the turn is the tau that fits best. Each element's damage is reckoned where the element was on
the rope at each movement, and reported at the stations of the last survey.

Computation. With u = lg S, v = lg d, RS-4 s.4 gives exactly

    1/N(S, D, d) = 1/N(S0, D, d) * 10^(-c0 t) * 10^(eps t),   t = u - lg S0,
    c0 = b1 + b3 (lg D - v0),  eps = b3 (v - v0),

so for each sheave diameter D and each stretch of time the movement side reduces to the moments
sum 10^(-c0 t) t^q of the movements whose height range holds an element's touch height. They are
summed for all elements at once with difference arrays (bincount + cumsum over the sorted touch
heights). 10^(eps t) is a power series in eps t (|eps t| is small: eps follows only the rope's wear),
with the number of terms set by a bound on the truncation error (< 1e-9).
"""
import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import math
import re
import sys
import tempfile
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

G = 9.80665
COEF = {
    "8x36": (-1.214, 0.887, 7.432, -2.103),
    "6x36": (-1.371, 0.934, 7.518, -2.146),
}
LN10 = math.log(10.0)
MAX_BINS = 4_000_000      # cells of one difference array (time bins x touch heights)
TRUNC_TOL = 1e-9          # bound on the relative truncation error of the series
TURN_LR = 25.0            # evidence needed to take a rope as turned in an interval: n ln(SSE0/SSE1)
CLEAR_RATIO = 2.0         # profile match: mirrored misfit >= this x straight misfit -> clearly not turned
SUBBINS_TOTAL = 800       # time bins used to place turns, over all the intervals weighed for a rope
DEBUG = bool(os.environ.get("ROPES_DEBUG"))


def dbg(*a):
    if DEBUG:
        sys.stderr.write(" ".join(str(x) for x in a) + "\n")


# ----------------------------------------------------------------------------------------- reading

def _key(name):
    return re.sub(r"\s+", " ", str(name)).strip().upper()


def _colname(c):
    return re.sub(r"\s+", "_", str(c).replace("﻿", "").strip().lower())


def _numeric(s):
    s = s.astype(str).str.strip()
    out = pd.to_numeric(s, errors="coerce")
    bad = out.isna() & (s != "")
    if bad.any():  # tolerate a decimal comma or stray characters
        fixed = pd.to_numeric(s[bad].str.replace(",", ".", regex=False)
                              .str.replace(r"[^0-9eE+\-.]", "", regex=True), errors="coerce")
        out = out.copy()
        out[bad] = fixed
    return out.astype(float)


def read_table(path, numeric):
    """Read a small package table; normalise column names, crane keys and numeric columns."""
    df = pd.read_csv(path, dtype=str, keep_default_na=False, skipinitialspace=True,
                     encoding="utf-8-sig", index_col=False, on_bad_lines="skip")
    df.columns = [_colname(c) for c in df.columns]
    for col in numeric:
        df[col] = _numeric(df[col]) if col in df.columns else np.nan
    if "crane" not in df.columns:
        df["crane"] = ""
    df["key"] = df["crane"].map(_key)
    return df


def read_by_crane(path, cols):
    """A large table as {crane key: {column: float array}}, rows in file order. Fast typed read,
    with a tolerant reader as the fallback."""
    try:
        df = pd.read_csv(path, dtype={"crane": "category"}, engine="c", encoding="utf-8-sig",
                         low_memory=False, index_col=False, skipinitialspace=True)
        df.columns = [_colname(c) for c in df.columns]
        if "crane" not in df.columns:
            raise ValueError("columns")
        for c in cols:
            if c not in df.columns:
                df[c] = np.nan
            elif df[c].dtype.kind not in "fi":  # a stray cell: coerce this column only
                df[c] = _numeric(df[c])
        cat = df["crane"].astype("category")
        keys = np.array([_key(c) for c in cat.cat.categories], dtype=object)
        codes = cat.cat.codes.to_numpy()
        arrs = {c: df[c].to_numpy(dtype=float) for c in cols}
        out = {}
        ukeys = np.unique(keys) if len(keys) else []
        if len(ukeys) == len(keys):  # one category a crane: group by code
            order = np.argsort(codes, kind="stable")
            sc = codes[order]
            for ci, k in enumerate(keys):
                a, b = np.searchsorted(sc, ci, "left"), np.searchsorted(sc, ci, "right")
                sel = order[a:b]
                out[k] = {c: arrs[c][sel] for c in cols}
        else:
            for k in ukeys:
                sel = np.isin(codes, np.nonzero(keys == k)[0])
                out[k] = {c: arrs[c][sel] for c in cols}
        return out
    except Exception:
        df = read_table(path, cols)
        return {k: {c: g[c].to_numpy(dtype=float) for c in cols} for k, g in df.groupby("key", sort=False)}


def construction_coef(text):
    t = str(text).strip().lower().replace("×", "x").replace(" ", "")
    for name, cf in COEF.items():
        if t.startswith(name) or name in t:
            return cf
    return COEF["8x36"] if t.startswith("8") else COEF["6x36"]


# ---------------------------------------------------------------------------------- per-crane data

class Rope:
    pass


def _f(v, default=np.nan):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return default
    return v if np.isfinite(v) else default


def drop_misreadings(x, d):
    """Drop gross misreadings of a survey (a slipped digit, a zero): readings far from the survey's
    median or from their neighbours along the rope. Wear and the gauge's repeatability (0.02 mm) are
    far inside these limits; the stations dropped are interpolated from their neighbours."""
    if len(d) < 3:
        return x, d
    med = float(np.median(d))
    ok = (d > 0.6 * med) & (d < 1.4 * med)
    if len(d) >= 5:
        pad = np.pad(d, 2, mode="edge")
        loc = np.median(np.lib.stride_tricks.sliding_window_view(pad, 5), axis=1)
        ok &= np.abs(d - loc) <= max(1.0, 0.06 * med)
    if ok.sum() < max(2, len(d) // 2):
        return x, d
    return x[ok], d[ok]


def prepare(crow, sheaves, mov, surv):
    """Collect what one crane's reckoning needs."""
    r = Rope()
    r.name = str(crow["crane"]).strip()
    r.b = construction_coef(crow.get("rope_construction", ""))
    r.n = _f(crow["falls"])
    r.H = _f(crow["upper_block_height_m"])
    r.mb = _f(crow["block_mass_t"], 0.0)
    e = _f(crow["reeving_efficiency"], 1.0)
    if e <= 0:
        e = 1.0
    elif e > 1.5:  # given in per cent
        e = e / 100.0
    r.e = e
    r.xs = np.zeros(0)
    r.dm = None
    r.lo = np.zeros(0)
    r.sheaves = []

    sh = []
    for _, q in sheaves.iterrows():
        is_drum = str(q.get("sheave", "")).strip().lower().startswith("drum")
        p = _f(q["parts"], r.n if is_drum else np.nan)
        D = _f(q["diameter_mm"])
        w = _f(q["bend_weight"], 0.5 if is_drum else 1.0)
        a = _f(q["offset_m"], 0.0)
        if not (np.isfinite(p) and p > 0 and np.isfinite(D) and D > 0) or w == 0:
            continue
        sh.append((float(p), float(a), float(D), float(w)))

    # ---- surveys
    if surv is not None:
        sd, sx, sdia = surv["day"], surv["station_m"], surv["diameter_mm"]
        ok = np.isfinite(sd) & np.isfinite(sx)
    if surv is None or not (ok & np.isfinite(sdia) & (sdia > 0)).any():
        # no survey at all: the stations of the rope's layout (1 m apart, 0.5 m from the ends) and a
        # diameter estimated from the sheaves (D/d is near 26.5 in every package seen, sizes even mm)
        L = _f(crow["rope_length_m"])
        if not (np.isfinite(L) and L >= 1 and sh):
            return r
        Ds = [s[2] for s in sh if s[3] >= 1.0] or [s[2] for s in sh]
        dguess = max(2.0, 2.0 * round(max(Ds) / 26.5 / 2.0))
        xs = np.arange(int(round(L))) + 0.5
        surv = {"day": np.zeros(len(xs)), "station_m": xs, "diameter_mm": np.full(len(xs), dguess)}
        dbg(f"{r.name}: no survey, stations from L and d taken as {dguess} mm")
        sd, sx, sdia = surv["day"], surv["station_m"], surv["diameter_mm"]
        ok = np.ones(len(xs), dtype=bool)
    sd, sx, sdia = sd[ok], sx[ok], sdia[ok]
    days = np.unique(sd)
    r.xs = np.unique(sx[sd == days[-1]])
    L = _f(crow["rope_length_m"])
    if not np.isfinite(L) or L <= 0:
        L = float(r.xs.min() + r.xs.max())
    r.L = L
    order = np.lexsort((sx, sd))
    sd, sx, sdia = sd[order], sx[order], sdia[order]
    bounds = np.searchsorted(sd, days, side="left").tolist() + [len(sd)]
    surveys = []
    for k in range(len(days)):
        a, b = bounds[k], bounds[k + 1]
        x, d = sx[a:b], sdia[a:b]
        good = np.isfinite(d) & (d > 0)
        x, d = x[good], d[good]
        if len(x):
            ux, inv = np.unique(x, return_inverse=True)
            if len(ux) != len(x):
                d = np.bincount(inv, weights=d) / np.bincount(inv)
            ux, d = drop_misreadings(ux, d)
            if len(ux):
                surveys.append((days[k], ux, d))
    if not surveys:
        return r
    r.days = np.array([t for t, _, _ in surveys])
    r.surveys = [(x, d) for _, x, d in surveys]
    r.dm = np.vstack([survey_at(r, k, r.xs) for k in range(len(r.days))])
    # length the rope is mirrored about when turned end for end: the surveys' span (first and last
    # station 0.5 m from the ends), which is L when the records agree
    span = float(r.xs.min() + r.xs.max())
    r.Lm = r.L if abs(span - r.L) <= 1.0 else span
    r.sheaves = sh

    # ---- movements
    if mov is None or not (np.isfinite(r.n) and r.n > 0 and np.isfinite(r.H)):
        return r
    day = np.asarray(mov["day"], dtype=float)
    h1 = np.asarray(mov["from_height_m"], dtype=float)
    h2 = np.asarray(mov["to_height_m"], dtype=float)
    ld = np.asarray(mov["hook_load_t"], dtype=float)
    if not np.isfinite(day).all():
        day = pd.Series(day).ffill().fillna(0.0).to_numpy()
    ld = np.where(np.isfinite(ld), ld, 0.0)
    keep = np.isfinite(h1) & np.isfinite(h2) & (h1 != h2) & (day >= 0)
    if not keep.all():
        day, h1, h2, ld = day[keep], h1[keep], h2[keep], ld[keep]
    S = (ld + r.mb) * (1000.0 * G) / (r.n * r.e)
    ok = S > 0
    if not ok.all():
        day, h1, h2, S = day[ok], h1[ok], h2[ok], S[ok]
    r.lo = np.minimum(h1, h2)
    r.hi = np.maximum(h1, h2)
    r.u = np.log10(S)
    r.day = day
    r.k = np.clip(np.searchsorted(r.days, day, side="right") - 1, 0, len(r.days) - 1).astype(np.int64)
    return r


def survey_at(r, k, pos):
    x, d = r.surveys[k]
    return np.interp(pos, x, d)


def positions(r, o):
    """Rope positions (from the drum anchorage) of the final stations' elements, orientation o."""
    return r.xs if o == 0 else r.Lm - r.xs


# ------------------------------------------------------------------------------------- reckoning

def lgN(b, D, d, u):
    b0, b1, b2, b3 = b
    lDd = np.log10(D) - np.log10(d)
    return b0 + (b1 + b3 * lDd) * (u - 2.0 * np.log10(d)) + b2 * lDd


class Touch:
    """Touch heights of every sheave at every element in both orientations, per sheave diameter
    group, and where each movement's height range starts and ends among them."""

    def __init__(self, r):
        nst = len(r.xs)
        groups = {}
        for sh in r.sheaves:
            groups.setdefault(round(sh[2], 9), []).append(sh)
        self.groups = list(groups.values())
        hq = []
        for members in self.groups:
            for (p, a, _, _) in members:
                for o in (0, 1):
                    hq.append(r.H - (r.L - a - positions(r, o)) / p)
        hq = np.round(np.concatenate(hq), 9)
        hs_all, inv = np.unique(hq, return_inverse=True)
        plo = np.searchsorted(hs_all, r.lo, side="left")
        phi = np.searchsorted(hs_all, r.hi, side="right")
        self.P, self.plo, self.phi, self.idx = [], [], [], []
        blk = 0
        for g, members in enumerate(self.groups):
            nblk = 2 * len(members)
            gi = inv[blk * nst:(blk + nblk) * nst]
            mask = np.zeros(len(hs_all), dtype=bool)
            mask[gi] = True
            cnt = np.concatenate([[0], np.cumsum(mask)])
            self.P.append(int(mask.sum()))
            self.plo.append(cnt[plo])
            self.phi.append(cnt[phi])
            idx = {}
            for j in range(len(members)):
                for o in (0, 1):
                    b = 2 * j + o
                    idx[(j, o)] = cnt[gi[b * nst:(b + 1) * nst]]
            self.idx.append(idx)
            blk += nblk


def binned_sums(plo, phi, P, binm, nbins, weights):
    """For each weight vector: F[b, i] = sum of the weights of the movements in bin b whose height
    range holds touch height i (i < P). Movements with binm < 0 are left out. Yields chunks of bins."""
    live = (plo < phi) & (binm >= 0)
    if not live.all():
        plo, phi, binm = plo[live], phi[live], binm[live]
        weights = [w[live] for w in weights]
    if len(binm) > 1 and not np.all(binm[1:] >= binm[:-1]):
        order = np.argsort(binm, kind="stable")
        plo, phi, binm = plo[order], phi[order], binm[order]
        weights = [w[order] for w in weights]
    bb = np.searchsorted(binm, np.arange(nbins + 1), side="left")
    per = max(1, MAX_BINS // (P + 1))
    for ba in range(0, nbins, per):
        bz = min(nbins, ba + per)
        ma, mz = bb[ba], bb[bz]
        nb = (bz - ba) * (P + 1)
        if mz <= ma:
            yield ba, bz, [np.zeros((bz - ba, P)) for _ in weights]
            continue
        kk = (binm[ma:mz] - ba) * (P + 1)
        idx = np.concatenate([kk + plo[ma:mz], kk + phi[ma:mz]])
        out = []
        for w in weights:
            wv = w[ma:mz]
            F = np.bincount(idx, weights=np.concatenate([wv, -wv]), minlength=nb)
            out.append(np.cumsum(F.reshape(bz - ba, P + 1), axis=1)[:, :P])
        yield ba, bz, out


def reference_u(u, c0):
    z = -c0 * (u - u.max())
    wt = np.power(10.0, z - z.max())
    s = wt.sum()
    return float(np.dot(wt, u) / s) if s > 0 else float(u.mean())


# ---- pass 1: where the elements were (turns), from damage increments and the survey wear

def profile_misfit(r, k):
    """Misfit of survey k+1 against survey k read straight and read mirrored."""
    xa, da = r.surveys[k]
    xb, db = r.surveys[k + 1]
    out = []
    for pos in (xb, r.Lm - xb):
        inside = (pos >= xa[0] - 0.5) & (pos <= xa[-1] + 0.5)
        if inside.sum() < 3:
            out.append(np.inf)
            continue
        diff = np.interp(pos[inside], xa, da) - db[inside]
        out.append(float(np.mean(np.abs(diff - np.median(diff)))))
    return out


def coarse_increments(r, T, cand, nsub):
    """Damage increments of every element in nsub time bins of each interval in cand, in both
    orientations, d taken as the survey's median (enough to weigh patterns): G1[c, b, o, s]."""
    nst = len(r.xs)
    K = len(r.days)
    slot = np.full(K, -1, dtype=np.int64)
    for c, k in enumerate(cand):
        slot[k] = c
    sm = slot[r.k]
    binm = np.full(len(r.lo), -1, dtype=np.int64)
    sel = sm >= 0
    if sel.any():
        kk = r.k[sel]
        t0, t1 = r.days[kk], r.days[np.minimum(kk + 1, K - 1)]
        f = np.floor((r.day[sel] - t0) / np.maximum(t1 - t0, 1e-12) * nsub)
        binm[sel] = sm[sel] * nsub + np.clip(f, 0, nsub - 1).astype(np.int64)
    nbins = len(cand) * nsub
    bin_k = np.repeat(np.asarray(cand, dtype=np.int64), nsub)
    vbar = np.array([float(np.median(np.log10(d))) for _, d in r.surveys])
    b0, b1, b2, b3 = r.b
    G1 = np.zeros((nbins, 2, nst))
    for g, members in enumerate(T.groups):
        D = members[0][2]
        ck = b1 + b3 * (math.log10(D) - vbar)          # exponent of S per survey period
        u0 = reference_u(r.u, float(np.median(ck)))
        W = np.zeros(len(r.u))
        W[sel] = np.power(10.0, -ck[r.k[sel]] * (r.u[sel] - u0))
        base = np.power(10.0, -lgN(r.b, D, np.power(10.0, vbar), u0))   # (K,)
        for ba, bz, (F,) in binned_sums(T.plo[g], T.phi[g], T.P[g], binm, nbins, [W]):
            fac = base[bin_k[ba:bz]][:, None]
            for j, (_, _, _, w) in enumerate(members):
                for o in (0, 1):
                    G1[ba:bz, o] += (w * fac) * F[:, T.idx[g][(j, o)]]
    return G1.reshape(len(cand), nsub, 2, nst)


def _sse_rows(dec, X):
    """Residual sums of squares of dec ~ alpha X[i] + beta (alpha >= 0) for every row X[i]."""
    Xc = X - X.mean(axis=1, keepdims=True)
    dc = dec - dec.mean()
    sxx = np.einsum("ij,ij->i", Xc, Xc)
    sxy = Xc @ dc
    alpha = np.where(sxx > 0, sxy / np.where(sxx > 0, sxx, 1.0), 0.0)
    alpha = np.maximum(alpha, 0.0)
    return float(dc @ dc) - 2.0 * alpha * sxy + alpha * alpha * sxx


def orientations(r, T):
    """From the last survey backwards: the orientation of each survey's record relative to the last
    one (0 same, 1 turned end for end), and the day of each turn {interval k: day}."""
    K = len(r.days)
    o = np.zeros(K, dtype=np.int64)
    turns = {}
    if K < 2 or len(r.lo) == 0 or not r.sheaves:
        return o, turns
    cand = []
    for k in range(K - 1):
        straight, mirrored = profile_misfit(r, k)
        if not (mirrored >= CLEAR_RATIO * straight):
            cand.append(k)
        dbg(f"  {r.name} interval {k}: profile misfit straight {straight:.4f} mirrored {mirrored:.4f}")
    if not cand:
        return o, turns
    nsub = int(max(4, min(48, SUBBINS_TOTAL // len(cand))))
    G1 = coarse_increments(r, T, cand, nsub)
    slot = {k: c for c, k in enumerate(cand)}
    nst = len(r.xs)
    for k in range(K - 2, -1, -1):
        on = o[k + 1]
        if k not in slot:
            o[k] = on
            continue
        oo = 1 - on
        g_new = G1[slot[k], :, on]      # (nsub, nst): increments with the elements as at survey k+1
        g_old = G1[slot[k], :, oo]      # ... as turned
        d_next = survey_at(r, k + 1, positions(r, on))
        dec0 = survey_at(r, k, positions(r, on)) - d_next
        dec1 = survey_at(r, k, positions(r, oo)) - d_next
        sse0 = float(_sse_rows(dec0, g_new.sum(axis=0)[None, :])[0])
        cn = np.vstack([np.zeros(nst), np.cumsum(g_new, axis=0)])
        co = np.vstack([np.zeros(nst), np.cumsum(g_old, axis=0)])
        X = co + (cn[nsub] - cn)        # row i: turned after the first i bins of the interval
        sse = _sse_rows(dec1, X)
        i1 = int(np.argmin(sse))
        sse1 = float(sse[i1])
        lr = nst * math.log(max(sse0, 1e-300) / max(sse1, 1e-300))
        dbg(f"  {r.name} interval {k} ({r.days[k]:.2f}-{r.days[k + 1]:.2f}): rms0 {math.sqrt(max(sse0, 0) / nst):.4f}"
            f" rms1 {math.sqrt(max(sse1, 0) / nst):.4f} at {i1}/{nsub}  LR {lr:.1f}")
        if lr > TURN_LR:
            o[k] = oo
            turns[k] = r.days[k] + (r.days[k + 1] - r.days[k]) * i1 / nsub
            dbg(f"  {r.name}: rope turned end for end in interval {k}, on day {turns[k]:.2f}")
        else:
            o[k] = on
    return o, turns


# ---- pass 2: the damage

def damage(r):
    """RS-4 damage of the final stations' elements, exact up to a series truncation < TRUNC_TOL."""
    nst = len(r.xs)
    dam = np.zeros(nst)
    if r.dm is None or len(r.lo) == 0 or not r.sheaves:
        return dam
    K = len(r.days)
    T = Touch(r)
    try:
        o, turns = orientations(r, T)
    except Exception as exc:  # cannot weigh the surveys: take the rope as never turned
        dbg(f"{r.name}: orientations failed: {exc!r}")
        o, turns = np.zeros(K, dtype=np.int64), {}
    # diameter of each element at each survey
    dm = np.vstack([survey_at(r, k, positions(r, o[k])) for k in range(K)])
    r.dm = dm
    # time bins: one per survey period, split at a turn; each with a survey and an orientation
    first = np.zeros(K, dtype=np.int64)
    bin_k, bin_o = [], []
    for k in range(K):
        first[k] = len(bin_k)
        bin_k.append(k)
        bin_o.append(o[k])
        if k in turns:
            bin_k.append(k)
            bin_o.append(o[k + 1])
    binm = first[r.k]
    for k, td in turns.items():
        binm[(r.k == k) & (r.day >= td)] += 1
    bin_k = np.array(bin_k)
    bin_o = np.array(bin_o)
    r.bin_k, r.bin_o, r.binm = bin_k, bin_o, binm

    b0, b1, b2, b3 = r.b
    v = np.log10(dm)
    v0 = 0.5 * (float(v.min()) + float(v.max()))
    eps = b3 * (v - v0)                            # (K, nst)
    emax = float(np.abs(eps).max())
    for g, members in enumerate(T.groups):
        D = members[0][2]
        c0 = b1 + b3 * (math.log10(D) - v0)
        u0 = reference_u(r.u, c0)
        t = r.u - u0
        B = emax * float(np.abs(t).max()) * LN10
        Q = 1
        while Q < 40 and B ** Q / math.factorial(Q) * math.exp(2.0 * B) >= TRUNC_TOL:
            Q += 1
        if Q >= 40:
            dam += damage_direct(r, members, bin_k, bin_o, binm)
            continue
        W = np.power(10.0, -c0 * t)
        moments = [W]
        for q in range(1, Q):
            moments.append(moments[-1] * t)
        inv_fact = [1.0 / math.factorial(q) for q in range(Q)]
        base = np.power(10.0, -lgN(r.b, D, dm, u0))           # (K, nst): 1/N(S0, D, d)
        for ba, bz, Fs in binned_sums(T.plo[g], T.phi[g], T.P[g], binm, len(bin_k), moments):
            for bi in range(ba, bz):
                k, ob = bin_k[bi], bin_o[bi]
                ek = eps[k] * LN10
                series = np.zeros(nst)
                for j, (_, _, _, w) in enumerate(members):
                    ix = T.idx[g][(j, ob)]
                    acc = Fs[Q - 1][bi - ba, ix] * inv_fact[Q - 1]
                    for q in range(Q - 2, -1, -1):  # Horner in eps*ln10
                        acc = acc * ek + Fs[q][bi - ba, ix] * inv_fact[q]
                    series += w * acc
                dam += base[k] * series
    return dam


def damage_direct(r, members, bin_k, bin_o, binm):
    """Direct sum over movements, stations and sheaves (slow; a fallback)."""
    nst = len(r.xs)
    dam = np.zeros(nst)
    S = np.power(10.0, r.u)
    step = max(1, 2_000_000 // max(1, nst))
    ob_m = bin_o[binm]
    for (p, a, D, w) in members:
        for o in (0, 1):
            hq = r.H - (r.L - a - positions(r, o)) / p
            sel_o = np.nonzero(ob_m == o)[0]
            for i0 in range(0, len(sel_o), step):
                ii = sel_o[i0:i0 + step]
                inside = (r.lo[ii, None] <= hq[None, :]) & (hq[None, :] <= r.hi[ii, None])
                rows = np.nonzero(inside.any(axis=1))[0]
                if len(rows) == 0:
                    continue
                ii = ii[rows]
                d = r.dm[r.k[ii]]
                ln = lgN(r.b, D, d, np.log10(S[ii])[:, None])
                dam += w * np.where(inside[rows], np.power(10.0, -ln), 0.0).sum(axis=0)
    return dam


# ---------------------------------------------------------------------------------------- output

def station_numbers(xs):
    if len(xs) == 0:
        return []
    num = np.rint(xs - 0.5).astype(np.int64) + 1
    if (np.abs(xs - 0.5 - (num - 1)) < 0.02).all() and (num >= 1).all() and len(np.unique(num)) == len(num):
        return num.tolist()
    return list(range(1, len(xs) + 1))


def fmt_values(vals):
    vals = np.asarray(vals, dtype=float)
    vals = np.where(np.isfinite(vals) & (vals > 0), vals, 0.0)
    mx = float(vals.max()) if len(vals) else 0.0
    dec = int(min(60, max(6, 9 - math.floor(math.log10(mx))))) if mx > 0 else 6
    return [f"{x:.{dec}f}" for x in vals]


def csv_field(s):
    if any(ch in s for ch in ',"\n\r'):
        return '"' + s.replace('"', '""') + '"'
    return s


def write_output(path, lines):
    data = ("\n".join(lines) + "\n").encode("utf-8")
    d = os.path.dirname(os.path.abspath(path))
    try:
        fd, tmp = tempfile.mkstemp(prefix=".ropes_", suffix=".tmp", dir=d)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            um = os.umask(0)
            os.umask(um)
            os.chmod(tmp, 0o666 & ~um)
            os.replace(tmp, path)  # replaces a link at `path` itself, never its target
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    except Exception:
        if os.path.islink(path):
            os.unlink(path)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0), 0o666)
        with os.fdopen(fd, "wb") as f:
            f.write(data)


def rope_damage(r):
    try:
        with np.errstate(all="ignore"):
            vals = damage(r)
        if not np.isfinite(vals).all():
            raise FloatingPointError("non-finite damage")
        return vals
    except Exception as exc:  # fall back on the direct sum, the rope taken as never turned
        dbg(f"{r.name}: fast reckoning failed: {exc!r}")
        K = len(r.days)
        r.dm = np.vstack([survey_at(r, k, r.xs) for k in range(K)])
        with np.errstate(all="ignore"):
            vals = damage_direct(r, r.sheaves, np.arange(K), np.zeros(K, dtype=np.int64), r.k)
        return np.where(np.isfinite(vals), vals, 0.0)


def main(argv):
    works, out = argv[1], argv[2]
    lines = ["row,damage"]
    try:
        cranes = read_table(os.path.join(works, "cranes.csv"),
                            ["falls", "upper_block_height_m", "block_mass_t", "reeving_efficiency",
                             "rope_length_m"])
        sheaves = read_table(os.path.join(works, "sheaves.csv"),
                             ["parts", "offset_m", "diameter_mm", "bend_weight"])
        surveys = read_by_crane(os.path.join(works, "surveys.csv"), ["day", "station_m", "diameter_mm"])
        try:
            movs = read_by_crane(os.path.join(works, "movements.csv"),
                                 ["day", "from_height_m", "to_height_m", "hook_load_t"])
        except Exception:
            movs = {}
        sh_by = {k: g for k, g in sheaves.groupby("key", sort=False)}
        seen = set()
        for _, c in cranes.iterrows():
            key = c["key"]
            if key in seen or key == "":
                continue
            seen.add(key)
            name = str(c["crane"]).strip()
            xs = np.zeros(0)
            vals = None
            try:
                r = prepare(c, sh_by.get(key, sheaves.iloc[0:0]), movs.get(key), surveys.get(key))
                xs = r.xs
                vals = rope_damage(r) if r.dm is not None and len(r.lo) else np.zeros(len(xs))
            except Exception as exc:
                dbg(f"{name}: {exc!r}")
                if len(xs) == 0:
                    sv = surveys.get(key)
                    if sv is not None and len(sv["day"]):
                        ok = np.isfinite(sv["day"]) & np.isfinite(sv["station_m"])
                        if ok.any():
                            last = sv["day"][ok].max()
                            xs = np.unique(sv["station_m"][ok & (sv["day"] == last)])
                vals = np.zeros(len(xs))
            if vals is None or len(vals) != len(xs):
                vals = np.zeros(len(xs))
            for num, txt in zip(station_numbers(xs), fmt_values(vals)):
                lines.append(f"{csv_field(f'{name}-{num:03d}')},{txt}")
    finally:
        write_output(out, lines)


if __name__ == "__main__":
    try:
        if len(sys.argv) < 3:
            sys.stderr.write("usage: python3 ropes.py WORKS_DIR OUT_CSV\n")
        else:
            main(sys.argv)
    except BaseException as exc:  # the exit status has to be 0
        try:
            sys.stderr.write(f"ropes.py: {exc!r}\n")
        except Exception:
            pass
    sys.exit(0)
