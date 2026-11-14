#!/usr/bin/env python3
"""HN-3 (rev. 5) calculation of supply temperatures and delivered heat for one heat-network package.

Usage: python3 heatnet.py PACKAGE_DIR OUT_CSV

Before the calculation the package's own records are used to check the network data:
  * the pressure survey is compared with the hydraulics of section 3; a pipe whose resistance
    does not fit the survey (fouled, part-closed valve) gets the resistance the survey shows;
  * the heat meters (first 24 h) are compared with the calculation; a substation whose metered
    volume does not fit its commissioned return temperature gets the return temperature the meter shows.
"""
import sys, os, json
from collections import deque
import numpy as np
import pandas as pd
import scipy.sparse as sp

RHO = 975.0
CP = 4.19
DT = 120.0
SPH = 30  # steps per hour


class Net:
    def __init__(self, pkg):
        self.pkg = pkg
        cfg = json.load(open(os.path.join(pkg, 'network.json')))
        self.Tg = float(cfg['ground_C'])
        self.plant = str(cfg['plant_node'])
        rd = lambda f, **kw: pd.read_csv(os.path.join(pkg, f), **kw)
        pipes = rd('pipes.csv', dtype={'pipe': str, 'from_node': str, 'to_node': str})
        subs = rd('substations.csv', dtype={'substation': str, 'node': str})
        nodes = [str(x) for x in rd('nodes.csv', dtype=str)['node']]
        nodes += list(pipes['from_node']) + list(pipes['to_node']) + list(subs['node']) + [self.plant]
        nodes = list(dict.fromkeys(nodes))
        self.nodes = nodes
        self.nid = {n: i for i, n in enumerate(nodes)}
        self.pipes = list(pipes['pipe'])
        self.pu = np.array([self.nid[x] for x in pipes['from_node']], dtype=np.int64)
        self.pv = np.array([self.nid[x] for x in pipes['to_node']], dtype=np.int64)
        self.vol = pipes['volume_m3'].to_numpy(float)
        self.R = pipes['resistance_Pa_s2_kg2'].to_numpy(float).copy()
        self.tau = pipes['loss_time_h'].to_numpy(float) * 3600.0
        self.subs = list(subs['substation'])
        self.sid = {s: i for i, s in enumerate(self.subs)}
        self.snode = np.array([self.nid[x] for x in subs['node']], dtype=np.int64)
        self.Tr = subs['return_C'].to_numpy(float).copy()
        self.K = subs['valve_capacity'].to_numpy(float).copy()
        self.N, self.P, self.S = len(nodes), len(self.pipes), len(self.subs)
        self.p0 = self.nid[self.plant]

        dem = rd('demand.csv', dtype={'substation': str})
        self.dem = {}
        for s, g in dem.groupby('substation'):
            if s in self.sid:
                g = g.sort_values('time_h', kind='stable')
                self.dem[self.sid[s]] = (g['time_h'].to_numpy(float), g['heat_kW'].to_numpy(float))
        pl = rd('plant.csv').sort_values('time_h', kind='stable')
        self.pl_t = pl['time_h'].to_numpy(float)
        self.pl_T = pl['supply_C'].to_numpy(float)
        self.pl_dp = pl['dp_Pa'].to_numpy(float)

        ini = rd('initial.csv', dtype={'name': str, 'kind': str, 'network': str})
        pid = {p: i for i, p in enumerate(self.pipes)}
        self.ini_pipe = {'supply': np.full(self.P, np.nan), 'return': np.full(self.P, np.nan)}
        self.ini_node = {'supply': np.full(self.N, np.nan), 'return': np.full(self.N, np.nan)}
        for k, nm, nw, T in zip(ini['kind'], ini['name'], ini['network'], ini['temp_C']):
            nw = str(nw).strip().lower(); k = str(k).strip().lower()
            if nw not in self.ini_pipe:
                continue
            if k == 'pipe' and nm in pid:
                self.ini_pipe[nw][pid[nm]] = T
            elif k == 'node' and nm in self.nid:
                self.ini_node[nw][self.nid[nm]] = T
        for nw in ('supply', 'return'):
            a = self.ini_pipe[nw]; b = self.ini_node[nw]
            allv = np.concatenate([a, b])
            fill = np.nanmean(allv) if np.isfinite(allv).any() else 60.0
            for j in np.where(np.isnan(a))[0]:
                v = [x for x in (b[self.pu[j]], b[self.pv[j]]) if np.isfinite(x)]
                a[j] = np.mean(v) if v else fill
            for n in np.where(np.isnan(b))[0]:
                v = [a[j] for j in range(self.P) if self.pu[j] == n or self.pv[j] == n]
                b[n] = np.mean(v) if v else fill
        self.build_topology()

    # ---------------- topology -----------------
    def build_topology(self):
        N, P, S = self.N, self.P, self.S
        adj = [[] for _ in range(N)]
        for j in range(P):
            adj[self.pu[j]].append((j, self.pv[j]))
            adj[self.pv[j]].append((j, self.pu[j]))
        parent = np.full(N, -1); ppipe = np.full(N, -1)
        seen = np.zeros(N, bool); seen[self.p0] = True
        order = [self.p0]; tree = np.zeros(P, bool)
        i = 0
        while i < len(order):
            n = order[i]; i += 1
            for j, m in adj[n]:
                if not seen[m]:
                    seen[m] = True; parent[m] = n; ppipe[m] = j; tree[j] = True
                    order.append(m)
        path = {self.p0: {}}
        for n in order[1:]:
            j = ppipe[n]
            s = 1.0 if self.pu[j] == parent[n] else -1.0
            d = dict(path[parent[n]]); d[j] = s
            path[n] = d
        rows, cols, vals = [], [], []
        for n, pth in path.items():
            for j, s in pth.items():
                rows.append(n); cols.append(j); vals.append(s)
        A = sp.csr_matrix((vals, (rows, cols)), shape=(N, P))
        chords = [j for j in np.where(~tree)[0] if seen[self.pu[j]] and seen[self.pv[j]]]
        self.L = len(chords)
        Bd = np.zeros((P, self.L))
        for l, j in enumerate(chords):
            Bd[j, l] = 1.0
            pa, pb = path[self.pu[j]], path[self.pv[j]]
            for jj in set(pa) | set(pb):
                Bd[jj, l] += pa.get(jj, 0.0) - pb.get(jj, 0.0)
        self.Bd = Bd
        self.oncycle = np.any(Bd != 0, axis=1) | ~tree
        subnode = sp.csr_matrix((np.ones(S), (self.snode, np.arange(S))), shape=(N, S))
        self.TreeS = (A.T @ subnode).tocsr()          # P x S
        self.Asub = A[self.snode].tocsr()             # S x P
        self.TreeSd = self.TreeS.toarray()
        self.Asubd = self.Asub.toarray()
        # bridges: +1 if their flow (away from the plant) runs from_node -> to_node
        self.bdir = np.ones(P)
        for n in order[1:]:
            j = ppipe[n]
            self.bdir[j] = 1.0 if self.pu[j] == parent[n] else -1.0

    # ---------------- hydraulics (section 3) -----------------
    def _resid(self, m, c, mwant, DP, R, K):
        q = self.TreeS @ m
        if self.L:
            q = q + self.Bd @ c
        d = R * q * np.abs(q)
        dp = DP - 2.0 * (self.Asub @ d)
        sq = np.sqrt(np.maximum(dp, 0.0))
        mmax = K * sq
        act = mmax < mwant
        Fm = m - np.where(act, mmax, mwant)
        Fc = self.Bd.T @ d if self.L else np.zeros(0)
        return q, d, dp, sq, act, Fm, Fc

    def hydraulics(self, mwant, DP, m_prev=None, c_prev=None, R=None, K=None):
        """Semismooth Newton for the state of section 3: unknowns substation flows m and loop flows c."""
        R = self.R if R is None else R
        K = self.K if K is None else K
        Bd, L = self.Bd, self.L
        m = mwant.copy() if m_prev is None else np.minimum(m_prev, mwant)
        c = np.zeros(L) if c_prev is None else c_prev.copy()
        TreeS = self.TreeS
        q, d, dp, sq, act, Fm, Fc = self._resid(m, c, mwant, DP, R, K)
        for it in range(80):
            dscale = 1.0 + np.max(np.abs(d)) if len(d) else 1.0
            okm = np.all(np.abs(Fm) <= 1e-10 * (1.0 + m))
            okc = (not L) or np.max(np.abs(Fc)) <= 1e-8 * dscale
            if okm and okc:
                break
            idx = np.where(act)[0]
            nA = len(idx)
            dm = -Fm.copy()          # inactive rows: identity
            w = 2.0 * R * np.abs(q) + 1e-9 * dscale / (1.0 + np.abs(q))
            dmI = dm.copy(); dmI[idx] = 0.0
            qI = TreeS @ dmI         # pipe-flow change caused by the inactive part
            n = nA + L
            if n:
                J = np.zeros((n, n)); F = np.zeros(n)
                if nA:
                    g = K[idx] / np.maximum(sq[idx], 1e-12)
                    g = np.where(dp[idx] > 0, g, 0.0)
                    AW = self.Asubd[idx] * w
                    J[:nA, :nA] = np.eye(nA) + g[:, None] * (AW @ self.TreeSd[:, idx])
                    F[:nA] = Fm[idx] + g * (AW @ qI)
                    if L:
                        J[:nA, nA:] = g[:, None] * (AW @ Bd)
                if L:
                    BW = Bd.T * w
                    if nA:
                        J[nA:, :nA] = BW @ self.TreeSd[:, idx]
                    J[nA:, nA:] = BW @ Bd
                    F[nA:] = Fc + BW @ qI
                try:
                    dx = np.linalg.solve(J, -F)
                except np.linalg.LinAlgError:
                    dx = np.linalg.lstsq(J, -F, rcond=None)[0]
                dm[idx] = dx[:nA]
                dc = dx[nA:]
            else:
                dc = np.zeros(0)
            merit0 = np.sum(Fm ** 2) + np.sum((Fc / dscale) ** 2)
            t = 1.0
            for ls in range(30):
                mt = np.maximum(m + t * dm, 0.0)
                ct = c + t * dc
                res = self._resid(mt, ct, mwant, DP, R, K)
                merit = np.sum(res[5] ** 2) + np.sum((res[6] / dscale) ** 2)
                if merit < (1 - 1e-4 * t) * merit0 or merit == 0.0:
                    break
                t *= 0.5
            m, c = mt, ct
            q, d, dp, sq, act, Fm, Fc = res
        return m, q, c

    # ---------------- schedules -----------------
    def schedules(self, nsteps):
        t = np.arange(nsteps) / SPH  # t_(k-1) for k = 1..nsteps
        def lookup(ta, va):
            i = np.searchsorted(ta, t + 1e-9, side='right') - 1
            return va[np.clip(i, 0, len(va) - 1)]
        Q = np.zeros((nsteps, self.S))
        for s in range(self.S):
            if s in self.dem:
                Q[:, s] = lookup(*self.dem[s])
        return Q, lookup(self.pl_t, self.pl_dp), lookup(self.pl_t, self.pl_T)

    # ---------------- steps (sections 4, 5) -----------------
    def run(self, nsteps, sched, check_at=None, check=None):
        N, P, S = self.N, self.P, self.S
        Tg, tau, vol = self.Tg, self.tau, self.vol
        Qs, DPs, Tps = sched
        Tr = self.Tr
        pu, pv, snode, p0 = self.pu, self.pv, self.snode, self.p0
        cyc = np.where(self.oncycle)[0]
        fix = np.where(~self.oncycle)[0]
        nf = len(fix)
        bdir = self.bdir[fix]
        f_in = np.where(bdir > 0, pu[fix], pv[fix])    # supply inlet node of fixed-direction pipes
        f_out = np.where(bdir > 0, pv[fix], pu[fix])
        fvol = vol[fix]
        ftau = tau[fix]
        # FIFO stores of fixed-direction pipes, by cumulative inflow volume ("label").
        # column 0: label -V, column 1: label 0 (the initial water); column i+1 after the i-th moving step.
        ncol = nsteps + 2
        Cum = np.zeros((nf, ncol)); Gs = np.zeros((nf, ncol)); Gr = np.zeros((nf, ncol))
        Cum[:, 0] = -fvol
        Gs[:, 1] = fvol * (self.ini_pipe['supply'][fix] - Tg)
        Gr[:, 1] = fvol * (self.ini_pipe['return'][fix] - Tg)
        top = np.ones(nf, dtype=np.int64)
        ptr = np.ones(nf, dtype=np.int64)
        Gb_s = np.zeros(nf); Gb_r = np.zeros(nf)
        rows = np.arange(nf)
        # pipes that may reverse: deques from the from_node end to the to_node end, entries [vol, T']
        sup = {j: deque([[vol[j], self.ini_pipe['supply'][j] - Tg]]) for j in cyc}
        ret = {j: deque([[vol[j], self.ini_pipe['return'][j] - Tg]]) for j in cyc}

        Ts = self.ini_node['supply'].copy()
        Trn = self.ini_node['return'].copy()
        m_prev = None; c_prev = None
        hTs = np.zeros((nsteps + 1, S)); hTr = np.zeros((nsteps + 1, S))
        hQ = np.zeros((nsteps + 1, S)); hm = np.zeros((nsteps + 1, S)); hpr = np.zeros(nsteps + 1)
        hTs[0] = Ts[snode]; hTr[0] = Trn[snode]; hpr[0] = Trn[p0]
        sub_at_plant = snode == p0
        limacc = np.zeros(S)
        DTR = DT / RHO

        def pop_from(dq, V, right):
            acc = 0.0; rem = V; last = 0.0
            while rem > 0 and dq:
                seg = dq[-1] if right else dq[0]
                last = seg[1]
                if seg[0] <= rem:
                    acc += seg[0] * seg[1]; rem -= seg[0]
                    if right:
                        dq.pop()
                    else:
                        dq.popleft()
                else:
                    acc += rem * seg[1]; seg[0] -= rem; rem = 0.0
            if rem > 0:
                acc += rem * last
            return acc

        for k in range(1, nsteps + 1):
            tk = k * DT
            Tn = Ts[snode]
            dT = Tn - Tr
            mwant = np.where(dT > 1e-9, Qs[k - 1] / (CP * np.maximum(dT, 1e-9)), 0.0)
            m, q, c = self.hydraulics(mwant, DPs[k - 1], m_prev, c_prev)
            m_prev, c_prev = m, c
            aq = np.abs(q)
            Vm = aq * DTR
            down = np.where(q > 0, pv, pu)
            up = np.where(q > 0, pu, pv)
            outS = np.zeros(P); outR = np.zeros(P)

            # ---- outflow of fixed-direction pipes (supply and return together)
            if nf:
                Vf = np.maximum(q[fix] * bdir, 0.0) * DTR
                mov = Vf > 0
                Cnew = Cum[rows, top] + Vf
                b = Cnew - fvol
                while True:
                    inner = ptr <= top
                    cur = np.where(inner, Cum[rows, np.minimum(ptr, top)], np.inf)
                    adv = inner & (cur < b)
                    if not adv.any():
                        break
                    ptr = ptr + adv
                inner = ptr <= top
                pc = np.minimum(ptr, top)
                lo = Cum[rows, ptr - 1]
                seglen = np.where(inner, Cum[rows, pc] - lo, 0.0)
                sl = np.where(seglen > 0, seglen, 1.0)
                gs0 = Gs[rows, ptr - 1]; gr0 = Gr[rows, ptr - 1]
                segT_s = np.where(seglen > 0, (Gs[rows, pc] - gs0) / sl, 0.0)
                segT_r = np.where(seglen > 0, (Gr[rows, pc] - gr0) / sl, 0.0)
                nb_s = gs0 + (b - lo) * segT_s
                nb_r = gr0 + (b - lo) * segT_r
                ef = np.exp(-tk / ftau)
                Vd = np.where(mov, Vf, 1.0)
                outS[fix] = np.where(mov, Tg + (nb_s - Gb_s) / Vd * ef, 0.0)
                outR[fix] = np.where(mov, Tg + (nb_r - Gb_r) / Vd * ef, 0.0)
            for j in cyc:
                V = Vm[j]
                if V > 0:
                    e = np.exp(-tk / tau[j])
                    outS[j] = Tg + pop_from(sup[j], V, q[j] > 0) / V * e
                    outR[j] = Tg + pop_from(ret[j], V, q[j] < 0) / V * e

            # ---- supply nodes
            Hin = np.bincount(down, aq * outS, N)
            Min = np.bincount(down, aq, N)
            mpl = aq[up == p0].sum() + m[sub_at_plant].sum() - Min[p0]
            if mpl > 0:
                Hin[p0] += mpl * Tps[k - 1]; Min[p0] += mpl
            got = Min > 0
            Ts = np.where(got, Hin / np.where(got, Min, 1.0), Ts)
            Tn = Ts[snode]
            hQ[k] = m * CP * (Tn - Tr)
            limacc += np.where(m < mwant * (1 - 1e-9), hQ[k], 0.0)
            # ---- return nodes
            Hin = np.bincount(up, aq * outR, N) + np.bincount(snode, m * Tr, N)
            Min = np.bincount(up, aq, N) + np.bincount(snode, m, N)
            got = Min > 0
            Trn = np.where(got, Hin / np.where(got, Min, 1.0), Trn)

            # ---- inflow into pipes, entering at t_k
            for j in cyc:
                V = Vm[j]
                if V > 0:
                    e = np.exp(tk / tau[j])
                    Tps_ = (Ts[up[j]] - Tg) * e
                    Tpr_ = (Trn[down[j]] - Tg) * e
                    if q[j] > 0:
                        sup[j].appendleft([V, Tps_]); ret[j].append([V, Tpr_])
                    else:
                        sup[j].append([V, Tps_]); ret[j].appendleft([V, Tpr_])
            if nf and mov.any():
                r = rows[mov]
                t0 = top[mov]; t1 = t0 + 1
                einv = 1.0 / ef[mov]
                Cum[r, t1] = Cnew[mov]
                Gs[r, t1] = Gs[r, t0] + Vf[mov] * (Ts[f_in[mov]] - Tg) * einv
                Gr[r, t1] = Gr[r, t0] + Vf[mov] * (Trn[f_out[mov]] - Tg) * einv
                top = top + mov
                Gb_s = np.where(mov, nb_s, Gb_s); Gb_r = np.where(mov, nb_r, Gb_r)
            hTs[k] = Tn; hTr[k] = Trn[snode]; hm[k] = m; hpr[k] = Trn[p0]
            if check is not None and k == check_at:
                self.lim_E = limacc * DT / 3600.0
                if check(hTs, hQ, hm, k):
                    return None
        return hTs, hTr, hQ, hm, hpr

    # ---------------- checks against the package's own records -----------------
    def calibrate_resistance(self):
        f = os.path.join(self.pkg, 'pressure_survey.csv')
        if not os.path.exists(f) or self.S == 0:
            return
        s = pd.read_csv(f, dtype={'item': str})
        pl = s[s['item'].str.lower() == 'plant']
        if not len(pl):
            return
        DP = float(pl['dp_Pa'].iloc[0])
        m = np.zeros(self.S); meas = np.full(self.S, np.nan)
        for it, fl, d in zip(s['item'], s['flow_kg_s'], s['dp_Pa']):
            if it in self.sid:
                m[self.sid[it]] = fl; meas[self.sid[it]] = d
        have = np.isfinite(meas)
        Kbig = np.full(self.S, 1e30)

        def model(Rv):
            mm, q, c = self.hydraulics(m.copy(), DP, None, None, R=Rv, K=Kbig)
            return DP - 2.0 * (self.Asub @ (Rv * q * np.abs(q))), q

        def ss(dpm):
            return float(np.sum(np.where(have, meas - dpm, 0.0) ** 2))

        R = self.R.copy()
        NOISE = 200.0
        for rnd in range(40):
            dpm, q = model(R)
            res = np.where(have, meas - dpm, 0.0)
            if np.max(np.abs(res)) < 2.5 * NOISE:
                break
            r0 = ss(dpm)
            X = self.Asubd
            if self.L:
                w = 2.0 * R * np.abs(q) + 1e-9
                BWB = (self.Bd.T * w) @ self.Bd
                X = X - ((X * w) @ self.Bd) @ np.linalg.solve(BWB, self.Bd.T)
            Sens = -2.0 * X * (q * np.abs(q))[None, :]
            Sens[~have] = 0.0
            num = Sens.T @ res
            den = np.sum(Sens * Sens, axis=0)
            gain = np.where(den > 0, num * num / np.where(den > 0, den, 1.0), 0.0)
            best = None
            for j in np.argsort(-gain)[:6]:
                if den[j] <= 0 or gain[j] <= 0:
                    continue
                Rj = max(R[j] + num[j] / den[j], 1e-9)
                prevR, prevss = R[j], r0
                for _ in range(10):  # secant on this pipe's resistance
                    Rt = R.copy(); Rt[j] = Rj
                    dpt, _ = model(Rt)
                    st = ss(dpt)
                    sens = np.where(have, (dpt - dpm) / (Rj - R[j]), 0.0) if Rj != R[j] else None
                    if sens is None or not np.any(sens):
                        break
                    rt = np.where(have, meas - dpt, 0.0)
                    step = np.sum(sens * rt) / np.sum(sens * sens)
                    Rn = max(Rj + step, 1e-9)
                    if abs(Rn - Rj) < 1e-7 * abs(Rj) + 1e-12:
                        Rj = Rn; break
                    Rj = Rn
                Rt = R.copy(); Rt[j] = Rj
                st = ss(model(Rt)[0])
                if best is None or st < best[0]:
                    best = (st, Rt)
            if best is None or best[0] > 0.7 * r0:
                break
            R = best[1]
        self.R = R

    def load_meters(self):
        f = os.path.join(self.pkg, 'meters.csv')
        self.mE = np.full(self.S, np.nan); self.mV = np.full(self.S, np.nan)
        if os.path.exists(f):
            mt = pd.read_csv(f, dtype={'substation': str})
            for s, e, v in zip(mt['substation'], mt['energy_kWh'], mt['volume_m3']):
                if s in self.sid:
                    self.mE[self.sid[s]] = e; self.mV[self.sid[s]] = v
        self.mok = np.isfinite(self.mE) & np.isfinite(self.mV) & (self.mV > 0) & (self.mE > 0)
        self.flagged = np.zeros(self.S, bool)
        self.nrestart = 0
        self.lim_E = None

    def meter_check(self, hTs, hQ, hm, nst):
        """Compare the first 24 h with the heat meters; adjust the return temperature (and, where the
        valve limits, the valve capacity) of a substation that does not fit. True = run again."""
        if self.nrestart >= 6 or not self.mok.any():
            return False
        ok, E, Vv = self.mok, self.mE, self.mV
        Mm = hm[1:nst + 1].sum(0) * DT
        Em = hQ[1:nst + 1].sum(0) * DT / 3600.0
        relV = np.where(ok, Mm / RHO / np.where(ok, Vv, 1) - 1.0, 0.0)
        relE = np.where(ok, Em / np.where(ok, E, 1) - 1.0, 0.0)
        err = np.maximum(np.abs(relV), np.abs(relE))
        thr = max(0.005, 0.3 * float(err[ok & (Mm > 0)].max(initial=0.0)))
        self.flagged |= ok & (err > thr) & (Mm > 0)
        bad = self.flagged & (err > 0.001) & ok & (Mm > 0)
        if not bad.any():
            return False
        Tnw = (hm[1:nst + 1] * hTs[1:nst + 1]).sum(0) * DT / np.where(Mm > 0, Mm, 1)
        dT_meter = E * 3600.0 / (CP * Vv * RHO)
        newTr = self.Tr.copy()
        newTr[bad] = Tnw[bad] - dT_meter[bad]
        # energy that the valve held back: scale the valve capacity of valve-limited substations
        newK = self.K.copy()
        if self.lim_E is not None:
            limE = self.lim_E
            fix = bad & (np.abs(relE) > 0.0015) & (limE > 0.02 * Em)
            if fix.any():
                fac = 1.0 + (E[fix] - Em[fix]) / limE[fix]
                newK[fix] = self.K[fix] * np.clip(fac, 0.5, 2.0)
        if os.environ.get('HN_DEBUG'):
            print('meters', self.nrestart, [(self.subs[i], round(self.Tr[i], 3), round(newTr[i], 3), round(relV[i], 5), round(relE[i], 5), self.K[i], newK[i]) for i in np.where(bad)[0]], file=sys.stderr)
        if np.max(np.abs(newTr - self.Tr)) < 0.02 and np.max(np.abs(newK / self.K - 1)) < 1e-3:
            return False
        self.Tr = newTr; self.K = newK
        self.nrestart += 1
        return True


def main():
    pkg, out = sys.argv[1], sys.argv[2]
    net = Net(pkg)
    pts = pd.read_csv(os.path.join(pkg, 'points.csv'), dtype={'point': str, 'item': str, 'quantity': str})
    tmax = float(pts['time_h'].max()) if len(pts) else 1.0
    nsteps = max(int(round(tmax * SPH)), 1)
    n24 = 24 * SPH
    sched = net.schedules(max(nsteps, n24))
    R0, Tr0 = net.R.copy(), net.Tr.copy()
    try:
        net.calibrate_resistance()
    except Exception:
        net.R = R0
    net.load_meters()
    nrun = max(nsteps, n24)
    sch = tuple(x[:nrun] for x in sched)
    res = None
    K0 = net.K.copy()
    try:
        while res is None:
            res = net.run(nrun, sch, n24, net.meter_check)
    except Exception:
        net.Tr, net.K = Tr0, K0
        res = net.run(nrun, sch)
    hTs, hTr, hQ, hm, hpr = res
    cumQ = np.cumsum(hQ, axis=0)
    vals = []
    for t, item, qty in zip(pts['time_h'], pts['item'], pts['quantity']):
        k = min(max(int(round(float(t) * SPH)), 0), nsteps)
        if str(item).lower() == 'plant':
            vals.append(hpr[k]); continue
        s = net.sid[item]
        if qty == 'supply_C':
            vals.append(hTs[k, s])
        elif qty == 'return_C':
            vals.append(hTr[k, s])
        else:
            vals.append((cumQ[k, s] - cumQ[max(k - SPH, 0), s]) / SPH)
    pd.DataFrame({'point': pts['point'], 'value': vals}).to_csv(out, index=False, float_format='%.6f')


if __name__ == '__main__':
    main()
