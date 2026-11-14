#!/usr/bin/env python3
"""HN-3 calculation of supply temperatures and delivered heat for one package.

Usage: python3 heatnet.py PACKAGE_DIR OUT_CSV
"""
import sys, os, json, math
import numpy as np
import pandas as pd
import scipy.sparse as sp
import scipy.sparse.linalg as spla

RHO = 975.0
CP = 4.19
DT = 120.0
DTH = DT / 3600.0

CAL_R = os.environ.get("HN_CAL_R", "1") == "1"
CAL_TR = os.environ.get("HN_CAL_TR", "1") == "1"


def load(pkg):
    P = {}
    P['net'] = json.load(open(os.path.join(pkg, 'network.json')))
    rd = lambda f: pd.read_csv(os.path.join(pkg, f))
    P['nodes'] = rd('nodes.csv')
    P['pipes'] = rd('pipes.csv')
    P['subs'] = rd('substations.csv')
    P['demand'] = rd('demand.csv')
    P['plant'] = rd('plant.csv')
    P['initial'] = rd('initial.csv')
    P['meters'] = rd('meters.csv')
    P['survey'] = rd('pressure_survey.csv')
    P['points'] = rd('points.csv')
    return P


class Hydraulics:
    """Newton (global gradient) solution of section 3: pipe flows and node pressures.

    Supply and return pressure drops are equal, so with the plant supply pressure at dp0/2 and
    each return pressure equal to minus the supply pressure, dp at a node is twice its supply
    pressure.
    """

    def __init__(self, nn, pu, pv, R, plant, snode, K):
        self.nn = nn
        self.pu = pu
        self.pv = pv
        self.R = np.asarray(R, float)
        self.plant = plant
        self.snode = snode
        self.K = K
        free = np.ones(nn, bool)
        free[plant] = False
        self.free = np.nonzero(free)[0]
        nf = len(self.free)
        idx = -np.ones(nn, int)
        idx[self.free] = np.arange(nf)
        self.iu = idx[pu]
        self.iv = idx[pv]
        ne = len(pu)
        self.ne = ne
        A = sp.csr_matrix((np.r_[np.ones(ne), -np.ones(ne)],
                           (np.r_[np.arange(ne), np.arange(ne)], np.r_[pu, pv])), shape=(ne, nn))
        self.A = A
        self.Af = A[:, self.free].tocsr()
        self.AfT = self.Af.T.tocsr()
        self.a0 = np.asarray(A[:, plant].todense()).ravel()
        self.isub = idx[snode]
        sf = self.isub >= 0
        self.sf = sf
        # pattern
        rows = []; cols = []
        ok_u = self.iu >= 0; ok_v = self.iv >= 0; both = ok_u & ok_v
        e = np.arange(ne)
        # entries: (u,u) from pipes with u free, (v,v), (u,v),(v,u) for both
        r = np.r_[self.iu[ok_u], self.iv[ok_v], self.iu[both], self.iv[both], np.arange(nf)]
        c = np.r_[self.iu[ok_u], self.iv[ok_v], self.iv[both], self.iu[both], np.arange(nf)]
        self.e_uu = e[ok_u]; self.e_vv = e[ok_v]; self.e_b = e[both]
        pat = sp.csc_matrix((np.ones(len(r)), (r, c)), shape=(nf, nf))
        pat.sum_duplicates(); pat.sort_indices()
        self.pat = pat
        # map each entry to position in pat.data
        pos = {}
        indptr = pat.indptr; indices = pat.indices
        for col in range(nf):
            for q in range(indptr[col], indptr[col + 1]):
                pos[(indices[q], col)] = q
        self.map = np.array([pos[(ri, ci)] for ri, ci in zip(r.tolist(), c.tolist())], int)
        self.nnz = len(pat.data)
        self.nf = nf
        self.M = sp.csc_matrix((pat.data.copy(), pat.indices, pat.indptr), shape=(nf, nf))
        self.p = None
        self.q = None
        self.lu = None

    def solve(self, dp0, mw):
        R = self.R; K = self.K
        p0 = dp0 / 2.0
        nf = self.nf
        if self.p is None:
            pf = np.full(nf, p0 * 0.9)
            q = np.full(self.ne, 0.1)
        else:
            pf = self.pf.copy(); q = self.q.copy()
        isub = self.isub; sf = self.sf
        isf = isub[sf]; Ksf = K[sf]
        Af = self.Af; AfT = self.AfT
        a0p = self.a0 * p0
        M = self.M
        mp = self.map; nnz = self.nnz
        eu = self.e_uu; ev = self.e_vv; eb = self.e_b
        mwf = mw[sf]
        pf0 = pf; q0 = q
        prev = None
        full = True
        for it in range(80):
            pos = np.maximum(pf[isf], 0.0)
            cap = Ksf * np.sqrt(2.0 * pos)
            lim = cap < mwf
            draw = np.where(lim, cap, mwf)
            aq = np.abs(q)
            Gi = 0.5 / (R * np.maximum(aq, 1e-5))
            r1 = R * q * aq - (Af @ pf + a0p)
            r2 = AfT @ q + np.bincount(isf, draw, nf)
            if full:
                dd = np.where(lim, Ksf / np.sqrt(2.0 * np.maximum(pos, 1.0)), 0.0)
                gb = -Gi[eb]
                vals = np.concatenate((Gi[eu], Gi[ev], gb, gb, np.bincount(isf, dd, nf) + 1e-14))
                M.data = np.bincount(mp, vals, nnz)
                self.lu = spla.splu(M, permc_spec='MMD_AT_PLUS_A')
            dp = self.lu.solve(AfT @ (Gi * r1) - r2)
            dq = Gi * (Af @ dp - r1)
            sdq = np.max(np.abs(dq)); sdp = np.max(np.abs(dp))
            if not full and (it >= 4 or (prev is not None and sdq > 0.3 * prev)
                             or not np.isfinite(sdq)):
                # stale factorisation not contracting: restart with full Newton
                full = True
                pf = pf0; q = q0; prev = None
                continue
            pf = pf + dp
            q = q + dq
            if sdq < 3e-4 and sdp < 20.0:
                break
            prev = sdq
        self.pf = pf; self.q = q; self.p = True
        pfull_s = np.where(sf, pf[np.maximum(isub, 0)], p0)
        pos = np.maximum(pfull_s, 0.0)
        draw = np.minimum(K * np.sqrt(2.0 * pos), mw)
        self.iters = it
        self.dps = 2.0 * pos
        return q, draw


def find_bridges(nn, pu, pv, root):
    """Return (is_bridge, parent_is_from) using an iterative DFS from the plant."""
    ne = len(pu)
    adj = [[] for _ in range(nn)]
    for e in range(ne):
        adj[pu[e]].append((pv[e], e))
        adj[pv[e]].append((pu[e], e))
    disc = [-1] * nn
    low = [0] * nn
    is_bridge = np.zeros(ne, bool)
    from_parent = np.ones(ne, bool)
    t = 0
    disc[root] = low[root] = 0
    t = 1
    stack = [(root, -1, iter(adj[root]))]
    while stack:
        u, pe, it = stack[-1]
        adv = False
        for v, e in it:
            if e == pe:
                continue
            if disc[v] < 0:
                disc[v] = low[v] = t
                t += 1
                from_parent[e] = (pu[e] == u)
                stack.append((v, e, iter(adj[v])))
                adv = True
                break
            else:
                low[u] = min(low[u], disc[v])
        if not adv:
            stack.pop()
            if stack:
                w = stack[-1][0]
                low[w] = min(low[w], low[u])
                if low[u] > disc[w]:
                    is_bridge[pe] = True
    return is_bridge, from_parent


def run(P, R, Tr, nsteps_limit=None, Kv=None):
    net = P['net']
    nodes = list(P['nodes']['node'])
    nid = {n: i for i, n in enumerate(nodes)}
    nn = len(nodes)
    pipes = P['pipes']
    ne = len(pipes)
    pu = pipes['from_node'].map(nid).values
    pv = pipes['to_node'].map(nid).values
    vol = pipes['volume_m3'].values.astype(float)
    tau = pipes['loss_time_h'].values.astype(float)
    subs = P['subs']
    ns = len(subs)
    sid = {s: i for i, s in enumerate(subs['substation'])}
    snode = subs['node'].map(nid).values
    K = subs['valve_capacity'].values.astype(float) if Kv is None else np.asarray(Kv, float)
    Tr = np.asarray(Tr, float)
    plant = nid[net['plant_node']]
    Tg = float(net['ground_C'])
    hours = float(net['hours'])
    nsteps = int(round(hours * 3600 / DT))
    if nsteps_limit is not None:
        nsteps = min(nsteps, nsteps_limit)

    dem = P['demand']
    times = np.arange(nsteps) * DTH
    Qs = np.zeros((nsteps, ns))
    for s, g in dem.groupby('substation'):
        g = g.sort_values('time_h')
        ii = np.searchsorted(g['time_h'].values, times + 1e-9, side='right') - 1
        Qs[:, sid[s]] = g['heat_kW'].values[np.maximum(ii, 0)]
    pl = P['plant'].sort_values('time_h')
    ii = np.maximum(np.searchsorted(pl['time_h'].values, times + 1e-9, side='right') - 1, 0)
    Tsup = pl['supply_C'].values[ii]
    DP = pl['dp_Pa'].values[ii]

    ini = P['initial']
    Tn_s = np.zeros(nn); Tn_r = np.zeros(nn)
    Tp_s = np.zeros(ne); Tp_r = np.zeros(ne)
    pidx = {p: i for i, p in enumerate(pipes['pipe'])}
    for kind, name, nw, T in ini[['kind', 'name', 'network', 'temp_C']].itertuples(index=False):
        if kind == 'node':
            (Tn_s if nw == 'supply' else Tn_r)[nid[name]] = T
        else:
            (Tp_s if nw == 'supply' else Tp_r)[pidx[name]] = T

    isb, frp = find_bridges(nn, pu, pv, plant)
    B = np.nonzero(isb)[0]
    L = np.nonzero(~isb)[0]
    nb = len(B)
    sgnB = np.where(frp[B], 1.0, -1.0)
    parB = np.where(frp[B], pu[B], pv[B])
    chB = np.where(frp[B], pv[B], pu[B])
    volB = vol[B]
    tauB = tau[B]
    # history arrays: index 0 sentinel, 1 initial plug, k+1 entry of step k
    W = nsteps + 2
    rows = np.arange(nb)
    hist = {}
    for key, T0 in (('s', Tp_s[B]), ('r', Tp_r[B])):
        C = np.zeros((nb, W)); I = np.zeros((nb, W)); A = np.zeros((nb, W))
        C[:, 0] = -volB
        A[:, 1] = T0 - Tg
        I[:, 1] = (T0 - Tg) * volB
        hist[key] = dict(C=C, I=I, A=A, ptr=np.ones(nb, int), x=-volB.copy(), F=np.zeros(nb))

    from collections import deque
    Ll = L.tolist()
    cs = {j: deque([[vol[j], Tp_s[j] - Tg]]) for j in Ll}
    cr = {j: deque([[vol[j], Tp_r[j] - Tg]]) for j in Ll}

    hyd = Hydraulics(nn, pu, pv, R, plant, snode, K)
    rec_Ts = np.zeros((nsteps + 1, ns))
    rec_Tr = np.zeros((nsteps + 1, ns))
    rec_E = np.zeros((nsteps + 1, ns))
    rec_Tpl = np.zeros(nsteps + 1)
    rec_m = np.zeros((nsteps + 1, ns))
    rec_lim = np.zeros((nsteps + 1, ns), bool)
    rec_dp = np.zeros((nsteps + 1, ns))
    rec_Tprev = np.zeros((nsteps + 1, ns))
    rec_Q = np.zeros((nsteps + 1, ns))
    rec_Ts[0] = Tn_s[snode]
    rec_Tr[0] = Tn_r[snode]
    rec_Tpl[0] = Tn_r[plant]
    sub_at_plant = snode == plant
    mTr_dummy = None

    def bridge_out(h, V, k):
        C = h['C']; I = h['I']; A = h['A']; ptr = h['ptr']
        x = h['x'] + V
        while True:
            msk = (C[rows, ptr] < x) & (ptr < k)
            if not msk.any():
                break
            ptr[msk] += 1
        F = I[rows, ptr - 1] + A[rows, ptr] * (x - C[rows, ptr - 1])
        with np.errstate(invalid='ignore', divide='ignore'):
            avg = np.where(V > 0, (F - h['F']) / np.where(V > 0, V, 1.0), 0.0)
        h['x'] = x; h['F'] = F
        return avg

    def bridge_in(h, V, Ain, k):
        C = h['C']; I = h['I']; A = h['A']
        C[:, k + 1] = C[:, k] + V
        A[:, k + 1] = Ain
        I[:, k + 1] = I[:, k] + Ain * V

    for k in range(1, nsteps + 1):
        tk = k * DTH
        Tn_sub_prev = Tn_s[snode]
        dT = Tn_sub_prev - Tr
        mw = Qs[k - 1] / (CP * np.maximum(dT, 1e-6))
        q, m = hyd.solve(DP[k - 1], mw)
        aq = np.abs(q)
        fw = q > 0
        ef = np.exp(tk / tau)
        outs = np.zeros(ne); outr = np.zeros(ne)
        # bridges
        qB = np.maximum(q[B] * sgnB, 0.0)
        VB = qB * DT / RHO
        if nb:
            outs[B] = Tg + bridge_out(hist['s'], VB, k) / ef[B]
            outr[B] = Tg + bridge_out(hist['r'], VB, k) / ef[B]
        # loop pipes
        V = aq * DT / RHO
        Vl = V.tolist(); fwl = fw.tolist(); efl = ef.tolist()
        for j in Ll:
            Vj = Vl[j]
            if Vj <= 0.0:
                continue
            f = fwl[j]
            for c, right, outl in ((cs[j], f, outs), (cr[j], not f, outr)):
                rem = Vj; acc = 0.0
                if right:
                    while rem > 1e-15 and c:
                        seg = c[-1]
                        if seg[0] <= rem:
                            acc += seg[0] * seg[1]; rem -= seg[0]; c.pop()
                        else:
                            acc += rem * seg[1]; seg[0] -= rem; rem = 0.0
                else:
                    while rem > 1e-15 and c:
                        seg = c[0]
                        if seg[0] <= rem:
                            acc += seg[0] * seg[1]; rem -= seg[0]; c.popleft()
                        else:
                            acc += rem * seg[1]; seg[0] -= rem; rem = 0.0
                used = Vj - rem
                if used > 0:
                    outl[j] = Tg + acc / used / efl[j]
                else:
                    outl[j] = Tg + c[0][1] / efl[j] if c else Tg
        sout = np.where(fw, pv, pu)
        sinn = np.where(fw, pu, pv)
        sin_m = np.bincount(sout, aq, nn)
        sin_h = np.bincount(sout, aq * outs, nn)
        tot = m[sub_at_plant].sum() + aq[sinn == plant].sum()
        sin_m[plant] += tot
        sin_h[plant] += tot * Tsup[k - 1]
        has = sin_m > 0
        Tn_s = np.where(has, sin_h / np.where(has, sin_m, 1), Tn_s)
        rin_m = np.bincount(sinn, aq, nn) + np.bincount(snode, m, nn)
        rin_h = np.bincount(sinn, aq * outr, nn) + np.bincount(snode, m * Tr, nn)
        hasr = rin_m > 0
        Tn_r = np.where(hasr, rin_h / np.where(hasr, rin_m, 1), Tn_r)
        # inflows
        if nb:
            bridge_in(hist['s'], VB, (Tn_s[parB] - Tg) * ef[B], k)
            bridge_in(hist['r'], VB, (Tn_r[chB] - Tg) * ef[B], k)
        As = ((Tn_s[sinn] - Tg) * ef).tolist()
        Ar = ((Tn_r[sout] - Tg) * ef).tolist()
        for j in Ll:
            Vj = Vl[j]
            if Vj <= 0.0:
                continue
            if fwl[j]:
                cs[j].appendleft([Vj, As[j]]); cr[j].append([Vj, Ar[j]])
            else:
                cs[j].append([Vj, As[j]]); cr[j].appendleft([Vj, Ar[j]])
        Tsn = Tn_s[snode]
        rec_Ts[k] = Tsn
        rec_Tr[k] = Tn_r[snode]
        rec_E[k] = m * CP * (Tsn - Tr) * DT
        rec_m[k] = m
        rec_lim[k] = m < mw * (1 - 1e-9)
        rec_dp[k] = hyd.dps
        rec_Q[k] = Qs[k - 1]
        rec_Tprev[k] = Tn_sub_prev
        rec_Tpl[k] = Tn_r[plant]
    return dict(Ts=rec_Ts, Tr=rec_Tr, E=rec_E, Tpl=rec_Tpl, m=rec_m, lim=rec_lim, dp=rec_dp, Q=rec_Q, Tprev=rec_Tprev, sid=sid, nsteps=nsteps,
                nloop=len(L))


def survey_model(P, R):
    nodes = list(P['nodes']['node'])
    nid = {n: i for i, n in enumerate(nodes)}
    pp = P['pipes']
    subs = P['subs']
    sv = P['survey'].set_index('item')
    snode = subs['node'].map(nid).values
    fl = sv.loc[subs['substation'], 'flow_kg_s'].values.astype(float)
    obs = sv.loc[subs['substation'], 'dp_Pa'].values.astype(float)
    dp0 = float(sv.loc['plant', 'dp_Pa'])
    hy = Hydraulics(len(nodes), pp['from_node'].map(nid).values, pp['to_node'].map(nid).values,
                    R, nid[P['net']['plant_node']], snode, np.full(len(snode), 1e9))
    return hy, fl, obs, dp0, snode


def survey_eval(hy, R, fl, dp0):
    hy.R = np.asarray(R, float)
    hy.p = None
    hy.lu = None
    hy.pf_prev = None
    q, m = hy.solve(dp0, fl)
    for _ in range(3):
        q, m = hy.solve(dp0, fl)
    ps = np.where(hy.sf, hy.pf[np.maximum(hy.isub, 0)], dp0 / 2)
    return 2 * ps, q


def survey_jac(hy, R, q):
    """d(dp at substation nodes)/dR for every pipe, linearised at the solution."""
    aq = np.maximum(np.abs(q), 1e-5)
    Gi = 0.5 / (R * aq)
    nf = hy.nf
    vals = np.concatenate((Gi[hy.e_uu], Gi[hy.e_vv], -Gi[hy.e_b], -Gi[hy.e_b], np.full(nf, 1e-14)))
    M = sp.csc_matrix((np.bincount(hy.map, vals, hy.nnz), hy.pat.indices, hy.pat.indptr), shape=(nf, nf))
    lu = spla.splu(M)
    rhs = (hy.AfT @ sp.diags(Gi * q * np.abs(q))).toarray()
    X = lu.solve(rhs)
    J = np.zeros((len(hy.isub), len(R)))
    J[hy.sf] = 2 * X[hy.isub[hy.sf]]
    return J


def calibrate_R(P, log=None):
    """Find pipes whose resistance differs from the laid value, from the pressure survey."""
    R = P['pipes']['resistance_Pa_s2_kg2'].values.astype(float).copy()
    hy, fl, obs, dp0, snode = survey_model(P, R)
    pred, q = survey_eval(hy, R, fl, dp0)
    r = obs - pred
    chosen = []
    for rnd in range(12):
        if np.max(np.abs(r)) < 450:
            break
        J = survey_jac(hy, R, q)
        nrm = np.sum(J * J, 0)
        ok = nrm > 1e-12
        c = J.T @ r
        gain = np.where(ok, c * c / np.where(ok, nrm, 1), -1)
        # candidates must keep R positive
        dR = np.where(ok, c / np.where(ok, nrm, 1), 0)
        gain = np.where(R + dR > 0.02 * R, gain, -1)
        e = int(np.argmax(gain))
        if gain[e] <= 0:
            break
        if e not in chosen:
            chosen.append(e)
        # Gauss-Newton on the chosen set
        for gn in range(8):
            Jc = J[:, chosen]
            step, *_ = np.linalg.lstsq(Jc, r, rcond=None)
            Rn = R.copy()
            Rn[chosen] = np.maximum(R[chosen] + step, 0.02 * R[chosen])
            predn, qn = survey_eval(hy, Rn, fl, dp0)
            rn = obs - predn
            R, q, r = Rn, qn, rn
            if np.max(np.abs(step / R[chosen])) < 1e-4:
                break
            J = survey_jac(hy, R, q)
        if log is not None:
            log.append((rnd, [P['pipes']['pipe'][i] for i in chosen], np.max(np.abs(r))))
    return R


def _meter_model(Tr, K, Q, Tp, Ts, dp):
    """Metered energy (kJ) and mass (kg) over the series, flows as in section 3."""
    mw = Q / (CP * np.maximum(Tp - Tr, 1e-3))
    m = np.minimum(mw, K * np.sqrt(np.maximum(dp, 0.0)))
    return (m * CP * (Ts - Tr)).sum(0) * DT, m.sum(0) * DT


def _fit_one(Q, Tp, Ts, dp, Em, Mm, Tr0, K0, fitK):
    """Fit Tr (and K if fitK) of substations, holding their node series fixed."""
    n = Q.shape[1]

    def tr_for(K):
        lo = np.full(n, -50.0); hi = np.min(Tp, 0) - 0.5
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            _, M = _meter_model(mid, K, Q, Tp, Ts, dp)
            big = M > Mm
            hi = np.where(big, mid, hi); lo = np.where(big, lo, mid)
        return 0.5 * (lo + hi)

    if not fitK:
        return tr_for(K0), K0
    lo = np.log(K0) - 4; hi = np.log(K0) + 4
    for _ in range(50):
        mid = 0.5 * (lo + hi)
        Kc = np.exp(mid)
        Trc = tr_for(Kc)
        E, _ = _meter_model(Trc, Kc, Q, Tp, Ts, dp)
        big = E > Em
        hi = np.where(big, mid, hi); lo = np.where(big, lo, mid)
    Kc = np.exp(0.5 * (lo + hi))
    return tr_for(Kc), Kc


def calibrate_Tr(P, R, log=None, first=None):
    """Return temperatures (and, where needed, valve capacities) from the 24-hour meters."""
    subs = P['subs']
    Tr = subs['return_C'].values.astype(float).copy()
    K = subs['valve_capacity'].values.astype(float).copy()
    me = P['meters'].set_index('substation').loc[subs['substation']]
    Em = me['energy_kWh'].values.astype(float) * 3600.0  # kJ
    Mm = me['volume_m3'].values.astype(float) * RHO      # kg
    spm = int(round(3600 / DT))
    n24 = min(24 * spm, int(round(float(P['net']['hours']) * spm)))
    fixT = np.zeros(len(Tr), bool)
    fixK = np.zeros(len(Tr), bool)
    tried = np.zeros(len(Tr), bool)
    for it in range(8):
        res = first if (it == 0 and first is not None) else run(P, R, Tr, n24, K)
        sl = slice(1, n24 + 1)
        Emod = res['E'][sl].sum(0)
        Mmod = res['m'][sl].sum(0) * DT
        rv = Mmod / Mm - 1
        re = Emod / Em - 1
        fT = (np.abs(rv) > 0.006) | (fixT & (np.abs(rv) > 0.001))
        fK = (np.abs(re) > 0.006) | (fixK & (np.abs(re) > 0.001))
        if log is not None:
            log.append(('meters', it, int(fT.sum()), int(fK.sum()),
                        float(np.max(np.abs(rv))), float(np.max(np.abs(re)))))
        if not (fT.any() or fK.any()):
            if it == 0:
                return None
            break
        # first try a return temperature alone; a valve capacity only where that is not enough
        fixK |= fK & fixT & tried
        fixT |= fT | fK
        tried = fixT.copy()
        idx = np.nonzero(fixT)[0]
        Q = res['Q'][sl][:, idx]; Tp = res['Tprev'][sl][:, idx]
        Ts = res['Ts'][sl][:, idx]; dp = res['dp'][sl][:, idx]
        kk = fixK[idx]
        if (~kk).any():
            j = idx[~kk]
            t, _ = _fit_one(Q[:, ~kk], Tp[:, ~kk], Ts[:, ~kk], dp[:, ~kk], Em[j], Mm[j], Tr[j], K[j], False)
            Tr[j] = t
        if kk.any():
            j = idx[kk]
            t, kv = _fit_one(Q[:, kk], Tp[:, kk], Ts[:, kk], dp[:, kk], Em[j], Mm[j], Tr[j], K[j], True)
            Tr[j] = t; K[j] = kv
    return Tr, K


LOG = []


def main():
    pkg, out = sys.argv[1], sys.argv[2]
    P = load(pkg)
    R = P['pipes']['resistance_Pa_s2_kg2'].values.astype(float)
    if CAL_R:
        try:
            Rc = calibrate_R(P, LOG)
            if np.all(np.isfinite(Rc)) and np.all(Rc > 0):
                R = Rc
        except Exception as ex:  # keep the laid resistances
            LOG.append(('calR failed', repr(ex)))
    Tr = P['subs']['return_C'].values.astype(float)
    Kv = None
    if CAL_TR:
        try:
            cal = calibrate_Tr(P, R, LOG)
        except Exception as ex:
            cal = None
            LOG.append(('calTr failed', repr(ex)))
        if cal is not None and np.all(np.isfinite(cal[0])) and np.all(np.isfinite(cal[1])):
            Tr, Kv = cal
    res = run(P, R, Tr, None, Kv)
    sid = res['sid']
    spm = int(round(3600 / DT))
    pts = P['points']
    vals = []
    for pt, t, item, qn in pts[['point', 'time_h', 'item', 'quantity']].itertuples(index=False):
        k = int(round(t * spm))
        if item == 'plant':
            v = res['Tpl'][k]
        else:
            i = sid[item]
            if qn == 'supply_C':
                v = res['Ts'][k, i]
            elif qn == 'return_C':
                v = res['Tr'][k, i]
            else:
                v = res['E'][max(1, k - spm + 1):k + 1, i].sum() / 3600.0
        vals.append(v)
    pd.DataFrame({'point': pts['point'], 'value': vals}).to_csv(out, index=False, float_format='%.6f')
    if os.environ.get('HN_LOG'):
        print(LOG, file=sys.stderr)


if __name__ == '__main__':
    main()
