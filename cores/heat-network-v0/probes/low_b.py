#!/usr/bin/env python3
"""HN-3 calculation of supply temperatures and delivered heat for one package.

Usage: python3 heatnet.py PACKAGE_DIR OUT_CSV
"""
import sys
import os
import json
import numpy as np
import pandas as pd
import scipy.sparse as sp
from scipy.sparse.linalg import splu

RHO = 975.0
CP = 4.19
DT = 120.0  # s
DTH = DT / 3600.0


class Plug:
    """Plug-flow contents of a set of pipes (one network), vectorised.

    Each pipe row holds sorted breakpoints s (a lagrangian volume coordinate)
    and the prefix integral I of B over s, where B = (T0-Tg)*exp(t0/tau) is
    constant within a parcel, so that the temperature at time t of a parcel is
    Tg + B exp(-t/tau) and volume averages are linear in B. The pipe contents
    are exactly [s[h], s[t]]; the s[h] end is the pipe's from_node end.
    """

    def __init__(self, V, tau_h, T_init, Tg, W=64):
        n = len(V)
        self.n = n
        self.V = V.astype(float)
        self.tau = tau_h.astype(float)
        self.Tg = Tg
        self.W = W
        self.s = np.zeros((n, W))
        self.I = np.zeros((n, W))
        mid = W // 2
        self.h = np.full(n, mid, dtype=np.int64)
        self.t = np.full(n, mid + 1, dtype=np.int64)
        r = np.arange(n)
        self.s[r, mid + 1] = self.V
        self.I[r, mid + 1] = (np.asarray(T_init, float) - Tg) * self.V
        self.rows = r

    def outflow(self, q, t_end_h):
        """Remove the volume |q| at the outlet end (q > 0: flow from_node->to_node).
        Return the mean outflow temperature evaluated at t_end."""
        n = self.n
        Tout = np.full(n, self.Tg)
        s = self.s
        I = self.I
        fwd = np.nonzero(q > 0)[0]
        rev = np.nonzero(q < 0)[0]
        Bm = np.zeros(n)
        if len(fwd):
            r = fwd
            aq = q[r]
            t = self.t[r]
            h = self.h[r]
            cut = s[r, t] - aq
            j = t - 1
            for _ in range(6):
                mv = (s[r, j] > cut) & (j > h)
                if not mv.any():
                    break
                j = j - mv
            else:
                mv = (s[r, j] > cut) & (j > h)
                for ii in np.nonzero(mv)[0]:
                    ri = r[ii]
                    seg = s[ri, h[ii]:t[ii]]
                    j[ii] = h[ii] + max(np.searchsorted(seg, cut[ii], side='right') - 1, 0)
            s0 = s[r, j]
            s1 = s[r, j + 1]
            i0 = I[r, j]
            i1 = I[r, j + 1]
            d = s1 - s0
            f = np.where(d > 0, (cut - s0) / np.where(d > 0, d, 1.0), 0.0)
            Ic = i0 + f * (i1 - i0)
            Bm[r] = (I[r, t] - Ic) / aq
            nt = j + 1
            s[r, nt] = cut
            I[r, nt] = Ic
            self.t[r] = nt
        if len(rev):
            r = rev
            aq = -q[r]
            t = self.t[r]
            h = self.h[r]
            cut = s[r, h] + aq
            j = h + 1
            for _ in range(6):
                mv = (s[r, j] < cut) & (j < t)
                if not mv.any():
                    break
                j = j + mv
            else:
                mv = (s[r, j] < cut) & (j < t)
                for ii in np.nonzero(mv)[0]:
                    ri = r[ii]
                    seg = s[ri, h[ii] + 1:t[ii] + 1]
                    j[ii] = h[ii] + 1 + min(np.searchsorted(seg, cut[ii], side='left'), len(seg) - 1)
            s0 = s[r, j - 1]
            s1 = s[r, j]
            i0 = I[r, j - 1]
            i1 = I[r, j]
            d = s1 - s0
            f = np.where(d > 0, (cut - s0) / np.where(d > 0, d, 1.0), 0.0)
            Ic = i0 + f * (i1 - i0)
            Bm[r] = (Ic - I[r, h]) / aq
            nh = j - 1
            s[r, nh] = cut
            I[r, nh] = Ic
            self.h[r] = nh
        nz = q != 0
        Tout[nz] = self.Tg + Bm[nz] * np.exp(-t_end_h / self.tau[nz])
        return Tout

    def push(self, q, Tin, t_end_h):
        """Water at Tin enters the inlet end at t_end, volume |q|."""
        fwd = np.nonzero(q > 0)[0]
        rev = np.nonzero(q < 0)[0]
        need = np.concatenate([fwd[self.h[fwd] < 1], rev[self.t[rev] > self.W - 2]])
        for i in need:
            self._compact_row(i)
        B = (Tin - self.Tg) * np.exp(t_end_h / self.tau)
        s = self.s
        I = self.I
        if len(fwd):
            r = fwd
            aq = q[r]
            h = self.h[r] - 1
            s[r, h] = s[r, h + 1] - aq
            I[r, h] = I[r, h + 1] - B[r] * aq
            self.h[r] = h
        if len(rev):
            r = rev
            aq = -q[r]
            t = self.t[r] + 1
            s[r, t] = s[r, t - 1] + aq
            I[r, t] = I[r, t - 1] + B[r] * aq
            self.t[r] = t

    def _compact_row(self, i):
        h, t = self.h[i], self.t[i]
        k = t - h + 1
        if k + 4 > self.W // 2:
            self._grow()
        W = self.W
        h, t = self.h[i], self.t[i]
        start = (W - k) // 2
        seg_s = self.s[i, h:t + 1].copy()
        seg_I = self.I[i, h:t + 1].copy()
        self.s[i, start:start + k] = seg_s
        self.I[i, start:start + k] = seg_I
        self.h[i] = start
        self.t[i] = start + k - 1

    def _grow(self):
        W2 = self.W * 2
        off = (W2 - self.W) // 2
        s2 = np.zeros((self.n, W2))
        I2 = np.zeros((self.n, W2))
        s2[:, off:off + self.W] = self.s
        I2[:, off:off + self.W] = self.I
        self.s, self.I = s2, I2
        self.h += off
        self.t += off
        self.W = W2


class Hyd:
    def __init__(self, Bm, free, plant_n, R2, sn, Kv, NN):
        self.Bm = Bm.tocsr()
        self.BmT = Bm.T.tocsr()
        self.free = free
        self.plant_n = plant_n
        self.R2 = R2
        self.sn = sn
        self.Kv = Kv
        self.NN = NN
        NP = Bm.shape[0]
        NS = len(sn)
        self.NS = NS
        Bf = Bm[:, free].tocsc()
        self.BfT = Bf.T.tocsr()
        NF = len(free)
        fmap = -np.ones(NN, dtype=np.int64)
        fmap[free] = np.arange(NF)
        self.fsn = fmap[sn]
        # M = Bf^T diag(gi) Bf + diag(dn); build the linear map [gi, dn] -> M.data
        rows, cols, src = [], [], []
        Bc = Bf.tocsr()
        for j in range(NP):
            lo, hi = Bc.indptr[j], Bc.indptr[j + 1]
            idx = Bc.indices[lo:hi]
            val = Bc.data[lo:hi]
            for a in range(len(idx)):
                for b in range(len(idx)):
                    rows.append(idx[a]); cols.append(idx[b]); src.append((j, val[a] * val[b]))
        for i in range(NF):
            rows.append(i); cols.append(i); src.append((NP + i, 1.0))
        rows = np.array(rows); cols = np.array(cols)
        srcj = np.array([s[0] for s in src]); srcv = np.array([s[1] for s in src])
        # unique (row, col) pairs -> CSC positions
        key = cols * NF + rows
        uk, inv = np.unique(key, return_inverse=True)
        self.ur = uk % NF
        self.uc = uk // NF
        self.T = sp.csr_matrix((srcv, (inv, srcj)), shape=(len(uk), NP + NF))
        M0 = sp.csc_matrix((np.ones(len(uk)), (self.ur, self.uc)), shape=(NF, NF))
        M0.sort_indices()
        # map positions: build ordering consistent with csc
        self.indptr = M0.indptr
        self.indices = M0.indices
        # uk sorted by (col,row) which is csc order
        self.NF = NF
        self.NP = NP
        self.K2 = np.maximum(Kv, 1e-300) ** 2
        self.Smat = sp.csr_matrix((np.ones(NS), (sn, np.arange(NS))), shape=(NN, NS))
        ok = self.fsn >= 0
        self.SmatF = sp.csr_matrix((np.ones(ok.sum()), (self.fsn[ok], np.arange(NS)[ok])), shape=(NF, NS))
        self.lu = None
        self.act_lu = None
        self.zero_prev = np.zeros(NS, dtype=bool)

    def assemble(self, gi, dn):
        data = self.T @ np.concatenate([gi, dn])
        return sp.csc_matrix((data, self.indices, self.indptr), shape=(self.NF, self.NF))


def solve_hyd(H, m, p, mw, dpP, lim):
    """Hydraulic state of HN-3 section 3 in terms of the supply-return pressure
    difference: pipes dp_u - dp_v = 2R m|m|; substations take min(m_want, K sqrt(dp)).
    Active-set iteration on which valves are limiting; inside it a (quasi-)Newton
    iteration of the global gradient algorithm, with valve-limited substations as
    elements s|s|/K^2 = dp. The factorisation is reused while it converges fast."""
    p = p.copy()
    p[H.plant_n] = dpP
    free = H.free
    sn = H.sn
    Kv = H.Kv
    K2 = H.K2
    s = np.where(lim, np.minimum(mw, Kv * np.sqrt(np.maximum(p[sn], 0.0))), mw)
    zero = H.zero_prev & lim
    act = lim & ~zero
    for outer in range(60):
        last_err = None
        slow = False
        nit = 0
        while True:
            nit += 1
            am = np.abs(m)
            r1 = H.R2 * am * m - H.Bm @ p
            asb = np.abs(s)
            rv = s * asb / K2 - p[sn]
            sf = np.where(act, s, np.where(zero, 0.0, mw))
            r2 = (H.BmT @ m + H.Smat @ sf)[free]
            refac = (H.lu is None or (H.act_lu != act).any() or
                     slow or nit > 30)
            if refac:
                g = 2.0 * H.R2 * np.maximum(am, 1e-8)
                H.gi = 1.0 / g
                gv = 2.0 * np.maximum(asb, 1e-8) / K2
                H.gvi = np.where(act, 1.0 / gv, 0.0)
                dn = H.SmatF @ H.gvi
                H.lu = splu(H.assemble(H.gi, dn), permc_spec='MMD_AT_PLUS_A')
                H.act_lu = act.copy()
                fresh = True
            else:
                fresh = False
            gi = H.gi
            gvi = H.gvi
            rhs = -r2 + H.BfT @ (gi * r1) + H.SmatF @ (gvi * rv)
            dpf = H.lu.solve(rhs)
            dpfull = np.zeros(H.NN)
            dpfull[free] = dpf
            dm = (H.Bm @ dpfull - r1) * gi
            ds = (dpfull[sn] - rv) * gvi
            p += dpfull
            m = m + dm
            s = np.where(act, s + ds, s)
            err = max(np.max(np.abs(dm)) if len(dm) else 0.0, np.max(np.abs(ds)) if len(ds) else 0.0)
            if err < 1e-11 * (1.0 + np.max(np.abs(m))):
                break
            if nit > 300:
                break
            slow = (not fresh) and last_err is not None and err > 0.2 * last_err
            last_err = err
        # active set check
        pp = p[sn]
        cap = Kv * np.sqrt(np.maximum(pp, 0.0))
        a1 = lim & ~zero & (s > mw)
        a2 = ~lim & (cap < mw)
        z_new = lim & (pp <= 0)
        if not (a1.any() or a2.any() or (z_new != zero).any()):
            break
        lim = (lim & ~a1) | a2
        s = np.where(a1, mw, s)
        s = np.where(a2, cap, s)
        zero = z_new & lim
        act = lim & ~zero
    H.zero_prev = zero
    msub = np.where(zero, 0.0, np.where(lim, np.minimum(mw, Kv * np.sqrt(np.maximum(p[sn], 0.0))), mw))
    return m, p, msub, lim


def main():
    pkg, out = sys.argv[1], sys.argv[2]
    net = json.load(open(os.path.join(pkg, 'network.json')))
    nodes = pd.read_csv(os.path.join(pkg, 'nodes.csv'), dtype={'node': str})['node'].tolist()
    pipes = pd.read_csv(os.path.join(pkg, 'pipes.csv'), dtype={'pipe': str, 'from_node': str, 'to_node': str})
    subs = pd.read_csv(os.path.join(pkg, 'substations.csv'), dtype={'substation': str, 'node': str})
    demand = pd.read_csv(os.path.join(pkg, 'demand.csv'), dtype={'substation': str})
    plant = pd.read_csv(os.path.join(pkg, 'plant.csv'))
    init = pd.read_csv(os.path.join(pkg, 'initial.csv'), dtype={'name': str})
    points = pd.read_csv(os.path.join(pkg, 'points.csv'), dtype={'point': str, 'item': str})

    Tg = float(net['ground_C'])
    hours = float(net['hours'])
    nidx = {n: i for i, n in enumerate(nodes)}
    for col in ('from_node', 'to_node'):
        for n in pipes[col]:
            if n not in nidx:
                nidx[n] = len(nodes)
                nodes.append(n)
    for n in subs['node']:
        if n not in nidx:
            nidx[n] = len(nodes)
            nodes.append(n)
    NN = len(nodes)
    plant_n = nidx[str(net['plant_node'])]
    NP = len(pipes)
    pu = pipes['from_node'].map(nidx).values
    pv = pipes['to_node'].map(nidx).values
    R = pipes['resistance_Pa_s2_kg2'].values.astype(float)
    V = pipes['volume_m3'].values.astype(float)
    tau = pipes['loss_time_h'].values.astype(float)
    pidx = {p: i for i, p in enumerate(pipes['pipe'])}

    NS = len(subs)
    sidx = {s: i for i, s in enumerate(subs['substation'])}
    sn = subs['node'].map(nidx).values
    Tr = subs['return_C'].values.astype(float)
    Kv = subs['valve_capacity'].values.astype(float)

    # initial
    Tps = np.full(NP, Tg)
    Tpr = np.full(NP, Tg)
    Tns = np.full(NN, Tg)
    Tnr = np.full(NN, Tg)
    for kind, name, nw, T in init[['kind', 'name', 'network', 'temp_C']].itertuples(index=False):
        name = str(name)
        if kind == 'pipe':
            if name in pidx:
                (Tps if nw == 'supply' else Tpr)[pidx[name]] = T
        else:
            if name in nidx:
                (Tns if nw == 'supply' else Tnr)[nidx[name]] = T

    nsteps = int(round(hours * 3600 / DT))
    # points may ask beyond? take max point time
    if len(points):
        nsteps = max(nsteps, int(round(points['time_h'].max() * 3600 / DT)))
    tstart = np.arange(nsteps) * DTH  # t_(k-1) for k=1..nsteps

    # schedules at t_(k-1)
    plant = plant.sort_values('time_h', kind='stable')
    pi = np.searchsorted(plant['time_h'].values, tstart + 1e-9, side='right') - 1
    pi = np.maximum(pi, 0)
    Tplant = plant['supply_C'].values[pi]
    DPplant = plant['dp_Pa'].values[pi]

    Qsched = np.zeros((nsteps, NS))
    demand = demand[demand['substation'].isin(sidx)]
    for s, g in demand.groupby('substation'):
        g = g.sort_values('time_h', kind='stable')
        ii = np.searchsorted(g['time_h'].values, tstart + 1e-9, side='right') - 1
        ii = np.maximum(ii, 0)
        Qsched[:, sidx[s]] = g['heat_kW'].values[ii]

    # hydraulic structures
    free = np.array([i for i in range(NN) if i != plant_n])
    fmap = -np.ones(NN, dtype=np.int64)
    fmap[free] = np.arange(len(free))
    NF = len(free)
    Bm = sp.csr_matrix((np.concatenate([np.ones(NP), -np.ones(NP)]),
                        (np.concatenate([np.arange(NP)] * 2), np.concatenate([pu, pv]))),
                       shape=(NP, NN))
    BmT = Bm.T.tocsr()
    Bf = Bm[:, free].tocsc()
    BfT = Bf.T.tocsr()
    R2 = 2.0 * R
    # substations aggregated per node
    Smat = sp.csr_matrix((np.ones(NS), (sn, np.arange(NS))), shape=(NN, NS))

    hyd = Hyd(Bm, free, plant_n, R2, sn, Kv, NN)
    lim = np.zeros(NS, dtype=bool)
    p = np.full(NN, DPplant[0])
    m = np.full(NP, 1e-3)
    Kv = np.where(Kv > 0, Kv, 0.0)

    sub_ps = Plug(V, tau, Tps, Tg)
    sub_pr = Plug(V, tau, Tpr, Tg)
    ret_pipe_dummy = None

    # result accumulators
    want_T_steps = set()
    pts = points
    step_of = np.rint(pts['time_h'].values * 3600 / DT).astype(np.int64)
    Tsave = {}
    Rsave = {}
    heat_cum = np.zeros(NS)
    heat_hist = np.zeros((nsteps + 1, NS))  # cumulative energy kJ
    need_T = set(step_of[pts['quantity'].values == 'supply_C'].tolist())
    need_R = set(step_of[pts['quantity'].values == 'return_C'].tolist())

    Tsave[0] = Tns.copy()
    Rsave[0] = Tnr[plant_n]
    for k in range(1, nsteps + 1):
        tprev = (k - 1) * DTH
        tk = k * DTH
        Q = Qsched[k - 1]
        dpP = DPplant[k - 1]
        Tn_sub = Tns[sn]
        mw = Q / (CP * (Tn_sub - Tr))
        p[plant_n] = dpP
        m, p, msub, lim = solve_hyd(hyd, m, p, mw, dpP, lim)

        q = m * DT / RHO  # supply volume a->b
        # supply outflows
        To = sub_ps.outflow(q, tk)
        aq = np.abs(q)
        recv = np.where(q > 0, pv, pu)
        wsum = np.bincount(recv, weights=aq, minlength=NN)
        hsum = np.bincount(recv, weights=aq * To, minlength=NN)
        # plant
        mplant = (BmT @ m)[plant_n] + (Smat @ msub)[plant_n]
        vpl = max(mplant, 0.0) * DT / RHO
        wsum[plant_n] += vpl
        hsum[plant_n] += vpl * Tplant[k - 1]
        arr = wsum > 0
        Tns = np.where(arr, hsum / np.where(arr, wsum, 1.0), Tns)
        # push into supply pipes
        send = np.where(q > 0, pu, pv)
        sub_ps.push(q, Tns[send], tk)
        # heat
        Tn_sub = Tns[sn]
        heat_cum = heat_cum + msub * CP * (Tn_sub - Tr) * DT
        heat_hist[k] = heat_cum
        # return network: flow b->a, q_r = -q
        qr = -q
        Tor = sub_pr.outflow(qr, tk)
        recvr = np.where(qr > 0, pv, pu)
        wr = np.bincount(recvr, weights=aq, minlength=NN)
        hr = np.bincount(recvr, weights=aq * Tor, minlength=NN)
        vs = msub * DT / RHO
        wr += np.bincount(sn, weights=vs, minlength=NN)
        hr += np.bincount(sn, weights=vs * Tr, minlength=NN)
        arr = wr > 0
        Tnr = np.where(arr, hr / np.where(arr, wr, 1.0), Tnr)
        sendr = np.where(qr > 0, pu, pv)
        sub_pr.push(qr, Tnr[sendr], tk)
        if k in need_T:
            Tsave[k] = Tns.copy()
        if k in need_R:
            Rsave[k] = Tnr[plant_n]

    vals = []
    for pt, th, item, qty, k in zip(pts['point'].tolist(), pts['time_h'].tolist(), pts['item'].tolist(), pts['quantity'].tolist(), step_of.tolist()):
        if qty == 'supply_C':
            v = Tsave[k][sn[sidx[item]]]
        elif qty == 'heat_kW':
            k0 = max(k - int(round(3600 / DT)), 0)
            j = sidx[item]
            v = (heat_hist[k, j] - heat_hist[k0, j]) / 3600.0
        else:
            v = Rsave[k]
        vals.append(v)
    pd.DataFrame({'point': pts['point'], 'value': vals}).to_csv(out, index=False, float_format='%.6f')


if __name__ == '__main__':
    main()
