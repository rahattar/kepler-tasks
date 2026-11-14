#!/usr/bin/env python3
"""HN-3 calculation of supply temperatures and delivered heat for one package."""
import sys, os, json
import numpy as np
import pandas as pd
import scipy.sparse as sp
from scipy.sparse.linalg import spsolve, splu

RHO = 975.0
CP = 4.19
DT = 120.0
DTH = DT / 3600.0
MAXFIT = int(os.environ.get("MAXFIT", "2"))
PERMC = os.environ.get("PERMC", "MMD_AT_PLUS_A")


def load(pkg):
    rd = lambda f: pd.read_csv(os.path.join(pkg, f))
    with open(os.path.join(pkg, 'network.json')) as f:
        net = json.load(f)
    return (net, rd('nodes.csv'), rd('pipes.csv'), rd('substations.csv'), rd('demand.csv'),
            rd('plant.csv'), rd('initial.csv'), rd('points.csv'),
            rd('pressure_survey.csv') if os.path.exists(os.path.join(pkg, 'pressure_survey.csv')) else None,
            rd('meters.csv') if os.path.exists(os.path.join(pkg, 'meters.csv')) else None)


def schedule_at(times, values, t):
    """Value of a step schedule at time t (rows sorted by time)."""
    i = np.searchsorted(times, t + 1e-9, side='right') - 1
    return values[max(i, 0)]


class Hydraulics:
    """Solves the symmetric supply/return state on node pressure differences h = p_s - p_r.

    With return pipes mirroring supply pipes, the return pressure drop equals the supply drop, so
    h_u - h_v = 2 R m |m|.  Unknowns are h at all non-plant nodes; plant node h = DP.
    """

    def __init__(self, N, pu, pv, R, plant, sub_node, K):
        self.N, self.pu, self.pv = N, pu, pv
        self.g = 1.0 / np.sqrt(2.0 * R)  # m = g sign(dh) sqrt|dh|
        self.plant = plant
        self.sub_node, self.K = sub_node, K
        self.free = np.array([i for i in range(N) if i != plant])
        self.pos = -np.ones(N, dtype=int)
        self.pos[self.free] = np.arange(len(self.free))
        self.h = None
        P = len(pu)
        self.A = sp.csr_matrix((np.r_[np.ones(P), -np.ones(P)], (np.r_[pu, pv], np.r_[np.arange(P), np.arange(P)])),
                               shape=(N, P))  # node-pipe incidence (out of u)

    def sub_flow(self, h, mwant):
        hs = h[self.sub_node]
        mm = self.K * np.sqrt(np.maximum(hs, 0.0))
        m = np.minimum(mwant, mm)
        lim = mm < mwant
        d = np.where(lim & (hs > 0), self.K / (2 * np.sqrt(np.maximum(hs, 1e-6))), 0.0)
        m = np.where(hs > 0, m, 0.0)
        return m, d

    def residual(self, h, mwant):
        dh = h[self.pu] - h[self.pv]
        q = self.g * np.sign(dh) * np.sqrt(np.abs(dh))
        ms, ds = self.sub_flow(h, mwant)
        F = np.bincount(self.pu, q, self.N) - np.bincount(self.pv, q, self.N)
        F += np.bincount(self.sub_node, ms, self.N)
        return F, q, ms, ds, dh

    def _build_struct(self):
        N, pu, pv = self.N, self.pu, self.pv
        nf = len(self.free)
        iu, iv = self.pos[pu], self.pos[pv]
        rows, cols, src, sgn = [], [], [], []
        P = len(pu)
        ar = np.arange(P)
        for (r_, c_, s_) in ((iu, iu, 1.0), (iv, iv, 1.0), (iu, iv, -1.0), (iv, iu, -1.0)):
            m = (r_ >= 0) & (c_ >= 0)
            rows.append(r_[m]); cols.append(c_[m]); src.append(ar[m]); sgn.append(np.full(m.sum(), s_))
        # substation diagonals
        ps = self.pos[self.sub_node]
        m = ps >= 0
        rows.append(ps[m]); cols.append(ps[m]); src.append(P + np.nonzero(m)[0]); sgn.append(np.ones(m.sum()))
        rows = np.concatenate(rows); cols = np.concatenate(cols)
        self._src = np.concatenate(src); self._sgn = np.concatenate(sgn)
        key = cols.astype(np.int64) * nf + rows  # CSC order
        uk, inv = np.unique(key, return_inverse=True)
        self._inv = inv
        self._nnz = len(uk)
        self._indices = (uk % nf).astype(np.int32)
        ccol = (uk // nf)
        self._indptr = np.searchsorted(ccol, np.arange(nf + 1)).astype(np.int32)
        self._nf = nf

    def jac(self, dq, ds):
        if not hasattr(self, '_inv'):
            self._build_struct()
        w = np.concatenate([dq, ds])[self._src] * self._sgn
        data = np.bincount(self._inv, weights=w, minlength=self._nnz)
        return sp.csc_matrix((data, self._indices, self._indptr), shape=(self._nf, self._nf))

    def solve(self, DP, mwant):
        N = self.N
        if self.h is None:
            self.h = np.full(N, DP * 0.8)
        h = self.h.copy()
        h[self.plant] = DP
        fr = self.free
        scale = max(np.sum(mwant), 1e-9)
        lu = getattr(self, '_lu', None)
        fresh = False
        prev = None
        for it in range(200):
            F, q, ms, ds, dh = self.residual(h, mwant)
            r = F[fr]
            r0 = np.sum(r * r)
            nr = np.abs(r).max()
            if nr < 1e-9 * scale + 1e-12:
                break
            if lu is None or (prev is not None and r0 > 0.05 * prev and not fresh):
                dq = self.g / (2 * np.sqrt(np.maximum(np.abs(dh), 1e-3)))
                J = self.jac(dq, ds)
                lu = splu(J, permc_spec=PERMC, diag_pivot_thresh=0.0, options=dict(SymmetricMode=True))
                fresh = True
            else:
                fresh = False
            step = lu.solve(-r)
            lam = 1.0
            ok = False
            for _ in range(40):
                hn = h.copy()
                hn[fr] += lam * step
                Fn = self.residual(hn, mwant)[0][fr]
                if np.sum(Fn * Fn) < r0 * (1 - 1e-4 * lam):
                    ok = True
                    break
                if not fresh:
                    break
                if lam < 1e-9:
                    ok = True
                    break
                lam *= 0.5
            if not ok:
                lu = None  # refactor
                prev = None
                continue
            prev = r0
            h = hn
        self._lu = lu
        F, q, ms, ds, dh = self.residual(h, mwant)
        self.h = h
        return q, ms, h


def self_sensitivity(hyd, h, mwant):
    """d(dp at substation node)/d(extra take-off of that substation), others responding, own valve fixed."""
    F, q, ms, ds, dh = hyd.residual(h, mwant)
    dq = hyd.g / (2 * np.sqrt(np.maximum(np.abs(dh), 1e-3)))
    lu = splu(hyd.jac(dq, ds), permc_spec=PERMC, diag_pivot_thresh=0.0, options=dict(SymmetricMode=True))
    nodes_u, inv = np.unique(hyd.sub_node, return_inverse=True)
    pos = hyd.pos[nodes_u]
    nf = len(hyd.free)
    out = np.zeros(len(nodes_u))
    ok = pos >= 0
    if ok.any():
        Bm = np.zeros((nf, ok.sum()))
        Bm[pos[ok], np.arange(ok.sum())] = 1.0
        X = lu.solve(Bm)
        out[ok] = X[pos[ok], np.arange(ok.sum())]
    x = out[inv]
    # remove own valve response (Sherman-Morrison); other substations at the node are kept
    return x / np.maximum(1 - ds * x, 1e-12)


class Plugs:
    """Double ended ring buffers of water parcels for many pipes.

    Parcel value a = (T0 - Tg) * exp((t0 - tref) / tau); temperature at t: Tg + a exp(-(t - tref)/tau).
    Index orientation: low end = from_node end.
    """

    def __init__(self, V, tau, T0, Tg, cap=64):
        n = len(V)
        self.n, self.V, self.tau, self.Tg = n, V, tau, Tg
        self.C = cap
        self.vol = np.zeros((n, cap))
        self.a = np.zeros((n, cap))
        self.lo = np.zeros(n, dtype=np.int64)
        self.cnt = np.ones(n, dtype=np.int64)
        self.vol[:, 0] = V
        self.a[:, 0] = T0 - Tg
        self.tref = 0.0
        self.rows = np.arange(n)

    def grow(self):
        C = self.C
        idx = (self.lo[:, None] + np.arange(C)[None, :]) % C
        vol = np.take_along_axis(self.vol, idx, 1)
        a = np.take_along_axis(self.a, idx, 1)
        self.vol = np.zeros((self.n, 2 * C)); self.vol[:, :C] = vol
        self.a = np.zeros((self.n, 2 * C)); self.a[:, :C] = a
        self.lo[:] = 0
        self.C = 2 * C

    def rebase(self, t):
        f = np.exp(-(t - self.tref) / self.tau)
        self.a *= f[:, None]
        self.tref = t

    def step(self, flowvol, t_end, Tin_lo, Tin_hi):
        """flowvol>0: moves from low end to high end. Returns outflow mean temperature and volume.
        Tin_lo / Tin_hi: temperature of water entering at low / high end (callable after outflow)."""
        if np.max((t_end - self.tref) / self.tau) > 200:
            self.rebase(t_end)
        rows = self.rows
        rem = np.abs(flowvol).copy()
        pos = flowvol > 0
        acc = np.zeros(self.n)
        tot = rem.copy()
        C = self.C
        active = np.nonzero(rem > 0)[0]
        while active.size:
            p = pos[active]
            end = np.where(p, self.lo[active] + self.cnt[active] - 1, self.lo[active]) % C
            v = self.vol[active, end]
            take = np.minimum(rem[active], v)
            acc[active] += take * self.a[active, end]
            v2 = v - take
            rem[active] -= take
            emptied = v2 <= 1e-12 * self.V[active]
            self.vol[active, end] = np.where(emptied, 0.0, v2)
            e = active[emptied]
            pe = pos[e]
            self.cnt[e] -= 1
            self.lo[e[~pe]] = (self.lo[e[~pe]] + 1) % C
            done = (rem[active] <= 1e-12 * self.V[active]) | (self.cnt[active] == 0)
            active = active[~done]
        decay = np.exp(-(t_end - self.tref) / self.tau)
        with np.errstate(invalid='ignore', divide='ignore'):
            Tout = np.where(tot > 0, self.Tg + acc / np.where(tot > 0, tot, 1) * decay, np.nan)
        return Tout, tot

    def push(self, flowvol, Tin, t_end):
        """Add the step's inflow (Tin per pipe, at the inlet end implied by flow sign)."""
        mv = np.abs(flowvol)
        act = np.nonzero(mv > 0)[0]
        if act.size == 0:
            return
        if np.max(self.cnt[act]) + 1 > self.C:
            self.grow()
        C = self.C
        p = flowvol[act] > 0
        aval = (Tin[act] - self.Tg) * np.exp((t_end - self.tref) / self.tau[act])
        # positive flow enters at low end
        lp = act[p]
        self.lo[lp] = (self.lo[lp] - 1) % C
        idx_lo = self.lo[lp]
        self.vol[lp, idx_lo] = mv[lp]
        self.a[lp, idx_lo] = aval[p]
        ln = act[~p]
        idx_hi = (self.lo[ln] + self.cnt[ln]) % C
        self.vol[ln, idx_hi] = mv[ln]
        self.a[ln, idx_hi] = aval[~p]
        self.cnt[act] += 1


def calibrate_R(N, pu, pv, R, plant_i, snode, sname, survey, tol=500.0):
    sv = survey.set_index('item')
    flow = sv.loc[sname, 'flow_kg_s'].to_numpy(float)
    dpm = sv.loc[sname, 'dp_Pa'].to_numpy(float)
    DP = float(sv.loc['plant', 'dp_Pa'])
    R = R.copy()
    bigK = np.full(len(sname), 1e6)

    def run(Rx):
        hy = Hydraulics(N, pu, pv, Rx, plant_i, snode, bigK)
        q, ms, h = hy.solve(DP, flow)
        return h, q, hy

    used = set()
    for it in range(40):
        h, q, hy = run(R)
        r = h[snode] - dpm  # model minus measured
        if np.abs(r).max() <= tol:
            break
        # sensitivity of sub-node h to log R_j
        dh = h[pu] - h[pv]
        dq = hy.g / (2 * np.sqrt(np.maximum(np.abs(dh), 1e-3)))
        J = (hy.A @ sp.diags(dq) @ hy.A.T).tocsr()
        fr = hy.free
        Jf = J[fr][:, fr].tocsc()
        from scipy.sparse.linalg import splu
        lu = splu(Jf)
        # dF/dlogR_j = -q_j/2 at pipe ends: +1 at u, -1 at v
        B = (hy.A @ sp.diags(-q / 2.0)).tocsr()[fr].toarray()
        X = -lu.solve(B)  # dh_free / dlogR (free x P)
        full = np.zeros((N, len(pu)))
        full[fr] = X
        Ssub = full[snode]  # S x P
        # best single pipe fit: minimize ||r + a*S_j||
        nrm = np.sum(Ssub * Ssub, 0)
        ok = nrm > 0
        a = np.zeros(len(pu))
        a[ok] = -(Ssub[:, ok].T @ r) / nrm[ok]
        gain = np.zeros(len(pu))
        gain[ok] = a[ok] ** 2 * nrm[ok]
        j = int(np.argmax(gain))
        # 1-D refinement of R_j by secant on objective
        def obj(lr):
            Rx = R.copy(); Rx[j] = np.exp(lr)
            hh = run(Rx)[0]
            return np.sum((hh[snode] - dpm) ** 2)
        from scipy.optimize import minimize_scalar
        l0 = np.log(R[j])
        lnew = l0 + np.clip(a[j], -5, 5)
        res = minimize_scalar(obj, bracket=(min(l0, lnew) - 0.1, max(l0, lnew) + 0.1) if False else None,
                              bounds=(min(l0, lnew) - 2, max(l0, lnew) + 2), method='bounded',
                              options={'xatol': 1e-6})
        R[j] = np.exp(res.x)
        if os.environ.get('HN_DEBUG'):
            print('calib pipe', j, 'R', np.exp(l0), '->', R[j], 'maxr', np.abs(r).max(), file=sys.stderr)
    return R


def calibrate_subs(simulate, Tr, K, meters, sname, run_h, thr=0.004, maxfit=MAXFIT):
    """Fit return temperature and valve capacity of substations whose meters disagree."""
    mt = meters.set_index('substation').loc[sname]
    Em = mt['energy_kWh'].to_numpy(float)
    Vm = mt['volume_m3'].to_numpy(float)
    Tr = Tr.copy(); K = K.copy()
    Trc, Kc = Tr.copy(), K.copy()
    from scipy.optimize import least_squares
    for it in range(maxfit + 1):
        res = simulate(Tr, K, 24, local=True)
        if it == 0:
            first = res
        _, _, _, _, E, Vo, loc = res
        er = E / Em - 1; vr = Vo / Vm - 1
        bad = np.nonzero((np.abs(er) > thr) | (np.abs(vr) > thr))[0]
        if os.environ.get('HN_DEBUG'):
            print('subcal it', it, 'bad', [(sname[i], round(er[i], 4), round(vr[i], 4)) for i in bad], file=sys.stderr)
        if bad.size == 0:
            break
        for i in bad:
            Tp, Tn, dp, Q = loc['Tprev'][:, i], loc['Tnow'][:, i], loc['dp'][:, i], loc['Q'][:, i]
            sn, m0 = loc['sens'][:, i], loc['m'][:, i]
            d0 = dp + sn * m0

            def model(x, i=i):
                tr, kk = x[0], np.exp(x[1])
                mw = Q / (CP * (Tp - tr))
                k2 = kk * kk
                mv = (-k2 * sn + np.sqrt(k2 * k2 * sn * sn + 4 * k2 * np.maximum(d0, 0))) / 2
                m = np.where(d0 > 0, np.minimum(mw, mv), 0.0)
                e = np.sum(m * CP * (Tn - tr)) * DTH
                v = np.sum(m) * DT / RHO
                return np.array([e / Em[i] - 1, v / Vm[i] - 1])
            # energy matched: only return temperature matters (valve not limiting)
            x0 = np.array([Trc[i], np.log(Kc[i])])
            hiT = np.min(Tp) - 1.0
            cands = []
            r1 = least_squares(lambda y: model([y[0], x0[1]]), [min(Tr[i], hiT - 1e-6)], bounds=([0.0], [hiT]))
            cands.append((np.abs(model([r1.x[0], x0[1]])).max(), np.array([r1.x[0], x0[1]])))
            r2 = least_squares(lambda y: model([x0[0], y[0]]), [np.log(K[i])], bounds=([x0[1] - 6], [x0[1] + 6]))
            cands.append((np.abs(model([x0[0], r2.x[0]])).max(), np.array([x0[0], r2.x[0]])))
            one = min(cands, key=lambda c: c[0])
            if one[0] < 0.003:
                x = one[1]
            else:
                best = None
                for kstart in (np.log(K[i]), x0[1], x0[1] - 0.5, x0[1] + 0.5):
                    r = least_squares(model, np.array([min(Tr[i], hiT - 1e-6), kstart]), x_scale=np.array([1.0, 0.1]),
                                      bounds=([0.0, x0[1] - 6], [hiT, x0[1] + 6]))
                    if best is None or r.cost < best[0]:
                        best = (r.cost, r.x)
                x = best[1]
            Tr[i] = x[0]; K[i] = np.exp(x[1])
            if os.environ.get('HN_DEBUG'):
                print('  fit', sname[i], 'Tr', x0[0], '->', Tr[i], 'K', np.exp(x0[1]), '->', K[i], model(x), file=sys.stderr)
        if it == maxfit - 1:
            it += 1
            break
    return Tr, K, None


def main(pkg, out):
    net, nodes, pipes, subs, demand, plant, init, points, survey, meters = load(pkg)
    Tg = float(net['ground_C'])
    hours = float(net['hours'])
    nlist = list(nodes['node'])
    nid = {n: i for i, n in enumerate(nlist)}
    N = len(nlist)
    plant_i = nid[net['plant_node']]
    pu = pipes['from_node'].map(nid).to_numpy()
    pv = pipes['to_node'].map(nid).to_numpy()
    P = len(pu)
    R = pipes['resistance_Pa_s2_kg2'].to_numpy(float)
    V = pipes['volume_m3'].to_numpy(float)
    tau = pipes['loss_time_h'].to_numpy(float)
    sname = list(subs['substation'])
    sid = {s: i for i, s in enumerate(sname)}
    S = len(sname)
    snode = subs['node'].map(nid).to_numpy()
    Tr = subs['return_C'].to_numpy(float)
    K = subs['valve_capacity'].to_numpy(float)

    # schedules
    demand = demand.sort_values(['substation', 'time_h'])
    dem_t = {}
    for s, g in demand.groupby('substation'):
        dem_t[sid[s]] = (g['time_h'].to_numpy(float), g['heat_kW'].to_numpy(float))
    # demand changes on discrete hours typically; build per-step evaluation
    plant = plant.sort_values('time_h')
    pl_t = plant['time_h'].to_numpy(float)
    pl_T = plant['supply_C'].to_numpy(float)
    pl_dp = plant['dp_Pa'].to_numpy(float)

    # initial
    ini = init.set_index(['kind', 'network', 'name'])['temp_C']
    pname = list(pipes['pipe'])
    Ts0 = np.array([ini[('pipe', 'supply', p)] for p in pname])
    Tr0 = np.array([ini[('pipe', 'return', p)] for p in pname])
    Tsn = np.array([ini.get(('node', 'supply', n), np.nan) for n in nlist], float)
    Trn = np.array([ini.get(('node', 'return', n), np.nan) for n in nlist], float)

    if survey is not None:
        try:
            R = calibrate_R(N, pu, pv, R, plant_i, snode, sname, survey)
        except Exception as ex:
            print('resistance calibration failed:', ex, file=sys.stderr)

    per_h = int(round(3600 / DT))
    allt = np.unique(np.r_[demand['time_h'].to_numpy(float), pl_t])
    Tsn0, Trn0 = Tsn, Trn

    def simulate(Tr, K, run_h, local=False):
        Tsn, Trn = Tsn0.copy(), Trn0.copy()
        hyd = Hydraulics(N, pu, pv, R, plant_i, snode, K)
        sup = Plugs(V, tau, Ts0, Tg)
        ret = Plugs(V, tau, Tr0, Tg)
        nsteps = int(round(run_h * 3600 / DT))
        H = int(run_h)
        rec_T = np.zeros((H + 1, S)); rec_R = np.zeros((H + 1, S))
        rec_Q = np.zeros((H + 1, S)); rec_P = np.zeros(H + 1)
        qacc = np.zeros(S)
        mvol = np.zeros(S); menergy = np.zeros(S)
        loc = {'Tprev': [], 'Tnow': [], 'dp': [], 'Q': [], 'sens': [], 'm': []} if local else None
        Q = np.zeros(S)
        last_seg = None
        for k in range(1, nsteps + 1):
            t0 = (k - 1) * DT / 3600.0
            t1 = k * DT / 3600.0
            seg = np.searchsorted(allt, t0 + 1e-9, side='right')
            if seg != last_seg:
                for i in range(S):
                    tt, vv = dem_t[i]
                    Q[i] = schedule_at(tt, vv, t0)
                last_seg = seg
            DP = schedule_at(pl_t, pl_dp, t0)
            Tpl = schedule_at(pl_t, pl_T, t0)
            Tprev = Tsn[snode]
            mwant = Q / (CP * (Tprev - Tr))
            q, ms, h = hyd.solve(DP, mwant)
            fv = q * DT / RHO
            Tout, vout = sup.step(fv, t1, None, None)
            outnode = np.where(fv > 0, pv, pu)
            innode = np.where(fv > 0, pu, pv)
            m = vout > 0
            hv = np.bincount(outnode[m], vout[m] * Tout[m], N)
            vv_ = np.bincount(outnode[m], vout[m], N)
            netout = (np.bincount(pu, q, N) - np.bincount(pv, q, N))[plant_i] + np.sum(ms[snode == plant_i])
            pvol = max(netout, 0.0) * DT / RHO
            hv[plant_i] += pvol * Tpl
            vv_[plant_i] += pvol
            nz = vv_ > 0
            Tsn = Tsn.copy()
            Tsn[nz] = hv[nz] / vv_[nz]
            sup.push(fv, Tsn[innode], t1)
            Tnow = Tsn[snode]
            qd = ms * CP * (Tnow - Tr)
            qacc += qd
            rv = -fv
            Tout, vout = ret.step(rv, t1, None, None)
            outnode = np.where(rv > 0, pv, pu)
            innode = np.where(rv > 0, pu, pv)
            m = vout > 0
            svol = ms * DT / RHO
            hv = np.bincount(outnode[m], vout[m] * Tout[m], N) + np.bincount(snode, svol * Tr, N)
            vv_ = np.bincount(outnode[m], vout[m], N) + np.bincount(snode, svol, N)
            nz = vv_ > 0
            Trn = Trn.copy()
            Trn[nz] = hv[nz] / vv_[nz]
            ret.push(rv, Trn[innode], t1)
            if k <= 24 * per_h:
                mvol += svol
                menergy += qd * DTH
                if local:
                    if (k - 1) % per_h == 0:
                        sens = self_sensitivity(hyd, h, mwant)
                    loc['sens'].append(sens); loc['m'].append(ms.copy())
                    loc['Tprev'].append(Tprev); loc['Tnow'].append(Tnow)
                    loc['dp'].append(h[snode].copy()); loc['Q'].append(Q.copy())
            if k % per_h == 0:
                hr = k // per_h
                rec_T[hr] = Tnow
                rec_R[hr] = Trn[snode]
                rec_Q[hr] = qacc / per_h
                rec_P[hr] = Trn[plant_i]
                qacc[:] = 0
        if local:
            loc = {a_: np.array(b_) for a_, b_ in loc.items()}
        return rec_T, rec_R, rec_Q, rec_P, menergy, mvol, loc

    first = None
    if meters is not None and hours >= 24:
        try:
            Tr, K, first = calibrate_subs(simulate, Tr, K, meters, sname, hours)
        except Exception as ex:  # keep commissioned values
            print('substation calibration failed:', ex, file=sys.stderr)
            Tr = subs['return_C'].to_numpy(float); K = subs['valve_capacity'].to_numpy(float)
    if first is None:
        first = simulate(Tr, K, hours)
    rec_T, rec_R, rec_Q, rec_P, menergy, mvol, _ = first

    if os.environ.get('HN_DEBUG') and meters is not None:
        mt = meters.set_index('substation').loc[sname]
        dbg = pd.DataFrame({'sub': sname, 'Er': menergy / mt.energy_kWh.values - 1,
                            'Vr': mvol / mt.volume_m3.values - 1, 'Tr': Tr, 'K': K})
        dbg.to_csv(os.environ['HN_DEBUG'], index=False)
    vals = []
    for pt, th, item, qty in points[['point', 'time_h', 'item', 'quantity']].itertuples(index=False):
        hr = int(round(th))
        if item == 'plant':
            v = rec_P[hr]
        else:
            i = sid[item]
            v = {'supply_C': rec_T, 'return_C': rec_R, 'heat_kW': rec_Q}[qty][hr, i]
        vals.append(v)
    pd.DataFrame({'point': points['point'], 'value': vals}).to_csv(out, index=False, float_format='%.6f')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
