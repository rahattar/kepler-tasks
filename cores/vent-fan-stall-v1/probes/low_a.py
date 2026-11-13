#!/usr/bin/env python3
"""Airflow at every survey point of a district package, to VS-4."""
import sys, os, json, subprocess
import numpy as np
import pandas as pd


def load(pkg):
    rd = lambda f: pd.read_csv(os.path.join(pkg, f), dtype=str, keep_default_na=False)
    return (json.load(open(os.path.join(pkg, 'district.json'))), rd('branches.csv'), rd('surveys.csv'),
            rd('work_log.csv'), rd('regulators.csv'), rd('doors.csv'), rd('fans.csv'),
            rd('fan_curves.csv'), rd('log.csv'), rd('points.csv'))


def airway_resistances(pkg, dist, br, sv, wl):
    airways = list(br.loc[br.kind == 'airway', 'branch'])
    sv = sv.copy()
    sv['dp'] = sv.dp_Pa.astype(float)
    sv['q'] = sv.q_m3_s.astype(float)
    sv = sv[sv.q != 0]
    latest = {}
    for b, g in sv.groupby('branch'):
        g = g.sort_values('date', kind='stable')
        latest[b] = g.iloc[-1]
    work = wl[wl.work.str.strip().str.upper().isin(['RESUPPORTED', 'ENLARGED'])]
    lastwork = work.groupby('branch').date.max().to_dict()
    R, need = {}, []
    for a in airways:
        s = latest.get(a)
        if s is None or (a in lastwork and s.date <= lastwork[a]):
            need.append(a)
        if s is not None:
            R[a] = s.dp / (s.q * abs(s.q))
    if need:
        allow = int(dist.get('survey_allowance', len(need)))
        order = need[:allow]
        try:
            out = subprocess.run(['pqsurvey', pkg] + order, capture_output=True, text=True,
                                 timeout=20).stdout
            for line in out.strip().splitlines():
                p = line.split(',')
                if len(p) < 3 or p[0] == 'branch':
                    continue
                dp, q = float(p[1]), float(p[2])
                if q != 0:
                    R[p[0].strip()] = dp / (q * abs(q))
        except Exception as e:
            sys.stderr.write('pqsurvey failed: %s\n' % e)
        missing = [a for a in need if a not in R]
        if missing:
            sys.stderr.write('no resistance for %s\n' % missing)
    return R


class Fan:
    def __init__(self, q, p):
        self.q = np.asarray(q, float); self.p = np.asarray(p, float)

    def __call__(self, x):
        q, p = self.q, self.p
        i = int(np.clip(np.searchsorted(q, x) - 1, 0, len(q) - 2))
        s = (p[i + 1] - p[i]) / (q[i + 1] - q[i])
        return p[i] + s * (x - q[i]), s

    def region(self, x):
        q, p = self.q, self.p
        i = int(np.clip(np.searchsorted(q, x) - 1, 0, len(q) - 2))
        s = (p[i + 1] - p[i]) / (q[i + 1] - q[i])
        if s > 0:
            return 1
        return 0 if all(p[j + 1] <= p[j] for j in range(i)) else 2


class Net:
    def __init__(self, nodes, frm, to, fans):
        import scipy.sparse as sp
        self.sp = sp
        idx = {n: i for i, n in enumerate([n for n in nodes if n != 'ATM'])}
        nb = len(frm); nn = len(idx)
        self.nb, self.nn = nb, nn
        self.fi = np.array([idx.get(n, -1) for n in frm]); self.ti = np.array([idx.get(n, -1) for n in to])
        rows, cols, vals = [], [], []
        for k in range(nb):
            if self.fi[k] >= 0:
                rows += [k, nb + self.fi[k]]; cols += [nb + self.fi[k], k]; vals += [-1.0, -1.0]
            if self.ti[k] >= 0:
                rows += [k, nb + self.ti[k]]; cols += [nb + self.ti[k], k]; vals += [1.0, 1.0]
        self.off = sp.csc_matrix((vals, (rows, cols)), shape=(nb + nn, nb + nn))
        self.A = self.off[nb:, :nb]
        self.fans = fans
        self.p = np.zeros(nn)

    def resid(self, q, p, R):
        fi, ti = self.fi, self.ti
        pf = np.where(fi >= 0, p[np.maximum(fi, 0)], 0.0)
        pt = np.where(ti >= 0, p[np.maximum(ti, 0)], 0.0)
        h = R * q * np.abs(q); dh = 2 * R * np.abs(q)
        for k, f in self.fans.items():
            P, s = f(q[k]); h[k] -= P; dh[k] -= s
        return h - (pf - pt), dh

    def step(self, q, p, R, qold, Linv_dt):
        """Newton solve of L(q-qold)/dt + h(q) - dp = 0, Aq = 0. Linv_dt = L/dt (0 => steady)."""
        from scipy.sparse.linalg import spsolve
        nb = self.nb
        for it in range(50):
            F1, dh = self.resid(q, p, R)
            F1 = F1 + Linv_dt * (q - qold)
            d = dh + Linv_dt
            d = np.where(np.abs(d) < 1e-8, 1e-8, d)
            J = self.off + self.sp.diags(np.concatenate([d, np.zeros(self.nn)]), format='csc')
            F = np.concatenate([F1, self.A @ q])
            dx = spsolve(J, -F)
            q = q + dx[:nb]; p = p + dx[nb:]
            if np.max(np.abs(dx[:nb])) < 1e-10 * max(1.0, np.max(np.abs(q))):
                return q, p, True
        return q, p, False

    def transient(self, q, p, R):
        dt = 0.02
        for i in range(400):
            qn, pn, ok = self.step(q.copy(), p.copy(), R, q, 1.0 / dt)
            if not ok:
                dt /= 4; continue
            ch = np.max(np.abs(qn - q))
            q, p = qn, pn
            if dt > 1e6 and ch < 1e-9:
                break
            dt *= 2 if ch < 5 else 1
        return q, p


def regions(net, q):
    return tuple(f.region(q[k]) for k, f in net.fans.items())


def main():
    pkg, outcsv = sys.argv[1], sys.argv[2]
    dist, br, sv, wl, rg, dr, fn, fc, lg, pt = load(pkg)
    Rair = airway_resistances(pkg, dist, br, sv, wl)
    regs = {(r.regulator, int(float(r.setting))): float(r.resistance_Ns2_m8) for r in rg.itertuples()}
    doors = {r.door: (float(r.resistance_closed_Ns2_m8), float(r.resistance_open_Ns2_m8)) for r in dr.itertuples()}
    names = list(br.branch); bidx = {b: i for i, b in enumerate(names)}
    frm = list(br.from_node); to = list(br.to_node)
    nodes = sorted(set(frm) | set(to))
    fans = {}
    fc = fc.copy(); fc['q'] = fc.flow_m3_s.astype(float); fc['p'] = fc.pressure_Pa.astype(float)
    for r in fn.itertuples():
        g = fc[(fc.model == r.model) & (fc.blade_setting.astype(float) == float(r.blade_setting))]
        g = g.sort_values('q', kind='stable')
        fans[bidx[r.branch]] = Fan(g.q.values, g.p.values)
    base = np.zeros(len(names)); kinds = list(br.kind); items = list(br.item)
    for k, b in enumerate(names):
        if kinds[k] == 'airway': base[k] = Rair.get(b, np.nan)
        elif kinds[k] in ('stopping', 'fan'): base[k] = float(br.resistance_Ns2_m8[k] or 0)
    # log states
    lg = lg.sort_values('time', kind='stable')
    times = sorted(lg.time.unique())
    state = {}; states = []
    for t in times:
        for r in lg[lg.time == t].itertuples():
            state[r.item] = r.setting.strip()
        states.append(dict(state))
    pt = pt.copy()
    tarr = np.array(times)
    pt['si'] = np.searchsorted(tarr, pt.time.values, side='right') - 1
    net = Net(nodes, frm, to, fans)

    def Rof(st):
        R = base.copy()
        for k in range(len(names)):
            it = items[k]
            if kinds[k] == 'regulator': R[k] = regs[(it, int(float(st[it])))]
            elif kinds[k] == 'door': R[k] = doors[it][0 if st[it].lower() == 'closed' else 1]
        return R
    q = np.full(len(names), 0.0)
    for k in fans: q[k] = fans[k].q[-1] * 0.9
    p = np.zeros(net.nn)
    R = Rof(states[0])
    q, p = net.transient(q, p, R)
    sol = [q]
    NSUB = 16
    for i in range(1, len(states)):
        R1 = Rof(states[i])
        qn, pn, ok = net.step(q.copy(), p.copy(), R1, q, 0.0)
        if ok and regions(net, qn) == regions(net, q) and 1 not in regions(net, qn):
            q, p = qn, pn
        else:
            for j in range(1, NSUB + 1):
                Rj = np.exp(np.log(R) + (np.log(R1) - np.log(R)) * j / NSUB)
                q, p = net.transient(q, p, Rj)
        R = R1
        sol.append(q)
    res = {si: sol[max(si, 0)] for si in pt.si.unique()}
    with open(outcsv, 'w') as f:
        f.write('point,flow_m3_s\n')
        for r in pt.itertuples():
            f.write('%s,%.6f\n' % (r.point, res[r.si][bidx[r.branch]]))


if __name__ == '__main__':
    main()
