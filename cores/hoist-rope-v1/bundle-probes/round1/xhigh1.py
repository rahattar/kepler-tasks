#!/usr/bin/env python3
"""RS-4 bending fatigue damage along crane hoist ropes, for one works package.

usage: python3 ropes.py WORKS_DIR OUT_CSV

For every crane the damage of the rope element lying at each station of the
rope's last survey is reckoned (RS-4 sections 1-5) from the movement log, the
reeving and the surveys.

The program keeps track of the rope as a piece of material, not as places on
the crane:

* Survey sheets are put into one frame of rope elements by matching each
  sheet's diameter profile to its neighbours, forwards and mirrored.  A sheet
  that was written from the wrong end shows up as a mirrored profile.
* Whether the rope itself lay the other way round on the crane (turned end
  for end) is told from where the wear between two surveys fell: wear follows
  the bending damage of the crane positions the elements lay at.
* Each movement uses the diameter of the element itself from the last survey
  not later than the movement.
"""
import os
import sys

for _v in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ.setdefault(_v, '1')

import math
import numpy as np
import pandas as pd

G = 9.80665
COEF = {
    '8x36': (-1.214, 0.887, 7.432, -2.103),
    '6x36': (-1.371, 0.934, 7.518, -2.146),
}
LN10 = math.log(10.0)


# --------------------------------------------------------------------------
# reading
# --------------------------------------------------------------------------

def _read(path, cols):
    df = pd.read_csv(path, skipinitialspace=True)
    df.columns = [str(c).strip().lower() for c in df.columns]
    for c in cols:
        if c not in df.columns:
            raise ValueError('%s: column %s missing' % (path, c))
    if 'crane' in df.columns:
        df['crane'] = df['crane'].astype(str).str.strip()
    return df


def _num(s):
    return pd.to_numeric(s, errors='coerce').to_numpy(dtype=float)


def load_package(wd):
    cranes = _read(os.path.join(wd, 'cranes.csv'),
                   ['crane', 'falls', 'upper_block_height_m', 'block_mass_t',
                    'reeving_efficiency', 'rope_construction', 'rope_length_m'])
    sheaves = _read(os.path.join(wd, 'sheaves.csv'),
                    ['crane', 'parts', 'offset_m', 'diameter_mm', 'bend_weight'])
    path = os.path.join(wd, 'movements.csv')
    head = pd.read_csv(path, nrows=0, skipinitialspace=True)
    ccol = [c for c in head.columns if str(c).strip().lower() == 'crane']
    mv = pd.read_csv(path, skipinitialspace=True, engine='c', low_memory=False,
                     dtype={ccol[0]: 'category'} if ccol else None)
    mv.columns = [str(c).strip().lower() for c in mv.columns]
    if isinstance(mv['crane'].dtype, pd.CategoricalDtype):
        cats = [str(c).strip() for c in mv['crane'].cat.categories]
        if len(set(cats)) == len(cats):
            mv['crane'] = mv['crane'].cat.rename_categories(cats)
        else:
            mv['crane'] = mv['crane'].astype(str).str.strip()
    else:
        mv['crane'] = mv['crane'].astype(str).str.strip()
    surveys = _read(os.path.join(wd, 'surveys.csv'),
                    ['crane', 'day', 'station_m', 'diameter_mm'])
    return cranes, sheaves, mv, surveys


# --------------------------------------------------------------------------
# survey sheets
# --------------------------------------------------------------------------

def survey_table(sv, L):
    """Return (days, grid, P) with P[k] the diameters of sheet k on the grid
    of station places 0.5, 1.5, ... (index order as the sheet runs)."""
    day = _num(sv['day'])
    st = _num(sv['station_m'])
    dia = _num(sv['diameter_mm'])
    ok = np.isfinite(day) & np.isfinite(st) & np.isfinite(dia) & (dia > 0)
    day, st, dia = day[ok], st[ok], dia[ok]
    days = np.unique(day)
    if len(days) == 0:
        return None
    nL = int(round(L)) if np.isfinite(L) and L > 0.5 else 0
    # the stations of the last sheet decide the grid
    last = st[day == days[-1]]
    n_last = len(np.unique(np.round(last, 3)))
    nst = nL if nL > 0 else n_last
    if nL > 0 and abs(n_last - nL) > max(2, 0.02 * nL):
        nst = n_last
    grid = np.arange(nst) + 0.5
    P = np.full((len(days), nst), np.nan)
    for k, dd in enumerate(days):
        sel = day == dd
        s, d = st[sel], dia[sel]
        o = np.argsort(s, kind='stable')
        s, d = s[o], d[o]
        # collapse repeated stations
        us, inv = np.unique(np.round(s, 3), return_inverse=True)
        dm = np.bincount(inv, d) / np.bincount(inv)
        if len(us) == nst:
            P[k] = dm                       # one reading a station: by order
        else:
            idx = np.clip(np.round(us - 0.5).astype(int), 0, nst - 1)
            acc = np.bincount(idx, dm, nst)
            cnt = np.bincount(idx, None, nst)
            row = np.where(cnt > 0, acc / np.maximum(cnt, 1), np.nan)
            P[k] = row
        if np.isnan(P[k]).any():
            r = P[k]
            good = ~np.isnan(r)
            if good.any():
                P[k] = np.interp(np.arange(nst), np.nonzero(good)[0], r[good])
            else:
                P[k] = np.nan
    # sheets with nothing usable take their neighbour's values
    bad = np.isnan(P).all(1)
    if bad.all():
        return None
    for k in range(len(days)):
        if bad[k]:
            j = np.nonzero(~bad)[0]
            P[k] = P[j[np.argmin(np.abs(j - k))]]
    return days, grid, P


# --------------------------------------------------------------------------
# damage
# --------------------------------------------------------------------------

class Crane:
    pass


def crane_setup(c, sh, mv):
    """Gather the arrays of one crane.  Movements are put in order of time."""
    K = Crane()
    K.name = c['crane']
    K.n = float(c['falls'])
    K.H = float(c['upper_block_height_m'])
    K.mb = float(c['block_mass_t'])
    K.e = float(c['reeving_efficiency'])
    K.L = float(c['rope_length_m'])
    con = str(c['rope_construction']).strip().lower().replace(' ', '')
    if con not in COEF:
        con = con.replace('×', 'x')
    K.coef = COEF.get(con, COEF['8x36'])
    rows = []
    for _, r in sh.iterrows():
        p, a, D, w = (float(r['parts']), float(r['offset_m']),
                      float(r['diameter_mm']), float(r['bend_weight']))
        if np.isfinite(p) and np.isfinite(a) and np.isfinite(D) and D > 0 \
                and np.isfinite(w) and w != 0:
            rows.append((p, a, D, w))
    K.sheaves = rows
    day = _num(mv['day'])
    h1 = _num(mv['from_height_m'])
    h2 = _num(mv['to_height_m'])
    ld = _num(mv['hook_load_t'])
    ok = np.isfinite(day) & np.isfinite(h1) & np.isfinite(h2) & np.isfinite(ld)
    day, h1, h2, ld = day[ok], h1[ok], h2[ok], ld[ok]
    if len(day) > 1 and np.any(np.diff(day) < 0):
        o = np.argsort(day, kind='stable')
        day, h1, h2, ld = day[o], h1[o], h2[o], ld[o]
    K.day, K.h1, K.h2 = day, h1, h2
    S = (np.maximum(ld, 0.0) + K.mb) * 1000.0 * G / (K.n * K.e)
    S = np.maximum(S, 1e-6)
    K.u = np.log10(S)
    return K


def moments(K, piece, npc, grid, J, v0, u0=None):
    """Sums over the movements that pass each station, per piece of time.

    For each sheave diameter D a list of arrays M[j] (npc x nst):
        M[j][p, i] = sum_m w 10^(-B0 t_m) t_m^j
    over movements m of piece p whose sheave touch point passes station i,
    t = lg S - u0, B0 = b1 + b3 (lg D - v0)."""
    b0, b1, b2, b3 = K.coef
    nst = len(grid)
    nb = nst + 1
    size = npc * nb
    if u0 is None:
        u0 = crane_u0(K)
    t = K.u - u0
    uniform = nst > 0 and np.allclose(grid, np.arange(nst) + 0.5)
    base_idx = piece * nb
    groups = {}
    for (p, a, D, w) in K.sheaves:
        groups.setdefault(D, []).append((p, a, w))
    out = {}
    for D, lst in groups.items():
        lgD = math.log10(D)
        B0 = b1 + b3 * (lgD - v0)
        q0 = np.power(10.0, -B0 * t)
        acc = [np.zeros(size) for _ in range(J + 1)]
        for (p, a, w) in lst:
            x1 = K.L - a - p * (K.H - K.h1)
            x2 = K.L - a - p * (K.H - K.h2)
            lo = np.minimum(x1, x2)
            hi = np.maximum(x1, x2)
            if uniform:
                # station i at i + 0.5 m is passed when lo <= i + 0.5 <= hi
                i1 = np.clip(np.ceil(lo - 0.5), 0, nst).astype(np.int64)
                i2 = np.clip(np.floor(hi - 0.5) + 1, 0, nst).astype(np.int64)
            else:
                i1 = np.searchsorted(grid, lo, 'left')
                i2 = np.searchsorted(grid, hi, 'right')
            live = i2 > i1
            if not live.all():
                i1, i2 = i1[live], i2[live]
                bi, qq, tt = base_idx[live], q0[live], t[live]
            else:
                bi, qq, tt = base_idx, q0, t
            idx = np.concatenate((bi + i1, bi + i2))
            wq = qq * w
            for j in range(J + 1):
                wt = np.concatenate((wq, -wq))
                acc[j] += np.bincount(idx, wt, size)
                if j < J:
                    wq = wq * tt
        M = [np.cumsum(a_.reshape(npc, nb), axis=1)[:, :nst] for a_ in acc]
        out[D] = (B0, M)
    return out, u0


def crane_u0(K):
    if len(K.u):
        return 0.5 * (float(K.u.min()) + float(K.u.max()))
    return 4.0


def combine(K, mom, u0, dgrid, J):
    """Damage per piece and station from the moment sums and the diameters
    dgrid (npc x nst) of the elements lying at the stations."""
    b0, b1, b2, b3 = K.coef
    v = np.log10(dgrid)
    dmg = np.zeros_like(dgrid)
    fact = [1.0 / math.factorial(j) for j in range(J + 1)]
    for D, (B0, M) in mom.items():
        lgDd = math.log10(D) - v
        B = b1 + b3 * lgDd
        A = b0 - 2.0 * v * B + b2 * lgDd
        x = -(B - B0) * LN10
        pref = np.power(10.0, -(A + B * u0))
        ser = np.zeros_like(dgrid)
        xp = np.ones_like(dgrid)
        for j in range(J + 1):
            ser += xp * fact[j] * M[j]
            xp = xp * x
        dmg += pref * ser
    return dmg


def series_order(K, dmin, dmax, tol=1e-10):
    """Number of terms so the series in exp(x) is good to tol."""
    b0, b1, b2, b3 = K.coef
    if len(K.u):
        tmax = 0.5 * (K.u.max() - K.u.min())
    else:
        tmax = 0.0
    dv = 0.5 * abs(math.log10(dmax) - math.log10(dmin))
    xm = abs(b3) * dv * LN10 * tmax
    J = 1
    term = xm
    while J < 40:
        term = xm ** (J + 1) / math.factorial(J + 1)
        if term * math.exp(xm) < tol:
            break
        J += 1
    return J


# --------------------------------------------------------------------------
# where the rope elements lay
# --------------------------------------------------------------------------

def _corr(a, b):
    a = a - a.mean()
    b = b - b.mean()
    den = math.sqrt(float((a * a).sum()) * float((b * b).sum()))
    return float((a * b).sum()) / den if den > 0 else 0.0


def _anti_corr(a, b):
    """Correlation of the antisymmetric parts: +1 same way round, -1 mirrored."""
    return _corr(a - a[::-1], b - b[::-1])


def clean_sheets(P):
    """Replace readings that cannot be gauge readings of this rope (slips of
    the pen: a misplaced decimal point and the like) by their neighbours."""
    P = P.copy()
    med = np.median(P)
    bad = ~np.isfinite(P) | (np.abs(P - med) > 0.25 * med)
    for k in range(P.shape[0]):
        b = bad[k]
        if b.any() and (~b).any():
            P[k, b] = np.interp(np.nonzero(b)[0], np.nonzero(~b)[0], P[k, ~b])
        elif b.all():
            P[k] = med
    return P


def sheet_frame(P):
    """Orientation of every sheet relative to the last one.

    Returns sig (+1 sheet runs as the last sheet, -1 mirrored), E, the
    sheets turned into the frame of the last sheet, and sure[k], whether the
    profiles of sheets k and k+1 told their relative orientation."""
    n = P.shape[0]
    sig = np.ones(n, dtype=int)
    sure = np.zeros(n, dtype=bool)
    for k in range(n - 2, -1, -1):
        # only the part of a profile that is not the same both ways round
        # tells which way round it is
        c = _anti_corr(P[k], P[k + 1])
        if c < -0.3:
            rel, sure[k] = -1, True
        elif c > 0.3:
            rel, sure[k] = 1, True
        else:
            rel = 1
        sig[k] = sig[k + 1] * rel
    sure[n - 1] = True
    E = np.array([P[k] if sig[k] > 0 else P[k][::-1] for k in range(n)])
    return sig, E, sure


def temporal_clean(E):
    """Remove single readings far off the element's own history."""
    n = E.shape[0]
    if n < 3:
        return E
    E = E.copy()
    for k in range(n):
        if k == 0:
            ref = 2 * E[1] - E[2] if n > 2 else E[1]
            ref = np.maximum(ref, E[1])
        elif k == n - 1:
            ref = np.minimum(2 * E[k - 1] - E[k - 2], E[k - 1])
        else:
            ref = 0.5 * (E[k - 1] + E[k + 1])
        thr = np.maximum(0.6, 0.03 * ref)
        b = np.abs(E[k] - ref) > thr
        if k not in (0, n - 1):
            # a real reading lies between the readings before and after
            lo = np.minimum(E[k - 1], E[k + 1]) - thr
            hi = np.maximum(E[k - 1], E[k + 1]) + thr
            b = (E[k] < lo) | (E[k] > hi)
        E[k, b] = ref[b]
    return E


def lie_states(W, Dint, lam=0.6):
    """Physical lie of the rope in each survey interval, from the wear.

    W[p]: wear of the elements (frame of the last sheet) in interval p,
    Dint[p]: bending damage at the crane stations in interval p.
    State +1: element index = crane station index, -1: mirrored.
    A dynamic programme with a penalty for every turn of the rope."""
    m = np.array([2.0 * _anti_corr(W[p], Dint[p]) for p in range(len(W))])
    npc = len(m)
    if npc == 0:
        return np.ones(0, dtype=int), m
    score = np.zeros((npc, 2))     # 0: +1, 1: -1
    back = np.zeros((npc, 2), dtype=int)
    score[0] = [m[0], -m[0]]
    for p in range(1, npc):
        for s, val in ((0, m[p]), (1, -m[p])):
            stay = score[p - 1, s]
            move = score[p - 1, 1 - s] - lam
            if stay >= move:
                score[p, s], back[p, s] = stay + val, s
            else:
                score[p, s], back[p, s] = move + val, 1 - s
    st = np.zeros(npc, dtype=int)
    st[-1] = int(np.argmax(score[-1]))
    for p in range(npc - 1, 0, -1):
        st[p - 1] = back[p, st[p]]
    return np.where(st == 0, 1, -1), m


def wear_rss(E, C, pws, with_p=False):
    """Least squares fit of  d0 - E[k,e] = base[k] + r[e] C[k,e]^p,
    smallest residual sum over the exponents pws."""
    y = E[0].mean() - E
    n = E.shape[0]
    best = np.inf
    bp = pws[0]
    for pw in pws:
        X = np.maximum(C, 0.0) ** pw
        mx = X.max()
        if not mx > 0:
            continue
        X = X / mx
        s = (X * X).sum(0)
        ok = s > 1e-12 * s.max()
        Xo, so = X[:, ok], s[ok]
        a = (Xo * y[:, ok]).sum(0)
        Q = (Xo / so) @ Xo.T                        # n x n
        A = E.shape[1] * np.eye(n) - Q
        rhs = y.sum(1) - (Xo * (a / so)).sum(1)
        A += 1e-9 * np.eye(n)
        try:
            b = np.linalg.solve(A, rhs)
        except np.linalg.LinAlgError:
            continue
        r = np.zeros(E.shape[1])
        r[ok] = (a - (Xo * b[:, None]).sum(0)) / so
        res = y - b[:, None] - r * X
        rs = float((res * res).sum())
        if rs < best:
            best, bp = rs, pw
    return (best, bp) if with_p else best


def _flipmap(D, s):
    """Crane-station array -> element-frame array for lie state s."""
    return D if s > 0 else D[..., ::-1]


PWS = (0.4, 0.5, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 1.0, 1.1, 1.25)


def cum_elem(Dint, states, n):
    """Damage of every element (frame of the last sheet) at each survey,
    pieces p < k counting for survey k."""
    nst = Dint.shape[1]
    C = np.zeros((n, nst))
    acc = np.zeros(nst)
    for k in range(1, n):
        acc = acc + _flipmap(Dint[k - 1], states[k - 1])
        C[k] = acc
    return C


def window_damage(K, grid, days, piece, lo_p, hi_p, J, v0, dref, NS):
    """Damage at the crane stations in NS equal spans of time over the
    survey pieces lo_p..hi_p."""
    n = len(days)
    t_a = days[lo_p] if lo_p > 0 else min(days[0], K.day[0])
    t_b = days[hi_p + 1] if hi_p + 1 < n else K.day[-1]
    sub = np.linspace(t_a, t_b, NS + 1)
    win = (piece >= lo_p) & (piece <= hi_p)
    Kw = Crane()
    Kw.__dict__.update(K.__dict__)
    Kw.day, Kw.h1, Kw.h2, Kw.u = K.day[win], K.h1[win], K.h2[win], K.u[win]
    if len(Kw.day) == 0:
        return sub, np.zeros((NS, len(grid))), np.full(NS, lo_p)
    fp = np.clip(np.searchsorted(sub, Kw.day, 'right') - 1, 0, NS - 1)
    mom, u0 = moments(Kw, fp, NS, grid, J, v0)
    Df = combine(Kw, mom, u0, np.full((NS, len(grid)), dref), J)
    mids = 0.5 * (sub[:-1] + sub[1:])
    ps = np.clip(np.searchsorted(days, mids, 'right') - 1, lo_p, hi_p)
    return sub, Df, ps


def fit_turn(E, Dint, states, days, win, s_old, s_new):
    """Best time for a turn of the rope inside a window of time, fitted to
    the wear of all surveys.  states: lie of every survey piece outside the
    window.  Returns (T, rss_best)."""
    sub, Df, ps = win
    n, nst = E.shape
    NS = len(Df)
    lo_p, hi_p = int(ps.min()), int(ps.max())
    base = np.zeros((n, nst))
    for p in range(n - 1):
        if lo_p <= p <= hi_p:
            continue
        base[p + 1:] += _flipmap(Dint[p], states[p])
    best = (np.inf, 0.5 * (sub[0] + sub[-1]))
    contrib_old = [_flipmap(Df[f], s_old) for f in range(NS)]
    contrib_new = [_flipmap(Df[f], s_new) for f in range(NS)]

    def cum(cut):
        C = base.copy()
        for f in range(NS):
            if ps[f] + 1 < n:
                C[ps[f] + 1:] += contrib_old[f] if f < cut else contrib_new[f]
        return C
    # the wear exponent belongs to the rope: fix it near the middle cut
    _, pbest = wear_rss(E, cum(NS // 2), PWS, with_p=True)
    i = PWS.index(pbest)
    pws = PWS[max(i - 1, 0):i + 2]
    for cut in (range(NS + 1) if s_old != s_new else (NS,)):
        r = wear_rss(E, cum(cut), pws)
        if r < best[0]:
            best = (r, float(sub[cut]))
    return best[1], best[0]


EVIDENCE = 25.0     # N ln(RSS0/RSS1) needed to accept a turn the lie DP did not see


def crane_result(K, svc):
    tab = survey_table(svc, K.L) if len(svc) else None
    if tab is None:
        nst = max(int(round(K.L)), 1)
        grid = np.arange(nst) + 0.5
        dn = 1.0
        if K.sheaves:
            dn = min(s[2] for s in K.sheaves) / 25.0
        days = np.array([0.0])
        P = np.full((1, nst), dn)
    else:
        days, grid, P = tab
        P = clean_sheets(P)
    n = len(days)
    nst = len(grid)
    info = {}
    if len(K.day) == 0 or not K.sheaves:
        return np.zeros(nst), info
    sig, E, sure = sheet_frame(P)
    E = temporal_clean(E)
    piece = np.clip(np.searchsorted(days, K.day, 'right') - 1, 0, n - 1)
    dmin, dmax = float(E.min()), float(E.max())
    v0 = math.log10(0.5 * (dmin + dmax))
    dref = float(np.median(E))
    J = series_order(K, dmin, dmax)
    mom, u0 = moments(K, piece, n, grid, J, v0)

    events = []
    if n >= 3:
        Dint = combine(K, mom, u0, P, J)
        W = E[:-1] - E[1:]
        states, margins = lie_states(W, Dint[:n - 1])
        st = np.r_[states, states[-1]].astype(int)
        info['margins'] = margins
        N = E.size
        flips = [k for k in range(1, n) if sig[k] != sig[k - 1]]
        # turns the lie DP saw
        for a in range(n - 2):
            if st[a] != st[a + 1]:
                cand = [k for k in flips if k - 1 in (a, a + 1)]
                if cand:
                    lo_p = hi_p = cand[0] - 1
                else:
                    lo_p, hi_p = a, a + 1
                events.append([lo_p, hi_p, int(st[a]), int(st[a + 1]), cand[0] if cand else None])
        used = set(e[4] for e in events if e[4] is not None)
        # a sheet that flips with no turn seen: written from the other end,
        # or a turn too late for the lie DP?  The wear of all sheets decides.
        for k in flips:
            if k in used or any(e[0] <= k - 1 <= e[1] for e in events):
                continue
            alt = st.copy()
            alt[k:] = -alt[k:]
            win = window_damage(K, grid, days, piece, k - 1, k - 1, J, v0, dref, 24)
            _, rss0 = fit_turn(E, Dint, st, days, win, int(st[k - 1]), int(st[k - 1]))
            T, rss1 = fit_turn(E, Dint, alt, days, win, int(st[k - 1]), int(alt[k]))
            stat = N * math.log(rss0 / max(rss1, 1e-300)) if rss0 > 0 else -np.inf
            info.setdefault('tests', []).append(('flip', k, round(stat, 1), round(T, 2)))
            if np.isfinite(rss1) and stat > EVIDENCE:
                st = alt
                events.append([k - 1, k - 1, int(st[k - 1]), int(st[k]), k])
        # a turn before the profile could show it: early sheets with no sure
        # orientation
        ka = 0
        while ka + 1 < n - 1 and not sure[ka + 1]:
            ka += 1
        if ka + 2 < n and not any(e[0] <= ka + 1 for e in events) \
                and len(margins) and (margins[:ka + 2] * st[:ka + 2]).min() < 0.15:
            win = window_damage(K, grid, days, piece, 0, ka + 1, J, v0, dref, 24)
            _, rss0 = fit_turn(E, Dint, st, days, win, int(st[ka + 2]), int(st[ka + 2]))
            best = None
            for flip_early in (True, False):
                E1 = E.copy()
                if flip_early:
                    E1[:ka + 1] = E1[:ka + 1, ::-1]
                T, rss1 = fit_turn(E1, Dint, st, days, win, int(-st[ka + 2]), int(st[ka + 2]))
                if best is None or rss1 < best[1]:
                    best = (T, rss1, E1, flip_early)
            T, rss1, E1, fe = best
            stat = N * math.log(rss0 / max(rss1, 1e-300)) if rss0 > 0 else -np.inf
            info.setdefault('tests', []).append(('early', ka, round(stat, 1), round(T, 2), fe))
            if np.isfinite(rss1) and stat > EVIDENCE:
                E = E1
                st[:ka + 2] = -st[ka + 2]
                events.append([0, ka + 1, int(-st[ka + 2]), int(st[ka + 2]), ('early', T)])
        info['sheet'] = sig
        info['states'] = st.copy()
    else:
        Dint = None
        st = np.ones(n, dtype=int)

    # when did each turn happen; the lie on either side of a window is read
    # from the final states, which later tests may have turned
    final_events = []
    for ev in events:
        lo_p, hi_p, s_old, s_new, tag = ev
        if hi_p + 1 < n:
            s_new = int(st[hi_p + 1])
            s_old = int(st[lo_p - 1]) if lo_p >= 1 else -s_new
        elif lo_p >= 1:
            s_old = int(st[lo_p - 1])
            s_new = -s_old
        if s_old == s_new:
            continue
        t_a = days[lo_p]
        t_b = days[hi_p + 1] if hi_p + 1 < n else K.day[-1]
        if isinstance(tag, tuple):
            T = tag[1]
        else:
            try:
                win = window_damage(K, grid, days, piece, lo_p, hi_p, J, v0, dref,
                                    24 * (hi_p - lo_p + 1))
                T, rss1 = fit_turn(E, Dint, st, days, win, s_old, s_new)
                if not np.isfinite(rss1):
                    T = 0.5 * (t_a + t_b)
            except Exception:
                T = 0.5 * (t_a + t_b)
        T = float(min(max(T, t_a), t_b))
        final_events.append((T, s_old, s_new, lo_p, hi_p))
    info['events'] = final_events

    # final pieces: survey intervals, split at the turns
    st_tail = int(st[-1])
    if final_events:
        brk = np.unique(np.r_[days, [e[0] for e in final_events]])
        fpiece = np.clip(np.searchsorted(brk, K.day, 'right') - 1, 0, len(brk) - 1)
        npc = len(brk)
        sv_idx = np.clip(np.searchsorted(days, brk, 'right') - 1, 0, n - 1)
        pst = st[sv_idx].astype(int)
        for (T, s_old, s_new, lo_p, hi_p) in final_events:
            in_win = (sv_idx >= lo_p) & (sv_idx <= hi_p)
            pst[in_win & (brk < T)] = s_old
            pst[in_win & (brk >= T)] = s_new
        # moments again only for the movements of the split pieces
        split = np.zeros(n, dtype=bool)
        for (T, s_old, s_new, lo_p, hi_p) in final_events:
            split[lo_p:hi_p + 1] = True
        inw = split[piece]
        Kw = Crane()
        Kw.__dict__.update(K.__dict__)
        Kw.day, Kw.h1, Kw.h2, Kw.u = K.day[inw], K.h1[inw], K.h2[inw], K.u[inw]
        momw, _ = moments(Kw, fpiece[inw], npc, grid, J, v0, u0)
        rows_w = split[sv_idx]
        mom2 = {}
        for D in mom:
            B0, M = mom[D]
            Mw = momw[D][1]
            mom2[D] = (B0, [np.where(rows_w[:, None], Mw[j], M[j][sv_idx]) for j in range(J + 1)])
        u02 = u0
    else:
        npc = n
        sv_idx = np.arange(n)
        pst = st.astype(int)
        mom2, u02 = mom, u0
    # diameters of the elements at the crane stations, piece by piece
    dgrid = np.array([_flipmap(E[sv_idx[p]], pst[p]) for p in range(npc)])
    Dp = combine(K, mom2, u02, dgrid, J)
    tot = np.zeros(nst)
    for p in range(npc):
        tot += Dp[p] if pst[p] == st_tail else Dp[p][::-1]
    info['pst'] = pst
    return np.maximum(tot, 0.0), info


def simple_result(K, svc):
    """Fallback: sheets as written, rope never turned."""
    tab = survey_table(svc, K.L)
    days, grid, P = tab
    n = len(days)
    piece = np.clip(np.searchsorted(days, K.day, 'right') - 1, 0, n - 1)
    J = series_order(K, P.min(), P.max())
    mom, u0 = moments(K, piece, n, grid, J, math.log10(P.mean()))
    return np.maximum(combine(K, mom, u0, P, J).sum(0), 0.0)


def fmt(x):
    if not np.isfinite(x) or x <= 0:
        return '0.0'
    return np.format_float_positional(float(x), precision=10, unique=False,
                                      fractional=False, trim='-')


def write_out(path, rows):
    data = 'row,damage\n' + ''.join('%s,%s\n' % (r, fmt(v)) for r, v in rows)
    if os.path.islink(path):
        os.unlink(path)
    elif os.path.isdir(path):
        raise IsADirectoryError(path)
    tmp = path + '.tmp%d' % os.getpid()
    try:
        with open(tmp, 'w', newline='') as fh:
            fh.write(data)
        os.replace(tmp, path)
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        if os.path.islink(path):
            os.unlink(path)
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, 'O_NOFOLLOW', 0)
        fd = os.open(path, flags, 0o644)
        with os.fdopen(fd, 'w', newline='') as fh:
            fh.write(data)


def run(wd, out, verbose=False):
    cranes, sheaves, mv, surveys = load_package(wd)
    rows = []
    mv_g = {c: g for c, g in mv.groupby('crane', sort=False)}
    sh_g = {c: g for c, g in sheaves.groupby('crane', sort=False)}
    sv_g = {c: g for c, g in surveys.groupby('crane', sort=False)}
    empty_mv = mv.iloc[:0]
    for _, c in cranes.iterrows():
        name = str(c['crane']).strip()
        svc = sv_g.get(name, surveys.iloc[:0])
        try:
            K = crane_setup(c, sh_g.get(name, sheaves.iloc[:0]), mv_g.get(name, empty_mv))
            try:
                dmg, info = crane_result(K, svc)
            except Exception:
                if verbose:
                    import traceback
                    traceback.print_exc()
                dmg, info = simple_result(K, svc), {}
            if verbose:
                print(name, {k: v for k, v in info.items() if k != 'margins'},
                      'margins', np.round(info.get('margins', []), 2), file=sys.stderr)
        except Exception:
            if verbose:
                import traceback
                traceback.print_exc()
            nst = 0
            try:
                tab = survey_table(svc, float(c['rope_length_m']))
                nst = len(tab[1])
            except Exception:
                try:
                    nst = int(round(float(c['rope_length_m'])))
                except Exception:
                    nst = 0
            dmg = np.zeros(nst)
        dmg = np.where(np.isfinite(dmg), dmg, 0.0)
        if len(dmg) and dmg.max() > 0:
            # what is left of the running sums at stations never bent
            dmg = np.where(dmg < 1e-9 * dmg.max(), 0.0, dmg)
        for i, x in enumerate(dmg):
            rows.append(('%s-%03d' % (name, i + 1), x))
    write_out(out, rows)


def main(argv):
    if len(argv) < 3:
        print('usage: ropes.py WORKS_DIR OUT_CSV', file=sys.stderr)
        return 0
    wd, out = argv[1], argv[2]
    verbose = bool(os.environ.get('ROPES_VERBOSE'))
    try:
        run(wd, out, verbose)
    except Exception:
        import traceback
        traceback.print_exc()
        try:
            if not os.path.exists(out) or os.path.islink(out):
                write_out(out, [])
        except Exception:
            pass
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
