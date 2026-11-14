#!/usr/bin/env python3
"""Bending fatigue damage along hoist ropes to RS-4.  Usage: ropes.py WORKS_DIR OUT_CSV"""
import os
import sys

import numpy as np
import pandas as pd

G = 9.80665
COEF = {'8x36': (-1.214, 0.887, 7.432, -2.103), '6x36': (-1.371, 0.934, 7.518, -2.146)}
Q = 16          # chunks per survey interval (resolution of an unrecorded turn)
NM = 4          # moments for the diameter correction
SIG = 0.02      # gauge noise, mm
TURN_PEN = 8.0
NOFLIP_PEN = 60.0  # penalty (in chi-square units) for assuming a turn
LN10 = np.log(10.0)


def orient_surveys(D):
    """s[k]: True if survey k's raw stations are mirrored relative to the last survey's frame."""
    K = len(D)
    s = np.zeros(K, bool)
    E = [None] * K
    E[K - 1] = D[K - 1]
    for k in range(K - 2, -1, -1):
        c = []
        for cand in (D[k], D[k][::-1]):
            v = 0.0
            for j in range(k + 1, min(K, k + 5)):
                v += np.var(E[j] - cand)
            c.append(v)
        s[k] = c[1] < c[0]
        E[k] = D[k][::-1] if s[k] else D[k]
    return s, np.array(E)


def fit_cost(dl, P):
    P = P - P.mean()
    y = dl - dl.mean()
    pp = P @ P
    tot = y @ y
    if pp <= 0:
        return tot / SIG ** 2
    a = (P @ y) / pp
    if a <= 0:
        return tot / SIG ** 2
    return (tot - a * (P @ y)) / SIG ** 2


def crane_damage(c, sh, mv, sv):
    L = float(c.rope_length_m)
    n = int(round(L))
    b0, b1, b2, b3 = COEF[str(c.rope_construction).strip()]
    days = np.sort(sv.day.unique())
    st_last = None
    D = []
    for d in days:
        q = sv[sv.day == d].sort_values('station_m')
        idx = np.clip(np.floor(q.station_m.values).astype(int), 0, n - 1)
        arr = np.full(n, np.nan)
        arr[idx] = q.diameter_mm.values
        if np.isnan(arr).any():
            good = ~np.isnan(arr)
            arr = np.interp(np.arange(n), np.nonzero(good)[0], arr[good])
        D.append(arr)
    D = np.array(D)
    K = len(days)
    s, E = orient_surveys(D)   # E: diameters in the element frame (frame of survey 0)
    g0 = np.log10(np.nanmean(D[0]))

    mday = mv.day.values
    seg = np.searchsorted(days, mday, side='right') - 1
    seg = np.clip(seg, 0, K - 1)
    # chunk index inside each segment, equal counts
    chunk = np.zeros(len(mv), np.int64)
    order = np.argsort(mday, kind='stable')
    seg_o = seg[order]
    starts = np.searchsorted(seg_o, np.arange(K))
    ends = np.searchsorted(seg_o, np.arange(K), side='right')
    for k in range(K):
        m = ends[k] - starts[k]
        if m:
            chunk[order[starts[k]:ends[k]]] = (np.arange(m) * Q) // m
    cid = seg * Q + chunk
    NC = K * Q

    S = (mv.hook_load_t.values + float(c.block_mass_t)) * 1000.0 * G / (int(c.falls) * float(c.reeving_efficiency))
    u = np.log10(S)
    u0 = float(np.median(u))
    v = u - u0
    h1 = mv.from_height_m.values
    h2 = mv.to_height_m.values
    H = float(c.upper_block_height_m)

    sheaves = []
    for _, q in sh.iterrows():
        Dd = float(q.diameter_mm)
        lgD = np.log10(Dd)
        w = float(q.bend_weight)
        c0 = b1 + b3 * (lgD - g0)
        lgN0 = b0 + c0 * (u - 2 * g0) + b2 * (lgD - g0)
        f = w * 10.0 ** (-lgN0)
        x1 = L - q.offset_m - q.parts * (H - h1)
        x2 = L - q.offset_m - q.parts * (H - h2)
        lo = np.clip(np.ceil(np.minimum(x1, x2) - 0.5), 0, n).astype(np.int64)
        hi = np.clip(np.floor(np.maximum(x1, x2) - 0.5) + 1, 0, n).astype(np.int64)
        ok = hi > lo
        il = cid[ok] * (n + 1) + lo[ok]
        ih = cid[ok] * (n + 1) + hi[ok]
        fo = f[ok]
        vo = v[ok]
        M = np.empty((NM, NC, n))
        vp = np.ones_like(vo)
        for j in range(NM):
            wj = fo * vp
            a = np.bincount(il, wj, NC * (n + 1)) - np.bincount(ih, wj, NC * (n + 1))
            M[j] = np.cumsum(a.reshape(NC, n + 1), axis=1)[:, :n]
            vp = vp * vo / (j + 1)   # store v^j / j!
        sheaves.append((M, c0, b3, b2))

    # loss proxy in reeving frame per chunk
    B = sum(sh_[0][0] for sh_ in sheaves).reshape(K, Q, n)

    # DP over rope orientation o_k at each survey (o_0 = 0)
    INF = 1e300
    cost = np.array([0.0, 0.0])
    back = []
    turn_t = {}
    for k in range(K - 1):
        dl = E[k] - E[k + 1]
        new = np.full(2, INF)
        bp = np.zeros(2, int)
        Bk = B[k]
        cum = np.cumsum(Bk, axis=0)
        tot = cum[-1]
        for o1 in (0, 1):
            for o2 in (0, 1):
                if cost[o1] >= INF:
                    continue
                if o1 == o2:
                    P = tot[::-1] if o1 else tot
                    cc = fit_cost(dl, P)
                else:
                    best = INF
                    bt = Q // 2
                    for t in range(1, Q):
                        before = cum[t - 1]
                        after = tot - before
                        P = (before[::-1] if o1 else before) + (after[::-1] if o2 else after)
                        ct = fit_cost(dl, P)
                        if ct < best:
                            best, bt = ct, t
                    cc = best + (TURN_PEN if s[k] != s[k + 1] else NOFLIP_PEN)
                    turn_t[(k, o1)] = bt
                if cost[o1] + cc < new[o2]:
                    new[o2] = cost[o1] + cc
                    bp[o2] = o1
        back.append(bp)
        cost = new
    o = np.zeros(K, int)
    o[-1] = int(np.argmin(cost))
    for k in range(K - 2, -1, -1):
        o[k] = back[k][o[k + 1]]

    # orientation per chunk
    och = np.zeros((K, Q), int)
    for k in range(K):
        och[k, :] = o[k]
        if k < K - 1 and o[k + 1] != o[k]:
            t = turn_t[(k, o[k])]
            och[k, t:] = o[k + 1]

    dmg = np.zeros(n)   # element frame
    for M, c0, b3_, b2_ in sheaves:
        Mr = M.reshape(NM, K, Q, n)
        for k in range(K):
            g = np.log10(E[k])
            de = g - g0
            pref = 10.0 ** (b2_ * de + 2 * c0 * de - 2 * b3_ * de * de + b3_ * de * (u0 - 2 * g0))
            z = LN10 * b3_ * de
            for oo in (0, 1):
                sel = och[k] == oo
                if not sel.any():
                    continue
                Ms = Mr[:, k, sel, :].sum(axis=1)   # reeving frame
                if oo:
                    Ms = Ms[:, ::-1]
                ser = np.zeros(n)
                zp = np.ones(n)
                for j in range(NM):
                    ser += Ms[j] * zp
                    zp = zp * z
                dmg += pref * ser
    # result at stations along the rope at the end of the log (reeving frame)
    res = dmg[::-1] if och[-1, -1] else dmg
    return res


def main():
    wd, out = sys.argv[1], sys.argv[2]
    cr = pd.read_csv(os.path.join(wd, 'cranes.csv'), skipinitialspace=True)
    sh = pd.read_csv(os.path.join(wd, 'sheaves.csv'), skipinitialspace=True)
    mv = pd.read_csv(os.path.join(wd, 'movements.csv'), skipinitialspace=True)
    sv = pd.read_csv(os.path.join(wd, 'surveys.csv'), skipinitialspace=True)
    for df in (cr, sh, mv, sv):
        df.columns = [x.strip() for x in df.columns]
        df['crane'] = df['crane'].astype(str).str.strip() if 'crane' in df else None
    mvg = dict(tuple(mv.groupby('crane', sort=False)))
    shg = dict(tuple(sh.groupby('crane', sort=False)))
    svg = dict(tuple(sv.groupby('crane', sort=False)))
    lines = ['row,damage']
    for _, c in cr.iterrows():
        name = c.crane
        m = mvg.get(name, mv.iloc[:0])
        n = int(round(float(c.rope_length_m)))
        try:
            r = crane_damage(c, shg[name], m, svg[name])
        except Exception as e:  # never fail the run
            print('warning:', name, e, file=sys.stderr)
            r = np.zeros(n)
        r = np.nan_to_num(r)
        for i, x in enumerate(r):
            lines.append('%s-%03d,%.9f' % (name, i + 1, x))
    if os.path.islink(out):
        os.unlink(out)
    with open(out, 'w') as fh:
        fh.write('\n'.join(lines) + '\n')


if __name__ == '__main__':
    main()
