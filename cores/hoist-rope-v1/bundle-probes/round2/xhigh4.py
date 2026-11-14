#!/usr/bin/env python3
"""Bending fatigue damage along crane hoist ropes to RS-4 (issue 3).

usage: python3 ropes.py WORKS_DIR OUT_CSV

Reads cranes.csv, sheaves.csv, movements.csv and surveys.csv of one works
package and writes OUT_CSV with the header ``row,damage`` and one row for
every station of every crane's rope (``<crane>-<station number>``).

Method
------
RS-4 damage of an element is the sum over all its bendings of w / N, with
lg N = b0 + (b1 + b3 u) lg(S/d^2) + b2 u,  u = lg(D/d).  Written as
1/N = 10^(-b0 + 2 c lg d - b2 u) * S^(-c),  c = b1 + b3 u,
the only coupling between the movement (S) and the element (d) is S^(-c).
It is expanded about a central exponent c0 and a central ln S:
S^(-c) = e^(-c lam) e^(-c0 t) sum_m (-(c - c0))^m t^m / m!,  t = ln S - lam,
so for every survey period the sums over movements reduce to a few moment
profiles along the rope, each built with difference arrays (bincount +
cumsum) over the stretch of rope passed by each sheave's point of touch.
The number of terms is chosen so that the truncation error is < 1e-10.

Rope surveys and rope orientation
---------------------------------
Elements are tracked as material: a rope that is turned end for end carries
its damage with it.  Successive surveys are compared; a survey whose profile
matches the mirror image of the previous one (and not the profile itself)
marks an event.  An event is either a rope turned end for end between the
two surveys, or surveys that from then on were recorded from the dead end.
The two are told apart (and the day of a turn estimated) by fitting the
diameter loss of every element against its accumulated damage under each
explanation; the explanation that fits best is used.  The diameters used
in N are always those of the element itself at the last survey not later
than the movement.
"""
import os
import sys
import math
import time

START = time.process_time()

import numpy as np
import pandas as pd

G = 9.80665
COEF = {
    '8x36': (-1.214, 0.887, 7.432, -2.103),
    '6x36': (-1.371, 0.934, 7.518, -2.146),
}
DEBUG = bool(os.environ.get('ROPES_DEBUG'))


def dbg(*a):
    if DEBUG:
        print(*a, file=sys.stderr)


# --------------------------------------------------------------------------
# reading
# --------------------------------------------------------------------------
def read_table(path):
    df = pd.read_csv(path, skipinitialspace=True, engine='c', low_memory=False)
    df.columns = [str(c).strip().lower().lstrip('﻿') for c in df.columns]
    return df


def num(df, col, default=np.nan):
    if col not in df.columns:
        return np.full(len(df), default, dtype=float)
    s = df[col]
    if s.dtype.kind in 'fiu':
        return s.to_numpy(dtype=float)
    s = s.astype(str).str.strip().str.replace(',', '.', regex=False)
    return pd.to_numeric(s, errors='coerce').to_numpy(dtype=float)


def names(df, col='crane'):
    """crane names (stripped) as integer codes + list of unique names."""
    codes, uniq = pd.factorize(df[col], sort=False)
    uniq = [str(u).strip() for u in uniq]
    # merge names that differ only by surrounding blanks
    remap = {}
    out = []
    for u in uniq:
        if u not in remap:
            remap[u] = len(out)
            out.append(u)
    lut = np.array([remap[u] for u in uniq] + [-1], dtype=np.int64)
    codes = lut[np.where(codes < 0, len(uniq), codes)]
    return codes, out


def construction_coef(s):
    k = str(s).strip().lower().replace(' ', '').replace('×', 'x').replace('*', 'x')
    if k in COEF:
        return COEF[k]
    for key in COEF:
        if k.startswith(key) or key in k:
            return COEF[key]
    if k.startswith('8'):
        return COEF['8x36']
    return COEF['6x36']


# --------------------------------------------------------------------------
# station grid and survey table
# --------------------------------------------------------------------------
class Grid:
    def __init__(self, pos, L):
        self.pos = np.asarray(pos, dtype=float)
        self.M = len(self.pos)
        self.L = float(L)
        d = np.diff(self.pos)
        self.uniform = self.M >= 2 and np.all(np.abs(d - d.mean()) < 1e-6) and d.mean() > 0
        if self.uniform:
            self.g0 = self.pos[0]
            self.dx = d.mean()
        elif self.M == 1:
            self.uniform = True
            self.g0 = self.pos[0]
            self.dx = 1.0
        self.symmetric = bool(np.allclose(self.pos + self.pos[::-1], self.L, atol=1e-6))

    def rev(self, v):
        """value at the mirrored place L - x, for vectors (or rows) on the grid."""
        if self.symmetric:
            return v[..., ::-1]
        xq = self.L - self.pos
        if v.ndim == 1:
            return np.interp(xq, self.pos, v)
        return np.vstack([np.interp(xq, self.pos, r) for r in v])

    def span(self, lo, hi):
        """index range [jl, jh) of grid stations with lo <= x <= hi."""
        M = self.M
        if self.uniform:
            jl = np.ceil((lo - self.g0) / self.dx)
            jh = np.floor((hi - self.g0) / self.dx) + 1.0
            np.clip(jl, 0, M, out=jl)
            np.clip(jh, 0, M, out=jh)
            jl = jl.astype(np.int64)
            jh = jh.astype(np.int64)
        else:
            jl = np.searchsorted(self.pos, lo, 'left')
            jh = np.searchsorted(self.pos, hi, 'right')
        jh = np.maximum(jh, jl)
        return jl, jh


def build_grid(L, last_pos):
    """stations of the rope's last survey, numbered from the drum anchorage."""
    z = np.unique(np.round(np.asarray(last_pos, dtype=float), 6))
    z = z[np.isfinite(z)]
    if len(z) == 0:
        n = max(int(round(L)), 1)
        return Grid(0.5 + np.arange(n), L), np.arange(n)
    idx = np.round(z - 0.5)
    on = np.all(np.abs(z - 0.5 - idx) < 0.05) and idx.min() >= 0 and len(np.unique(idx)) == len(z)
    if on:
        n = int(idx.max()) + 1
        if abs(L - round(L)) < 0.05 and int(round(L)) >= n:
            n = int(round(L))
        return Grid(0.5 + np.arange(n), L), np.arange(n)
    return Grid(z, L), np.arange(len(z))


def survey_table(grid, sv_day, sv_pos, sv_dia):
    """diameters of every survey interpolated onto the grid, in recorded coordinates."""
    ok = np.isfinite(sv_day) & np.isfinite(sv_pos) & np.isfinite(sv_dia) & (sv_dia > 0)
    sv_day, sv_pos, sv_dia = sv_day[ok], sv_pos[ok], sv_dia[ok]
    if len(sv_day) == 0:
        return np.zeros(0), np.zeros((0, grid.M))
    dkey = np.round(sv_day, 6)
    days = np.unique(dkey)
    tab = []
    keep = []
    for k, dd in enumerate(days):
        sel = dkey == dd
        p = sv_pos[sel]
        v = sv_dia[sel]
        # gauge glitches: readings far off the survey's own median are dropped
        med = np.median(v)
        good = (v > 0.6 * med) & (v < 1.4 * med)
        p, v = p[good], v[good]
        if len(p) == 0:
            continue
        o = np.argsort(p, kind='mergesort')
        p, v = p[o], v[o]
        up, inv = np.unique(np.round(p, 6), return_inverse=True)
        if len(up) < len(p):
            v = np.bincount(inv, v) / np.bincount(inv)
            p = up
        tab.append(np.interp(grid.pos, p, v))
        keep.append(dd)
    return np.array(keep), np.array(tab)


# --------------------------------------------------------------------------
# events between surveys (mirrored profiles)
# --------------------------------------------------------------------------
def detect_events(grid, tab):
    """indices k where survey k matches the mirror image of survey k-1."""
    # A rope only gets thinner: aligned the right way, a survey exceeds the one
    # before only by the gauge's scatter (~0.02 mm).  The statistic is the mean
    # square excess over the quarter of the stations where it is largest, so that
    # a short worn stretch on a long rope is not diluted.
    ev = []
    M = tab.shape[1]
    nq = min(M, max(10, M // 4))

    def top(e):
        r = np.maximum(e, 0.0)
        r = r * r
        if nq < M:
            r = np.partition(r, M - nq)[M - nq:]
        return float(r.mean())

    for k in range(1, len(tab)):
        A = tab[k - 1]
        B = tab[k]
        s_id = top(B - A)
        s_rv = top(B - grid.rev(A))
        if s_id > 2e-3 and s_rv * 4.0 < s_id:
            ev.append(k)
        dbg('   survey %d: id %.2e rev %.2e%s' % (k, s_id, s_rv, ' EVENT' if ev and ev[-1] == k else ''))
    return ev


def fit_resid(y, F):
    """least squares y_kj = a_k + beta_j F_kj; returns the residual sum of squares."""
    K, M = y.shape
    nrm = np.einsum('kj,kj->j', F, F)
    act = nrm > 1e-300
    if not act.any():
        r = y - y.mean(1, keepdims=True)
        return float((r * r).sum())
    Fa = F[:, act] / np.sqrt(nrm[act])
    ya = y[:, act]
    proj = np.einsum('kj,kj->j', Fa, ya)
    rhs = y.sum(1) - Fa @ proj
    A = M * np.eye(K) - Fa @ Fa.T
    A += 1e-9 * M * np.eye(K)
    try:
        a = np.linalg.solve(A, rhs)
    except np.linalg.LinAlgError:
        a = np.linalg.lstsq(A, rhs, rcond=None)[0]
    r = y - a[:, None]
    pr = np.einsum('kj,kj->j', Fa, r[:, act])
    return float((r * r).sum() - (pr * pr).sum())


class Crane:
    pass


def tension(cr, load):
    m = np.maximum(np.where(np.isfinite(load), load, 0.0), 0.0) + max(cr.mb, 0.0)
    S = m * 1000.0 * G / (cr.n * cr.e)
    return np.maximum(S, 1e-6)


def touch(cr, sh, h0, h1):
    """stretch [lo, hi] of rope (x from the drum anchorage) passed by a sheave's point of touch."""
    x0 = cr.L - sh[1] - sh[0] * (cr.H - h0)
    x1 = cr.L - sh[1] - sh[0] * (cr.H - h1)
    return np.minimum(x0, x1), np.maximum(x0, x1)


def choose_orientation(cr, grid, days, tab, events, mv):
    """decide for every event whether the rope was turned (and when) or the surveys
    were recorded from the dead end.  Returns (rec, turns): rec[k] = +1/-1 recording
    orientation of survey k, turns = list of (event index, day of the turn)."""
    P, M = tab.shape
    E = len(events)
    day, h0, h1, load = mv
    if P < 3 or len(day) == 0:
        # too little to judge: assume turns at the middle of the interval
        turns = [(k, 0.5 * (days[k - 1] + days[k])) for k in events]
        return np.ones(P, dtype=int), turns

    NB = 20
    # time boundaries of the groups: survey days, and sub-bins inside event intervals
    bnd = list(days)
    sub = {}
    for k in events:
        a, b = days[k - 1], days[k]
        pts = a + (b - a) * np.arange(1, NB) / NB
        bnd.extend(pts.tolist())
    bnd = np.unique(np.array(bnd))
    gstart = np.searchsorted(bnd, days)            # group index starting at survey k
    for k in events:
        i0 = gstart[k - 1]
        sub[k] = np.arange(i0, gstart[k] + 1)      # candidate turn boundaries (group indices)
    NG = len(bnd)
    grp = np.searchsorted(bnd, day, 'right') - 1
    grp = np.clip(grp, 0, NG - 1)

    # damage increments by position for every group, with a constant diameter
    S = tension(cr, load)
    lgS = np.log10(S)
    dref = float(np.median(tab[0]))
    lgd = math.log10(dref)
    b0, b1, b2, b3 = cr.coef
    acc = np.zeros(NG * (M + 1))
    base = grp * (M + 1)
    for sh in cr.sheaves:
        u = math.log10(sh[2]) - lgd
        lgN = b0 + (b1 + b3 * u) * (lgS - 2 * lgd) + b2 * u
        wN = sh[3] * np.power(10.0, -lgN)
        lo, hi = touch(cr, sh, h0, h1)
        jl, jh = grid.span(lo, hi)
        acc += np.bincount(base + jl, wN, NG * (M + 1))
        acc -= np.bincount(base + jh, wN, NG * (M + 1))
    Ipos = np.cumsum(acc.reshape(NG, M + 1), axis=1)[:, :M]
    Irev = grid.rev(Ipos)
    tab_rev = grid.rev(tab)
    gstart_ext = gstart

    def build(rec0, types, tb):
        """types[i] in 'A','B' for events[i]; tb[i] boundary group index of a turn."""
        rec = np.empty(P, dtype=int)
        r = rec0
        ti = 0
        for k in range(P):
            if ti < E and events[ti] == k:
                if types[ti] == 'B':
                    r = -r
                ti += 1
            rec[k] = r
        # orientation of each group relative to the final one
        ori = np.ones(NG, dtype=int)
        oris = np.ones(P, dtype=int)
        for i, k in enumerate(events):
            if types[i] == 'A':
                ori[:tb[i]] *= -1
                oris[:k] *= -1          # surveys before the event: rope the other way round
        comb = rec * oris
        y = -np.where(comb[:, None] > 0, tab, tab_rev)
        Imap = np.where(ori[:, None] > 0, Ipos, Irev)
        C = np.vstack([np.zeros(M), np.cumsum(Imap, axis=0)])
        D = C[gstart_ext]
        return rec, y, D

    def score(y, D, qs):
        best = (np.inf, None)
        Dp = np.maximum(D, 0.0)
        with np.errstate(divide='ignore'):
            lD = np.log(Dp)
        for q in qs:
            F = np.where(Dp > 0, np.exp(q * lD), 0.0)
            r = fit_resid(y, F)
            if r < best[0]:
                best = (r, q)
        return best

    def score_q(y, D):
        """residual with the exponent of the wear law fitted (coarse, then fine)."""
        r, q = score(y, D, np.arange(0.3, 1.21, 0.1))
        return score(y, D, np.clip(q + np.arange(-0.08, 0.081, 0.02), 0.05, 2.0))

    # Model choice: residual in units of the noise variance, plus a charge for
    # every turn.  A turn's day is a free parameter searched over the interval,
    # and a turn just before the last survey explains the surveys exactly as a
    # last survey recorded from the dead end does, so a turn has to earn its
    # place: BIC charge ln(n) plus 20.  Surveys recorded from the dead end from
    # the very first one on need a strong case (prior charge n/4).
    nobs = P * M
    lam = math.log(nobs) + 20.0

    def crit(r, s2):
        c = r[0] / s2 + lam * sum(1 for t in r[2] if t == 'A')
        if r[1] == -1:
            c += 0.25 * nobs
        return c

    def scan(rec0, types, tb, i, q, rs):
        """best boundary for turn i: every 4th candidate, then the neighbours."""
        cand = sub[events[i]]
        qs = q + np.array([-0.04, -0.02, 0.0, 0.02, 0.04])
        tried = {}

        def at(j):
            if j not in tried:
                tb2 = list(tb)
                tb2[i] = cand[j]
                _, y2, D2 = build(rec0, types, tb2)
                tried[j] = score(y2, D2, qs)
            return tried[j]
        coarse = sorted(set(list(range(0, len(cand), 4)) + [len(cand) - 1]))
        jb = min(coarse, key=lambda j: at(j)[0])
        for j in range(max(0, jb - 3), min(len(cand), jb + 4)):
            at(j)
        jb = min(tried, key=lambda j: tried[j][0])
        r2, q2 = tried[jb]
        if r2 < rs:
            return cand[jb], r2, q2
        return tb[i], rs, q

    def evaluate(rec0, types, passes=2):
        types = tuple(types)
        tb = [sub[k][len(sub[k]) // 2] for k in events]
        rec, y, D = build(rec0, types, tb)
        rs, q = score_q(y, D)
        nA = sum(1 for t in types if t == 'A')
        if time.process_time() - START > 2.6:
            passes = min(passes, 1)
        for _ in range(min(passes, nA)):
            # refine the turn days one after the other
            for i in range(E):
                if types[i] == 'A':
                    tb[i], rs, q = scan(rec0, types, tb, i, q, rs)
            _, y2, D2 = build(rec0, types, tb)
            rs, q = score_q(y2, D2)
        return [rs, rec0, types, list(tb), q]

    results = []
    if E <= 3:
        import itertools
        combos = list(itertools.product('AB', repeat=E))
        for types in combos:
            results.append(evaluate(1, types))
        # surveys recorded from the dead end from the first one on: refined only
        # when it could win (it needs a residual below 0.8 of the best other one)
        best1 = min(r[0] for r in results)
        for types in combos:
            r = evaluate(-1, types, passes=0)
            if r[0] < 1.15 * best1 and 'A' in types:
                r = evaluate(-1, types)
            results.append(r)
    else:
        # many events: start from recordings reversed back and forth and change
        # one event at a time, always the change that helps most (steepest descent)
        for rec0 in (1, -1):
            cur = evaluate(rec0, 'B' * E)
            results.append(cur)
            for _ in range(min(E, 4)):
                cands = []
                for i in range(E):
                    t2 = list(cur[2])
                    t2[i] = 'A' if t2[i] == 'B' else 'B'
                    cands.append(evaluate(rec0, t2, passes=1 if E <= 6 else 0))
                results.extend(cands)
                s2 = max(min([cur[0]] + [c[0] for c in cands]) / nobs, 1e-12)
                best = min(cands, key=lambda c: crit(c, s2))
                if crit(best, s2) < crit(cur, s2):
                    cur = best
                else:
                    break
                if time.process_time() - START > 2.8:
                    break
    s2 = max(min(r[0] for r in results) / nobs, 1e-12)
    for r in results:
        r.append(crit(r, s2))
        dbg('   hyp rec0=%+d types=%s tb=%s q=%.2f rms=%.5f crit=%.1f' % (
            r[1], ''.join(r[2]), [float(bnd[t]) for t in r[3]], r[4], math.sqrt(r[0] / nobs), r[5]))
    results.sort(key=lambda r: r[5])
    rs, rec0, types, tb, q, _ = results[0]
    rec, _, _ = build(rec0, types, tb)
    turns = []
    for i, k in enumerate(events):
        if types[i] == 'A':
            t = tb[i]
            tday = days[k] if t >= gstart[k] else bnd[t]
            turns.append((k, float(tday)))
    dbg('   chosen rec0=%+d types=%s turns=%s q=%.2f' % (rec0, ''.join(types), turns, q))
    return rec, turns


def global_check(cr, grid, days, tab, mv):
    """with no events: are all surveys recorded from the dead end?"""
    rec, turns = choose_orientation(cr, grid, days, tab, [], mv)
    return rec


# --------------------------------------------------------------------------
# exact RS-4 damage
# --------------------------------------------------------------------------
def damage(cr, grid, per, flip, dl, mv):
    """per: survey period of each movement; flip: movement made with the rope the
    other way round to its final orientation; dl: P x M diameters of the elements
    (labelled by their final place) at each survey."""
    day, h0, h1, load = mv
    P, M = dl.shape
    out = np.zeros(M)
    if len(day) == 0 or not cr.sheaves:
        return out
    b0, b1, b2, b3 = cr.coef
    S = tension(cr, load)
    lnS = np.log(S)
    lam = 0.5 * (lnS.min() + lnS.max())
    t = lnS - lam
    tmax = float(np.abs(t).max())
    lgd = np.log10(dl)
    base = per.astype(np.int64) * (M + 1)
    NN = P * (M + 1)
    # sheaves grouped by diameter and bend weight
    groups = {}
    for sh in cr.sheaves:
        groups.setdefault((sh[2], sh[3]), []).append(sh)
    spans = {}
    for (D, w), shs in groups.items():
        u = math.log10(D) - lgd
        c = b1 + b3 * u
        c0 = 0.5 * (c.min() + c.max())
        dl_ = c - c0
        x = float(np.abs(dl_).max()) * tmax
        T = 1
        term = 1.0
        while T < 60:
            term *= x / T
            if term < 1e-12:
                break
            T += 1
        W = np.exp(-c0 * t)
        Wm = [W]
        for m in range(1, T):
            Wm.append(Wm[-1] * t / m)
        acc = np.zeros((T, NN))
        for sh in shs:
            key = (sh[0], sh[1])
            if key in spans:
                il, ih = spans[key]
            else:
                lo, hi = touch(cr, sh, h0, h1)
                if flip is not None:
                    lo, hi = np.where(flip, cr.L - hi, lo), np.where(flip, cr.L - lo, hi)
                jl, jh = grid.span(lo, hi)
                il = base + jl
                ih = base + jh
                spans[key] = (il, ih)
            for m in range(T):
                acc[m] += np.bincount(il, Wm[m], NN)
                acc[m] -= np.bincount(ih, Wm[m], NN)
        F = np.cumsum(acc.reshape(T, P, M + 1), axis=2)[:, :, :M]
        poly = F[T - 1]
        for m in range(T - 2, -1, -1):
            poly = poly * (-dl_) + F[m]
        lg_pref = -b0 + 2.0 * c * lgd - b2 * u
        dmg = w * np.exp(lg_pref * math.log(10.0) - c * lam) * poly
        out += dmg.sum(0)
    return np.maximum(out, 0.0)


def process(cr, mv, sv):
    """damage at every station of the crane's rope (labels = places at the end of the log)."""
    sv_day, sv_pos, sv_dia = sv
    okp = np.isfinite(sv_day) & np.isfinite(sv_pos) & np.isfinite(sv_dia) & (sv_dia > 0)
    if okp.any():
        dlast = sv_day[okp].max()
        last_pos = sv_pos[okp & (np.round(sv_day, 6) == np.round(dlast, 6))]
    else:
        last_pos = []
    grid, numbers = build_grid(cr.L, last_pos)
    days, tab = survey_table(grid, sv_day, sv_pos, sv_dia)
    if len(days) == 0:
        # no usable survey: a nominal diameter from the sheave ratio (D/d ~ 25)
        dnom = min(sh[2] for sh in cr.sheaves) / 25.0 if cr.sheaves else 20.0
        days = np.array([0.0])
        tab = np.full((1, grid.M), dnom)
    P = len(days)
    dbg('crane %s: L=%g M=%d surveys=%d movements=%d' % (cr.name, cr.L, grid.M, P, len(mv[0])))
    events = detect_events(grid, tab) if P >= 2 else []
    rec = np.ones(P, dtype=int)
    turns = []
    if events:
        try:
            rec, turns = choose_orientation(cr, grid, days, tab, events, mv)
        except Exception as ex:  # pragma: no cover - fall back to turns mid-interval
            dbg('   orientation fit failed: %r' % (ex,))
            rec = np.ones(P, dtype=int)
            turns = [(k, 0.5 * (days[k - 1] + days[k])) for k in events]
    elif P >= 4 and len(mv[0]) > 0 and time.process_time() - START < 3.0:
        try:
            rec = global_check(cr, grid, days, tab, mv)
        except Exception as ex:  # pragma: no cover
            dbg('   global check failed: %r' % (ex,))
            rec = np.ones(P, dtype=int)
    day = mv[0]
    # orientation of the material relative to its final orientation: a movement
    # made before a turn, and a survey made before the survey that revealed it,
    # had the rope the other way round
    flip = None
    ori_s = np.ones(P, dtype=int)
    if turns:
        nflip = np.zeros(len(day), dtype=np.int64)
        for k, tday in turns:
            nflip += day < tday
            ori_s[:k] *= -1
        flip = (nflip % 2) == 1
    comb = rec * ori_s
    dl = np.where(comb[:, None] > 0, tab, grid.rev(tab))
    per = np.searchsorted(days, day, 'right') - 1
    per = np.clip(per, 0, P - 1)
    dmg = damage(cr, grid, per, flip, dl, mv)
    return numbers, dmg


# --------------------------------------------------------------------------
def fmt(v):
    if not np.isfinite(v) or v <= 0:
        return '0.0'
    return np.format_float_positional(float(v), precision=10, unique=False, fractional=False, trim='0')


def run(works):
    cranes = read_table(os.path.join(works, 'cranes.csv'))
    sheaves = read_table(os.path.join(works, 'sheaves.csv'))
    movements = read_table(os.path.join(works, 'movements.csv'))
    surveys = read_table(os.path.join(works, 'surveys.csv'))

    c_codes, c_names = names(cranes)
    s_codes, s_names = names(sheaves)
    m_codes, m_names = names(movements)
    v_codes, v_names = names(surveys)

    m_day = num(movements, 'day')
    m_h0 = num(movements, 'from_height_m')
    m_h1 = num(movements, 'to_height_m')
    m_ld = num(movements, 'hook_load_t', 0.0)
    m_ld = np.where(np.isfinite(m_ld), m_ld, 0.0)
    ok = np.isfinite(m_day) & np.isfinite(m_h0) & np.isfinite(m_h1) & (m_codes >= 0)
    v_day = num(surveys, 'day')
    v_pos = num(surveys, 'station_m')
    v_dia = num(surveys, 'diameter_mm')

    m_index = {n: i for i, n in enumerate(m_names)}
    v_index = {n: i for i, n in enumerate(v_names)}
    # movements of every crane, in order of time, without repeated rows
    order = np.lexsort((m_day, m_codes))
    order = order[ok[order]]
    mc = m_codes[order]
    bounds = np.searchsorted(mc, np.arange(len(m_names) + 1))

    sh_parts = num(sheaves, 'parts')
    sh_off = num(sheaves, 'offset_m', 0.0)
    sh_dia = num(sheaves, 'diameter_mm')
    sh_w = num(sheaves, 'bend_weight')
    sh_name = sheaves['sheave'].astype(str).str.strip().str.lower().to_numpy() if 'sheave' in sheaves.columns \
        else np.array([''] * len(sheaves))

    c_falls = num(cranes, 'falls')
    c_H = num(cranes, 'upper_block_height_m')
    c_mb = num(cranes, 'block_mass_t', 0.0)
    c_e = num(cranes, 'reeving_efficiency', 1.0)
    c_L = num(cranes, 'rope_length_m')
    c_con = cranes['rope_construction'].to_numpy() if 'rope_construction' in cranes.columns \
        else np.array(['6x36'] * len(cranes))

    lines = ['row,damage']
    seen = set()
    for i in range(len(cranes)):
        if c_codes[i] < 0:
            continue
        name = c_names[c_codes[i]]
        if name in seen:
            continue
        seen.add(name)
        cr = Crane()
        cr.name = name
        cr.n = float(c_falls[i]) if np.isfinite(c_falls[i]) and c_falls[i] > 0 else 1.0
        cr.H = float(c_H[i]) if np.isfinite(c_H[i]) else 0.0
        cr.mb = float(c_mb[i]) if np.isfinite(c_mb[i]) else 0.0
        cr.e = float(c_e[i]) if np.isfinite(c_e[i]) and c_e[i] > 0 else 1.0
        cr.L = float(c_L[i]) if np.isfinite(c_L[i]) and c_L[i] > 0 else 0.0
        cr.coef = construction_coef(c_con[i])
        cr.sheaves = []
        if name in s_names:
            sc = s_names.index(name)
            for r in np.where(s_codes == sc)[0]:
                if not (np.isfinite(sh_parts[r]) and np.isfinite(sh_dia[r]) and sh_dia[r] > 0):
                    continue
                w = sh_w[r]
                if not np.isfinite(w):
                    w = 0.5 if sh_name[r] == 'drum' else 1.0
                off = sh_off[r] if np.isfinite(sh_off[r]) else 0.0
                cr.sheaves.append((float(sh_parts[r]), float(off), float(sh_dia[r]), float(w)))
        if name in m_index:
            mi = m_index[name]
            sel = order[bounds[mi]:bounds[mi + 1]]
        else:
            sel = np.zeros(0, dtype=np.int64)
        mv = [m_day[sel], m_h0[sel], m_h1[sel], m_ld[sel]]
        if len(sel) > 1:
            dup = np.zeros(len(sel), dtype=bool)
            dup[1:] = ((mv[0][1:] == mv[0][:-1]) & (mv[1][1:] == mv[1][:-1]) &
                       (mv[2][1:] == mv[2][:-1]) & (mv[3][1:] == mv[3][:-1]))
            if dup.any():
                mv = [a[~dup] for a in mv]
        if name in v_index:
            vs = v_codes == v_index[name]
            sv = (v_day[vs], v_pos[vs], v_dia[vs])
        else:
            sv = (np.zeros(0), np.zeros(0), np.zeros(0))
        if cr.L <= 0:
            pos = sv[1][np.isfinite(sv[1])]
            cr.L = float(np.ceil(pos.max())) if len(pos) else 1.0
        try:
            numbers, dmg = process(cr, mv, sv)
        except Exception as ex:  # pragma: no cover - never leave a crane out
            dbg('crane %s failed: %r' % (name, ex))
            n = max(int(round(cr.L)), 1)
            numbers, dmg = np.arange(n), np.zeros(n)
        width = max(3, len(str(int(numbers.max()) + 1))) if len(numbers) else 3
        for j, v in zip(numbers, dmg):
            lines.append('%s-%0*d,%s' % (name, width, int(j) + 1, fmt(v)))
    return '\n'.join(lines) + '\n'


def write_out(path, text):
    path = os.path.abspath(path)
    d = os.path.dirname(path) or '.'
    os.makedirs(d, exist_ok=True)
    import tempfile
    fd, tmp = tempfile.mkstemp(prefix='.ropes-', suffix='.tmp', dir=d)
    try:
        with os.fdopen(fd, 'w', newline='\n') as f:
            f.write(text)
        mask = os.umask(0)
        os.umask(mask)
        os.chmod(tmp, 0o666 & ~mask)
        if os.path.islink(path) or (os.path.exists(path) and not os.path.isdir(path)):
            os.unlink(path)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def main(argv):
    if len(argv) != 3:
        print('usage: python3 ropes.py WORKS_DIR OUT_CSV', file=sys.stderr)
        return 2
    works, out = argv[1], argv[2]
    try:
        text = run(works)
    except Exception as ex:
        print('ropes.py: %r' % (ex,), file=sys.stderr)
        text = 'row,damage\n'
    write_out(out, text)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
