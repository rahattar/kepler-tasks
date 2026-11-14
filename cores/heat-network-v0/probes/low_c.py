import sys, os, json
import numpy as np
import pandas as pd
import scipy.sparse as sp
from scipy.sparse.linalg import splu

RHO = 975.0
C = 4.19
DT = 120.0


def main(pkg, out):
    net = json.load(open(os.path.join(pkg, 'network.json')))
    Tg = float(net['ground_C'])
    hours = float(net['hours'])
    nodes = pd.read_csv(os.path.join(pkg, 'nodes.csv'))['node'].astype(str).tolist()
    nidx = {n: i for i, n in enumerate(nodes)}
    N = len(nodes)
    pl = nidx[str(net['plant_node'])]
    pipes = pd.read_csv(os.path.join(pkg, 'pipes.csv'))
    pipes['pipe'] = pipes['pipe'].astype(str)
    P = len(pipes)
    pu = pipes['from_node'].astype(str).map(nidx).to_numpy()
    pv = pipes['to_node'].astype(str).map(nidx).to_numpy()
    VOL = pipes['volume_m3'].to_numpy(float)
    R = pipes['resistance_Pa_s2_kg2'].to_numpy(float)
    TAU = pipes['loss_time_h'].to_numpy(float) * 3600.0
    subs = pd.read_csv(os.path.join(pkg, 'substations.csv'))
    subs['substation'] = subs['substation'].astype(str)
    S = len(subs)
    sidx = {s: i for i, s in enumerate(subs['substation'])}
    sn = subs['node'].astype(str).map(nidx).to_numpy()
    Tr = subs['return_C'].to_numpy(float)
    K = subs['valve_capacity'].to_numpy(float)

    nsteps = int(round(hours * 3600 / DT))
    tk = np.arange(nsteps + 1) * DT  # seconds
    # schedules: value at t_(k-1) for step k
    plant = pd.read_csv(os.path.join(pkg, 'plant.csv')).sort_values('time_h')
    tstart = tk[:-1] / 3600.0
    pi_ = np.searchsorted(plant['time_h'].to_numpy(float), tstart + 1e-9, side='right') - 1
    Tsup_pl = plant['supply_C'].to_numpy(float)[pi_]
    DP = plant['dp_Pa'].to_numpy(float)[pi_]
    dem = pd.read_csv(os.path.join(pkg, 'demand.csv'))
    dem['substation'] = dem['substation'].astype(str)
    Q = np.zeros((nsteps, S))
    for s, g in dem.groupby('substation'):
        g = g.sort_values('time_h')
        ii = np.searchsorted(g['time_h'].to_numpy(float), tstart + 1e-9, side='right') - 1
        Q[:, sidx[s]] = g['heat_kW'].to_numpy(float)[np.maximum(ii, 0)]

    init = pd.read_csv(os.path.join(pkg, 'initial.csv'))
    init['name'] = init['name'].astype(str)
    pidx = {p: i for i, p in enumerate(pipes['pipe'])}
    Tpipe0 = np.zeros(2 * P)
    Tn_s = np.zeros(N)
    Tn_r = np.zeros(N)
    for kind, name, nw, T in init[['kind', 'name', 'network', 'temp_C']].itertuples(index=False):
        if kind == 'pipe':
            Tpipe0[pidx[name] + (P if nw == 'return' else 0)] = T
        else:
            (Tn_r if nw == 'return' else Tn_s)[nidx[name]] = T

    # ---------- hydraulics: unknown h = p_s - p_r at nodes ----------
    free = np.array([i for i in range(N) if i != pl])
    fpos = -np.ones(N, int)
    fpos[free] = np.arange(len(free))
    NF = len(free)
    g2 = 1.0 / np.sqrt(2.0 * R)
    # sparse pattern
    rows = np.concatenate([pu, pv, pu, pv])
    cols = np.concatenate([pu, pv, pv, pu])
    sgn = np.concatenate([np.ones(P), np.ones(P), -np.ones(P), -np.ones(P)])
    keep = (fpos[rows] >= 0) & (fpos[cols] >= 0)
    hr = fpos[rows[keep]]; hc = fpos[cols[keep]]; hs = sgn[keep]
    allr = np.concatenate([hr, np.arange(NF)])
    allc = np.concatenate([hc, np.arange(NF)])
    sub_free = fpos[sn]

    def flows(h, mw):
        d = h[pu] - h[pv]
        ad = np.abs(d)
        m = np.sign(d) * g2 * np.sqrt(ad)
        hp = np.maximum(h[sn], 0.0)
        ms = np.minimum(mw, K * np.sqrt(hp))
        return d, ad, m, hp, ms

    def _unused(h, mw):
        d, ad, m, hp, ms = flows(h, mw)
        e = np.sum((2.0 / 3.0) * g2 * ad ** 1.5)
        hs_ = (mw / K) ** 2
        lo = hp <= hs_
        es = np.where(lo, (2.0 / 3.0) * K * hp ** 1.5,
                      (2.0 / 3.0) * K * hs_ ** 1.5 + mw * (hp - hs_))
        return e + es.sum()

    S0 = sp.csc_matrix((np.ones(len(allr)), (allr, allc)), shape=(NF, NF))
    S0.sum_duplicates(); S0.sort_indices()
    c_ind, c_ptr = S0.indices.copy(), S0.indptr.copy()
    pos = np.array([c_ptr[c] + np.searchsorted(c_ind[c_ptr[c]:c_ptr[c + 1]], r) for r, c in zip(allr, allc)], dtype=np.int64)
    nnz = len(c_ind)
    LU = [None]

    def solve(h, mw, dp):
        h = h.copy()
        h[pl] = dp
        rprev = None
        refac = LU[0] is None
        for it in range(200):
            d, ad, m, hp, ms = flows(h, mw)
            # gradient = outflow - inflow + draw
            gr = np.bincount(pu, m, N) - np.bincount(pv, m, N) + np.bincount(sn, ms, N)
            gF = gr[free]
            rn = np.max(np.abs(gF))
            tot = max(1.0, ms.sum())
            if rn < 1e-11 * tot or (rn < 1e-8 * tot and rprev is not None and rn > 0.5 * rprev):
                break
            if rprev is not None and rn > 0.1 * rprev:
                refac = True
            rprev = rn
            dd = 0.5 * g2 / np.sqrt(np.maximum(ad, 1e-9))
            sat = K * np.sqrt(hp) >= mw
            hsub = np.where((hp > 0) & ~sat, 0.5 * K / np.sqrt(np.maximum(hp, 1e-12)), 0.0)
            diag = np.zeros(N)
            diag += np.bincount(sn, hsub, N)
            dsub = diag[free]
            val = np.concatenate([np.concatenate([dd, dd, dd, dd])[keep] * hs, dsub])
            if refac or it >= 150:
                Hm = sp.csc_matrix((np.bincount(pos, val, nnz), c_ind, c_ptr), shape=(NF, NF))
                LU[0] = splu(Hm, permc_spec='MMD_AT_PLUS_A', options=dict(SymmetricMode=True))
                refac = False
            step = LU[0].solve(-gF)
            d0 = gF @ step
            if not d0 < 0:
                step = -gF / np.maximum(np.concatenate([np.bincount(pu, dd, N) + np.bincount(pv, dd, N)])[free] + dsub, 1e-30)
                d0 = gF @ step

            def dphi(a):
                hn = h.copy(); hn[free] += a * step
                _, _, m2, _, ms2 = flows(hn, mw)
                g = (np.bincount(pu, m2, N) - np.bincount(pv, m2, N) + np.bincount(sn, ms2, N))[free]
                return g @ step, hn
            d1, hn = dphi(1.0)
            if d1 > 0.5 * abs(d0):
                lo_a, hi_a, dlo, dhi = 0.0, 1.0, d0, d1
                for _ in range(60):
                    a = hi_a - dhi * (hi_a - lo_a) / (dhi - dlo)
                    if not (lo_a + 0.01 * (hi_a - lo_a) < a < hi_a - 0.01 * (hi_a - lo_a)):
                        a = 0.5 * (lo_a + hi_a)
                    da, hn = dphi(a)
                    if abs(da) <= 0.5 * abs(d0):
                        break
                    if da < 0:
                        lo_a, dlo = a, da
                    else:
                        hi_a, dhi = a, da
            h = hn
        return h, m, ms

    # ---------- transport buffers ----------
    PP = 2 * P
    L = 2 * nsteps + 4
    c0 = nsteps + 2
    X = np.zeros((PP, L))
    W = np.zeros((PP, L))
    VV = np.concatenate([VOL, VOL])
    TT = np.concatenate([TAU, TAU])
    fu = np.concatenate([pu, pu])
    fv = np.concatenate([pv, pv])
    X[:, c0] = 0.0
    X[:, c0 + 1] = VV
    W[:, c0] = 0.0
    W[:, c0 + 1] = (Tpipe0 - Tg) * VV  # density * exp(0)
    lo = np.full(PP, c0)
    hi = np.full(PP, c0 + 1)
    ar = np.arange(PP)

    def Wat(rows_, x):
        a = lo[rows_].copy(); b = hi[rows_].copy()
        while True:
            act = b - a > 1
            if not act.any():
                break
            mid = (a + b) // 2
            cond = X[rows_, mid] <= x
            a = np.where(act & cond, mid, a)
            b = np.where(act & ~cond, mid, b)
        xa = X[rows_, a]; xb = X[rows_, a + 1]
        wa = W[rows_, a]; wb = W[rows_, a + 1]
        span = xb - xa
        f = np.where(span > 0, (x - xa) / np.where(span > 0, span, 1.0), 0.0)
        f = np.clip(f, 0.0, 1.0)
        return a, wa + f * (wb - wa)

    # results bookkeeping
    pts = pd.read_csv(os.path.join(pkg, 'points.csv'))
    pts['item'] = pts['item'].astype(str)
    hrs = pts['time_h'].round().astype(int).to_numpy()
    Hmax = int(round(hours))
    supT = np.full((Hmax + 1, N), np.nan)
    heatH = np.zeros((Hmax + 1, S))
    retT = np.full(Hmax + 1, np.nan)

    h = np.zeros(N)
    h[:] = DP[0] * 0.5
    for k in range(1, nsteps + 1):
        t = tk[k]
        mw = Q[k - 1] / (C * (Tn_s[sn] - Tr))
        h, m, ms = solve(h, mw, DP[k - 1])
        d = h[pu] - h[pv]
        m = np.sign(d) * g2 * np.sqrt(np.abs(d))
        q = np.concatenate([m, -m]) * DT / RHO  # signed volume along from->to
        # outflows
        fw = np.nonzero(q > 0)[0]
        bw = np.nonzero(q < 0)[0]
        inflow_v = np.zeros(2 * N)
        inflow_e = np.zeros(2 * N)
        ret_off = np.where(ar >= P, N, 0)
        outn = np.empty(0, int)
        for rows_, isf in ((fw, True), (bw, False)):
            if len(rows_) == 0:
                continue
            qa = np.abs(q[rows_])
            xl = X[rows_, lo[rows_]]; xr = X[rows_, hi[rows_]]
            if isf:
                x1 = xr - qa
                a, w1 = Wat(rows_, x1)
                integ = W[rows_, hi[rows_]] - w1
                hi[rows_] = a + 1
                X[rows_, a + 1] = x1; W[rows_, a + 1] = w1
                node = fv[rows_]
            else:
                x2 = xl + qa
                a, w2 = Wat(rows_, x2)
                integ = w2 - W[rows_, lo[rows_]]
                lo[rows_] = a
                X[rows_, a] = x2; W[rows_, a] = w2
                node = fu[rows_]
            E = Tg * qa + np.exp(-t / TT[rows_]) * integ
            nn = node + ret_off[rows_]
            inflow_v += np.bincount(nn, qa, 2 * N)
            inflow_e += np.bincount(nn, E, 2 * N)
        # supply mixing
        vs = inflow_v[:N].copy(); es = inflow_e[:N].copy()
        # plant: adds what network takes from supply node
        take = np.sum(np.where(pu == pl, np.maximum(m, 0), 0)) + np.sum(np.where(pv == pl, np.maximum(-m, 0), 0)) \
            + ms[sn == pl].sum()
        take -= np.sum(np.where(pu == pl, np.maximum(-m, 0), 0)) + np.sum(np.where(pv == pl, np.maximum(m, 0), 0))
        take = max(take, 0.0)
        vp = take * DT / RHO
        vs[pl] += vp; es[pl] += vp * Tsup_pl[k - 1]
        nz = vs > 0
        Tn_s = np.where(nz, es / np.where(nz, vs, 1.0), Tn_s)
        # substations
        heat = ms * C * (Tn_s[sn] - Tr)
        # return mixing
        vr = inflow_v[N:] + np.bincount(sn, ms * DT / RHO, N)
        er = inflow_e[N:] + np.bincount(sn, ms * DT / RHO * Tr, N)
        nz = vr > 0
        Tn_r = np.where(nz, er / np.where(nz, vr, 1.0), Tn_r)
        # inflows into pipes at t_k
        Tnode_all = np.concatenate([Tn_s, Tn_r])
        for rows_, isf in ((fw, True), (bw, False)):
            if len(rows_) == 0:
                continue
            qa = np.abs(q[rows_])
            dens = 0.0
            if isf:
                src = fu[rows_] + ret_off[rows_]
                dens = (Tnode_all[src] - Tg) * np.exp(t / TT[rows_])
                l0 = lo[rows_]
                X[rows_, l0 - 1] = X[rows_, l0] - qa
                W[rows_, l0 - 1] = W[rows_, l0] - dens * qa
                lo[rows_] = l0 - 1
            else:
                src = fv[rows_] + ret_off[rows_]
                dens = (Tnode_all[src] - Tg) * np.exp(t / TT[rows_])
                h0 = hi[rows_]
                X[rows_, h0 + 1] = X[rows_, h0] + qa
                W[rows_, h0 + 1] = W[rows_, h0] + dens * qa
                hi[rows_] = h0 + 1
        hour = (k - 1) // 30 + 1
        heatH[hour] += heat / 30.0
        if k % 30 == 0:
            supT[hour] = Tn_s
            retT[hour] = Tn_r[pl]

    vals = []
    for (pt, th, item, qty), H in zip(pts[['point', 'time_h', 'item', 'quantity']].itertuples(index=False), hrs):
        if qty == 'supply_C':
            v = supT[H, sn[sidx[item]]]
        elif qty == 'heat_kW':
            v = heatH[H, sidx[item]]
        else:
            v = retT[H]
        vals.append('%s,%.9f' % (pt, v))
    with open(out, 'w') as f:
        f.write('point,value\n' + '\n'.join(vals) + '\n')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
