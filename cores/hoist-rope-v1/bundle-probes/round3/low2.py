#!/usr/bin/env python3
"""RS-4 bending damage along hoist ropes for one works package.
Usage: python3 ropes.py WORKS_DIR OUT_CSV"""
import sys, os
import numpy as np, pandas as pd

G = 9.80665
COEF = {'8x36': (-1.214, 0.887, 7.432, -2.103), '6x36': (-1.371, 0.934, 7.518, -2.146)}
PEN_MISREAD = 8.0   # prior cost (log-likelihood units) of a survey read from the dead end
PEN_TURN = 20.0      # prior cost of an unrecorded turn end for end


def seg_damage(L, ns, H, sheaves, co, h0, h1, S, dpos):
    """Damage at each rope position (station centres) for movements (h0,h1,S),
    rope diameter dpos at each position. Exact up to a 4-term expansion of S^-B."""
    b0, b1, b2, b3 = co
    out = np.zeros(ns)
    if len(S) == 0:
        return out
    lnS = np.log(S)
    cS = lnS.mean()
    c = lnS - cS
    lgd = np.log10(dpos)
    for p, a, D, w in sheaves:
        lgR = np.log10(D) - lgd
        B = b1 + b3 * lgR
        A = b0 - 2 * B * lgd + b2 * lgR
        B0 = B.mean()
        xa = L - a - p * (H - h0)
        xb = L - a - p * (H - h1)
        lo = np.minimum(xa, xb)
        hi = np.maximum(xa, xb)
        il = np.clip(np.ceil(lo - 0.5), 0, ns).astype(np.int64)
        ih = np.clip(np.floor(hi - 0.5) + 1, 0, ns).astype(np.int64)
        ih = np.maximum(ih, il)
        v = np.exp(-B0 * lnS)
        delta = B - B0
        tot = np.zeros(ns)
        fact = 1.0
        for k in range(5):
            M = np.cumsum(np.bincount(il, v, ns + 1) - np.bincount(ih, v, ns + 1))[:ns]
            tot += M * (-delta) ** k / fact
            v = v * c
            fact *= (k + 1)
        tot *= np.exp(-delta * cS)
        out += w * 10.0 ** (-A) * tot
    return out


def fit_cost(l, regs):
    """least squares of l on [1, regs...] with nonnegative slopes; returns (cost, coefs)"""
    n = len(l)
    X = np.column_stack([np.ones(n)] + regs)
    best = None
    # try full fit, then drop negative slopes
    import itertools
    k = len(regs)
    for keep in itertools.product([1, 0], repeat=k):
        cols = [0] + [i + 1 for i in range(k) if keep[i]]
        co, *_ = np.linalg.lstsq(X[:, cols], l, rcond=None)
        if any(co[1:] < 0):
            continue
        full = np.zeros(k + 1)
        full[cols] = co
        sse = float(np.sum((l - X @ full) ** 2))
        if best is None or sse < best[0]:
            best = (sse, full)
    sse, full = best
    return n * np.log(max(sse, 1e-12) / n), full


def flipif(v, f):
    return v[::-1] if f else v


def crane_damage(c, shs, m, s):
    L = float(c['rope_length_m'])
    H = float(c['upper_block_height_m'])
    co = COEF[str(c['rope_construction']).strip()]
    days = np.sort(s['day'].unique())
    ns = None
    Dk = []
    for dy in days:
        g = s[s['day'] == dy].sort_values('station_m')
        Dk.append(g['diameter_mm'].values.astype(float))
    ns = len(Dk[-1])
    for i in range(len(Dk)):
        if len(Dk[i]) != ns:  # irregular survey: interpolate onto last survey stations
            g = s[s['day'] == days[i]].sort_values('station_m')
            Dk[i] = np.interp(np.arange(ns) + 0.5, g['station_m'].values, g['diameter_mm'].values)
    K = len(days)
    m = m.sort_values('day', kind='stable')
    md = m['day'].values
    h0 = m['from_height_m'].values.astype(float)
    h1 = m['to_height_m'].values.astype(float)
    S = (m['hook_load_t'].values + float(c['block_mass_t'])) * 1000.0 * G / (
        float(c['falls']) * float(c['reeving_efficiency']))
    bounds = np.searchsorted(md, days, side='left')
    bounds = np.append(bounds, len(md))
    bounds[0] = 0

    # nominal damage-rate profiles per interval (positions), uniform diameter
    R = []
    for j in range(K - 1):
        a, b = bounds[j], bounds[j + 1]
        R.append(seg_damage(L, ns, H, shs, co, h0[a:b], h1[a:b], S[a:b],
                            np.full(ns, max(Dk[j].mean(), 1e-3))))

    # Viterbi over states (o,q): o rope orientation, q survey read from dead end.
    states = [(0, 0), (0, 1), (1, 0), (1, 1)]
    def elem(k, st):
        o, q = st
        return flipif(Dk[k], o ^ q)
    def pos_of_elem(r, o):  # profile in position -> value at element u
        return flipif(r, o)
    cost = np.array([0.0, PEN_MISREAD, 1e9, 1e9])  # rope starts as put on
    back = []
    fits = []
    for j in range(K - 1):
        nc = np.full(4, np.inf)
        bk = np.zeros(4, int)
        ft = [None] * 4
        for t, st2 in enumerate(states):
            for f, st1 in enumerate(states):
                if cost[f] >= 1e8:
                    continue
                if st1[0] == st2[0]:
                    cst = np.inf
                    # the new rope's first survey is featureless: its orientation is not told
                    for f0 in ((0, 1) if j == 0 else (None,)):
                        e1 = elem(j, st1) if f0 is None else flipif(Dk[0], f0)
                        cc, cf = fit_cost(e1 - elem(j + 1, st2), [pos_of_elem(R[j], st1[0])])
                        cst = min(cst, cc)
                    extra = 0.0
                    info = None
                elif j == 0:
                    continue  # a turn before the first worn survey cannot be seen; take none
                else:
                    l = elem(j, st1) - elem(j + 1, st2)
                    cst, cf = fit_cost(l, [pos_of_elem(R[j], st1[0]), pos_of_elem(R[j], st2[0])])
                    extra = PEN_TURN
                    tot = cf[1] + cf[2]
                    info = cf[1] / tot if tot > 0 else 0.5
                tc = cost[f] + cst + extra + (PEN_MISREAD if st2[1] != st1[1] else 0.0)
                if tc < nc[t]:
                    nc[t] = tc
                    bk[t] = f
                    ft[t] = info
        cost = nc
        back.append(bk)
        fits.append(ft)
    st = int(np.argmin(cost))
    path = [st]
    phis = []
    for j in range(K - 2, -1, -1):
        phis.append(fits[j][st])
        st = back[j][st]
        path.append(st)
    path = path[::-1]
    phis = phis[::-1]

    # damage along the true history, in element coordinates
    dmg = np.zeros(ns)
    hist = []
    for j in range(K):
        o, q = states[path[j]]
        E = elem(j, states[path[j]])
        a, b = bounds[j], bounds[j + 1]
        if j < K - 1 and states[path[j + 1]][0] != o:
            o2 = states[path[j + 1]][0]
            # turn day: split where the share of the interval's damage matches the fit, kept near middle
            phi = phis[j] if phis[j] is not None else 0.5
            phi = 0.5 + 0.5 * (min(max(phi, 0.0), 1.0) - 0.5)
            w = np.abs(h1[a:b] - h0[a:b]) * S[a:b] ** (-co[1])
            cw = np.cumsum(w)
            cut = a + int(np.searchsorted(cw, phi * cw[-1])) if len(cw) else a
            hist.append((j, 'turn', float(md[cut]) if cut < len(md) else None))
            for (x0, x1, oo) in ((a, cut, o), (cut, b, o2)):
                dp = seg_damage(L, ns, H, shs, co, h0[x0:x1], h1[x0:x1], S[x0:x1], flipif(E, oo))
                dmg += flipif(dp, oo)
        else:
            dp = seg_damage(L, ns, H, shs, co, h0[a:b], h1[a:b], S[a:b], flipif(E, o))
            dmg += flipif(dp, o)
        if q:
            hist.append((j, 'misread'))
    oK = states[path[-1]][0]
    if os.environ.get('ROPES_DEBUG'):
        print(c['crane'], hist, file=sys.stderr)
    return flipif(dmg, oK)


def main():
    wd, out = sys.argv[1], sys.argv[2]
    cr = pd.read_csv(os.path.join(wd, 'cranes.csv'), skipinitialspace=True)
    sh = pd.read_csv(os.path.join(wd, 'sheaves.csv'), skipinitialspace=True)
    mv = pd.read_csv(os.path.join(wd, 'movements.csv'), skipinitialspace=True)
    sv = pd.read_csv(os.path.join(wd, 'surveys.csv'), skipinitialspace=True)
    for df in (cr, sh, mv, sv):
        df.columns = [x.strip() for x in df.columns]
        df['crane'] = df['crane'].astype(str).str.strip()
    lines = ['row,damage']
    for _, c in cr.iterrows():
        n = c['crane']
        shs = [(float(r.parts), float(r.offset_m), float(r.diameter_mm), float(r.bend_weight))
               for r in sh[sh['crane'] == n].itertuples()]
        d = crane_damage(c, shs, mv[mv['crane'] == n], sv[sv['crane'] == n])
        for i, v in enumerate(d):
            lines.append('%s-%03d,%.6g' % (n, i + 1, v))
    if os.path.islink(out):
        os.unlink(out)
    with open(out, 'w') as f:
        f.write('\n'.join(lines) + '\n')


if __name__ == '__main__':
    main()
