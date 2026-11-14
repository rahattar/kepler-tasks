#!/usr/bin/env python3
"""Bending fatigue damage along hoist ropes to RS-4 (issue 3), one works package."""
import os, sys
import numpy as np
import pandas as pd

G = 9.80665
COEF = {'8x36': (-1.214, 0.887, 7.432, -2.103),
        '6x36': (-1.371, 0.934, 7.518, -2.146)}
NMOM = 5


def period_damage(L, crane, sh, mv_day, hf, ht, lgS, dc, t0, t1):
    """Damage in crane frame from movements with t0 <= day < t1, crane-frame diameters dc."""
    b0, b1, b2, b3 = COEF[str(crane.rope_construction).strip()]
    i0, i1 = np.searchsorted(mv_day, [t0, t1], side='left')
    dmg = np.zeros(L)
    if i1 <= i0:
        return dmg
    a_h, b_h, s = hf[i0:i1], ht[i0:i1], lgS[i0:i1]
    H = crane.upper_block_height_m
    lgd = np.log10(dc)
    s0 = s.mean()
    ds = (s - s0) * np.log(10.0)
    pw = [np.ones_like(ds)]
    for k in range(1, NMOM):
        pw.append(pw[-1] * ds / k)
    for r in sh.itertuples():
        lD = np.log10(r.diameter_mm)
        l = lD - lgd
        c = b1 + b3 * l
        A = b0 + b2 * l - 2.0 * c * lgd
        c0 = c.mean()
        base = r.bend_weight * 10.0 ** (-c0 * s)
        xa = L - r.offset_m - r.parts * (H - a_h)
        xb = L - r.offset_m - r.parts * (H - b_h)
        lo = np.ceil(np.minimum(xa, xb) - 0.5)
        hi = np.floor(np.maximum(xa, xb) - 0.5)
        lo = np.clip(lo, 0, L).astype(np.int64)
        hi = np.clip(hi + 1, 0, L).astype(np.int64)
        ok = hi > lo
        lo, hi = lo[ok], hi[ok]
        idx = np.concatenate([lo, hi])
        tot = np.zeros(L)
        delta = c - c0
        # exp(-delta*ln10*s) = exp(-delta*ln10*s0) * sum_k (-delta)^k ds^k/k!
        fac = np.ones(L)
        for k in range(NMOM):
            wv = base[ok] * pw[k][ok]
            m = np.bincount(idx, weights=np.concatenate([wv, -wv]), minlength=L + 1)
            tot += fac * np.cumsum(m)[:L]
            fac = fac * (-delta)
        dmg += tot * 10.0 ** (-A - delta * s0)
    return dmg


def main():
    wd, out = sys.argv[1], sys.argv[2]
    cr = pd.read_csv(os.path.join(wd, 'cranes.csv'), skipinitialspace=True)
    sv = pd.read_csv(os.path.join(wd, 'sheaves.csv'), skipinitialspace=True)
    mv = pd.read_csv(os.path.join(wd, 'movements.csv'), skipinitialspace=True)
    su = pd.read_csv(os.path.join(wd, 'surveys.csv'), skipinitialspace=True)
    for df in (cr, sv, mv, su):
        df['crane'] = df['crane'].astype(str).str.strip()
    rows = []
    for crane in cr.itertuples():
        name = crane.crane
        L = int(round(crane.rope_length_m))
        sh = sv[sv.crane == name]
        m = mv[mv.crane == name]
        m = m.iloc[np.argsort(m.day.values, kind='stable')]
        day = m.day.values.astype(float)
        S = (m.hook_load_t.values + crane.block_mass_t) * 1000.0 * G / (crane.falls * crane.reeving_efficiency)
        lgS = np.log10(S)
        s = su[su.crane == name]
        sdays = np.sort(s.day.unique())
        prof = []
        for d in sdays:
            g = s[s.day == d].sort_values('station_m')
            st = g.station_m.values
            xs = np.arange(L) + 0.5
            prof.append(np.interp(xs, st, g.diameter_mm.values))
        prof = np.array(prof)
        dmg = history(L, crane, sh, day, m.from_height_m.values, m.to_height_m.values, lgS, sdays, prof)
        for i in range(L):
            rows.append('%s-%03d,%.10f' % (name, i + 1, dmg[i]))
    tmp = out + '.tmp%d' % os.getpid()
    with open(tmp, 'w') as f:
        f.write('row,damage\n' + '\n'.join(rows) + '\n')
    os.replace(tmp, out)


def _fit(y, cols):
    X = np.column_stack(cols + [np.ones_like(y)])
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    r = y - X @ coef
    return float(r @ r), coef


def history(L, crane, sh, day, hf, ht, lgS, sdays, prof):
    """Reconstruct turns / dead-end surveys from the thinning pattern, then sum damage."""
    K = len(sdays)
    ends = list(sdays[1:]) + [np.inf]
    fl = lambda v: v[::-1]
    # bending profile (crane frame) of each survey interval, diameters as given (only shape matters)
    B = [None] * K
    for k in range(1, K):
        B[k] = period_damage(L, crane, sh, day, hf, ht, lgS, prof[k - 1], sdays[k - 1], sdays[k])
        if B[k].max() > 0:
            B[k] = B[k] / B[k].max()
    # scores: sc[k][(r_prev, r_cur, turn)] = (sse, f)
    sc = [None] * K
    simple = []
    for k in range(1, K):
        d = {}
        for rp in (0, 1):
            cp = fl(prof[k - 1]) if rp else prof[k - 1]
            for rc in (0, 1):
                cc = fl(prof[k]) if rc else prof[k]
                e0, _ = _fit(cp - cc, [B[k]])
                e1, cf = _fit(fl(cp) - cc, [B[k], fl(B[k])])
                a, b = max(cf[0], 0.0), max(cf[1], 0.0)
                f = b / (a + b) if a + b > 0 else 0.5
                d[(rp, rc, 0)] = (e0, None)
                d[(rp, rc, 1)] = (e1, f)
        sc[k] = d
        simple.append(min(v[0] for v in d.values()))
    if K > 1:
        sig2 = float(np.median(simple)) / max(L - 2, 1)
    else:
        sig2 = 0.0
    pen = 60.0 * sig2
    # DP over r_k
    INF = float('inf')
    cost = {0: 0.0, 1: pen}
    back = [None] * K
    for k in range(1, K):
        nc, bk = {}, {}
        for rc in (0, 1):
            best = (INF, None)
            for rp in (0, 1):
                for t in (0, 1):
                    v = cost[rp] + sc[k][(rp, rc, t)][0] + pen * ((rp != rc) + t)
                    if v < best[0]:
                        best = (v, (rp, t))
            nc[rc], bk[rc] = best
        cost, back[k] = nc, bk
    r = [0] * K
    turn = [0] * K
    r[K - 1] = min(cost, key=cost.get)
    for k in range(K - 1, 0, -1):
        r[k - 1], turn[k] = back[k][r[k]]
    if os.environ.get('ROPES_DEBUG'):
        print(crane.crane, 'r', ''.join(map(str, r)), 'turn', ''.join(map(str, turn)), file=sys.stderr)
    dmg = np.zeros(L)
    for k in range(K):
        dc = fl(prof[k]) if r[k] else prof[k]
        t0 = -np.inf if k == 0 else sdays[k]
        t1 = ends[k]
        if k + 1 < K and turn[k + 1]:
            f = sc[k + 1][(r[k], r[k + 1], 1)][1]
            i0, i1 = np.searchsorted(day, [t0, t1])
            n = i1 - i0
            j = i0 + int(round(f * n))
            tt = day[j] if j < i1 else t1
            dmg += period_damage(L, crane, sh, day, hf, ht, lgS, dc, t0, tt)
            dmg = fl(dmg)
            dmg += period_damage(L, crane, sh, day, hf, ht, lgS, fl(dc), tt, t1)
        else:
            dmg += period_damage(L, crane, sh, day, hf, ht, lgS, dc, t0, t1)
    return dmg


if __name__ == '__main__':
    main()
