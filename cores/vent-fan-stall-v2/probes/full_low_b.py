#!/usr/bin/env python3
"""Airflow at every survey point of a district package, to VS-4."""
import sys, os, json, subprocess
import numpy as np
import pandas as pd
import scipy.sparse as sp
import scipy.sparse.linalg as spla

WORKS = ('RESUPPORTED', 'ENLARGED')


def load(pkg):
    rd = lambda f: pd.read_csv(os.path.join(pkg, f), dtype=str, keep_default_na=False)
    with open(os.path.join(pkg, 'district.json')) as fh:
        dist = json.load(fh)
    return dist, {f: rd(f + '.csv') for f in
                  ('branches', 'surveys', 'work_log', 'regulators', 'doors',
                   'fans', 'fan_curves', 'log', 'points')}


def airway_resistances(pkg, dist, t):
    br = t['branches']
    airways = list(br.loc[br.kind == 'airway', 'branch'])
    sv = t['surveys'].copy()
    sv['dp'] = sv.dp_Pa.astype(float)
    sv['q'] = sv.q_m3_s.astype(float)
    sv = sv.sort_values('date', kind='stable')
    last = {}
    for r in sv.itertuples():
        last[r.branch] = (r.date, r.dp, r.q)
    wl = t['work_log']
    lastwork = {}
    for r in wl.itertuples():
        if r.work.strip().upper() in WORKS:
            if r.branch not in lastwork or r.date > lastwork[r.branch]:
                lastwork[r.branch] = r.date
    need = []
    for a in airways:
        if a not in last:
            need.append(a)
        elif a in lastwork and lastwork[a] > last[a][0]:
            need.append(a)
    for a in airways:   # work on the day of the latest survey: order unknown, lower priority
        if a in last and a in lastwork and lastwork[a] == last[a][0]:
            need.append(a)
    R = {}
    for a in airways:
        if a in last:
            d, dp, q = last[a]
            R[a] = dp / (q * abs(q)) if q != 0 else np.nan
    if need:
        allow = int(dist.get('survey_allowance', len(need)))
        order = need[:allow]
        try:
            out = subprocess.run(['pqsurvey', pkg] + order, capture_output=True,
                                 text=True, timeout=20).stdout
            for line in out.strip().splitlines():
                p = line.strip().split(',')
                if len(p) != 3 or p[0] == 'branch':
                    continue
                try:
                    dp, q = float(p[1]), float(p[2])
                except ValueError:
                    continue
                if q != 0:
                    R[p[0]] = dp / (q * abs(q))
        except Exception as e:
            sys.stderr.write('pqsurvey failed: %s\n' % e)
    return R


class Fan:
    def __init__(self, q, p):
        o = np.argsort(q, kind='stable')
        self.q = np.asarray(q, float)[o]
        self.p = np.asarray(p, float)[o]
        self.s = np.diff(self.p) / np.diff(self.q)

    def __call__(self, x):
        i = np.clip(np.searchsorted(self.q, x, side='right') - 1, 0, len(self.s) - 1)
        return self.p[i] + self.s[i] * (x - self.q[i]), self.s[i]


def solve_passive(A, AT, R, b0, q, p, tol=1e-9):
    """Square-law network: f = R q|q| + AT p - b0 = 0, A q = 0 (unknown nodes)."""
    def res(q, p):
        return R * q * np.abs(q) + AT @ p - b0, A @ q
    f, g = res(q, p)
    nr = np.sqrt(f @ f + g @ g)
    for it in range(100):
        d = np.maximum(2 * R * np.abs(q), 1e-4 * R + 1e-9)
        Di = 1.0 / d
        M = (A @ sp.diags(Di) @ AT).tocsc()
        rhs = g - A @ (Di * f)
        dpv = spla.spsolve(M, rhs)
        dq = Di * (-f - AT @ dpv)
        lam = 1.0
        while True:
            qn, pn = q + lam * dq, p + lam * dpv
            fn, gn = res(qn, pn)
            nn = np.sqrt(fn @ fn + gn @ gn)
            if nn < nr or lam < 1e-4:
                break
            lam *= 0.5
        q, p, f, g, nr = qn, pn, fn, gn, nn
        if np.max(np.abs(lam * dq)) < tol * (1 + np.max(np.abs(q))):
            break
    return q, p


class FanSet:
    """Parallel fans at one fan house: h_i(q_i) = P_i(q_i) - Rd_i q_i|q_i| = p_house."""
    def __init__(self, fans, Rd):
        self.fans, self.Rd = fans, np.asarray(Rd, float)
        self.n = len(fans)

    def h(self, q):
        hv = np.empty(self.n); hs = np.empty(self.n)
        for k, f in enumerate(self.fans):
            P, s = f(q[k])
            hv[k] = P - self.Rd[k] * q[k] * abs(q[k])
            hs[k] = s - 2 * self.Rd[k] * abs(q[k])
        return hv, hs

    def rhs(self, q, Rs):
        hv, hs = self.h(q)
        Q = q.sum()
        return hv - Rs * Q * abs(Q), hs, 2 * Rs * abs(Q)

    def stable(self, q, Rs):
        _, hs, c = self.rhs(q, Rs)
        J = np.diag(hs) - c
        return np.all(np.linalg.eigvals(J).real < 0)

    def newton(self, q, Rs):
        q = q.copy()
        for it in range(30):
            F, hs, c = self.rhs(q, Rs)
            J = np.diag(hs) - c
            try:
                dq = np.linalg.solve(J, -F)
            except np.linalg.LinAlgError:
                return None
            q = q + dq
            if np.max(np.abs(dq)) < 1e-9 * (1 + np.abs(q).max()):
                F, _, _ = self.rhs(q, Rs)
                if np.max(np.abs(F)) < 1e-6:
                    return q
        return None

    def relax(self, q, Rs, steps=60000):
        q = q.copy()
        for it in range(steps):
            F, hs, c = self.rhs(q, Rs)
            rate = np.max(np.abs(hs)) + c * self.n + 1e-6
            dt = 0.2 / rate
            q = q + dt * F
            if it % 20 == 0:
                qn = self.newton(q, Rs)
                if qn is not None and self.stable(qn, Rs) and np.max(np.abs(qn - q)) < 1.0:
                    return qn
        return q

    def track(self, q, Rs_old, Rs_new, nsub=40):
        for k in range(1, nsub + 1):
            Rs = Rs_old + (Rs_new - Rs_old) * k / nsub
            qn = self.newton(q, Rs)
            if qn is None or not self.stable(qn, Rs) or np.max(np.abs(qn - q)) > 3.0:
                qn = self.relax(q, Rs)
            q = qn
        return q


def main():
    pkg, out_csv = sys.argv[1], sys.argv[2]
    dist, t = load(pkg)
    br = t['branches']
    names = list(br.branch)
    bidx = {b: i for i, b in enumerate(names)}
    kinds = list(br.kind)
    fanrows = [i for i in range(len(names)) if kinds[i] == 'fan']
    house = br.from_node.iloc[fanrows[0]]
    net = [i for i in range(len(names)) if kinds[i] != 'fan']
    nb = len(net)
    nidx_net = {names[b]: k for k, b in enumerate(net)}
    nodes = sorted((set(br.from_node.iloc[net]) | set(br.to_node.iloc[net])) - {'ATM', house})
    nidx = {n: i for i, n in enumerate(nodes)}
    N = len(nodes)
    P0 = 1000.0
    rows, cols, vals = [], [], []
    b0 = np.zeros(nb)       # known part: p_from - p_to = R q|q|  ->  R q|q| + AT p - b0 = 0
    for k, i in enumerate(net):
        fn, tn = br.from_node.iloc[i], br.to_node.iloc[i]
        if fn in nidx:
            rows.append(nidx[fn]); cols.append(k); vals.append(-1.0)
        if tn in nidx:
            rows.append(nidx[tn]); cols.append(k); vals.append(1.0)
        # AT p gives p_to - p_from for unknown nodes; known p: ATM 0, house -P0
        pf = -P0 if fn == house else 0.0
        pt = -P0 if tn == house else 0.0
        b0[k] = pf - pt
    A = sp.csr_matrix((vals, (rows, cols)), shape=(N, nb))
    AT = A.T.tocsr()
    into_house = np.array([1.0 if br.to_node.iloc[i] == house else
                           (-1.0 if br.from_node.iloc[i] == house else 0.0) for i in net])

    Rair = airway_resistances(pkg, dist, t)
    R = np.zeros(nb)
    items = list(br.item)
    for k, i in enumerate(net):
        kd = kinds[i]
        if kd == 'airway':
            R[k] = Rair.get(names[i], np.nan)
        elif kd == 'stopping':
            R[k] = float(br.resistance_Ns2_m8.iloc[i])
    R[np.isnan(R)] = 1e-3

    regtab, doortab = {}, {}
    for r in t['regulators'].itertuples():
        regtab[(r.regulator, int(float(r.setting)))] = float(r.resistance_Ns2_m8)
    for r in t['doors'].itertuples():
        doortab[(r.door, 'closed')] = float(r.resistance_closed_Ns2_m8)
        doortab[(r.door, 'open')] = float(r.resistance_open_Ns2_m8)
    item_branches = {}
    for k, i in enumerate(net):
        if kinds[i] in ('regulator', 'door'):
            item_branches.setdefault(items[i], []).append(k)

    def setval(item, s):
        s = s.strip().lower()
        if (item, s) in doortab:
            return doortab[(item, s)]
        return regtab[(item, int(float(s)))]

    fc = t['fan_curves']
    fanobjs, Rd, fan_names = [], [], []
    frow = {r.branch: r for r in t['fans'].itertuples()}
    for i in fanrows:
        r = frow[names[i]]
        sub = fc[(fc.model == r.model) &
                 (fc.blade_setting.astype(float) == float(r.blade_setting))]
        fanobjs.append(Fan(sub.flow_m3_s.astype(float).values,
                           sub.pressure_Pa.astype(float).values))
        Rd.append(float(br.resistance_Ns2_m8.iloc[i]))
        fan_names.append(names[i])
    FS = FanSet(fanobjs, Rd)

    log = t['log'].copy()
    log['time'] = log.time.str.strip()
    times = sorted(set(log.time))
    groups = {tm: g for tm, g in log.groupby('time')}

    q = np.ones(nb); p = np.full(N, -P0 / 2)
    qf = None
    Rs_prev = None
    states = []
    for tm in times:
        for r in groups[tm].itertuples():
            for k in item_branches.get(r.item, []):
                R[k] = setval(r.item, r.setting)
        q, p = solve_passive(A, AT, R, b0, q, p)
        Qh = into_house @ q
        Rs = P0 / (Qh * abs(Qh))
        if qf is None:
            qf = np.array([f.q[-1] for f in fanobjs]) * 0.9
            qf = FS.relax(qf, Rs)
        else:
            qf = FS.track(qf, Rs_prev, Rs)
        Rs_prev = Rs
        Qt = qf.sum()
        scale = Qt / Qh
        states.append((q * scale, qf.copy()))

    pts = t['points'].copy()
    pts['time'] = pts.time.str.strip()
    tlist = np.array(times)
    fpos = {b: k for k, b in enumerate(fan_names)}
    with open(out_csv, 'w') as fh:
        fh.write('point,flow_m3_s\n')
        for r in pts.itertuples():
            k = max(np.searchsorted(tlist, r.time, side='right') - 1, 0)
            qs, qfs = states[k]
            if r.branch in fpos:
                v = qfs[fpos[r.branch]]
            else:
                v = qs[nidx_net[r.branch]]
            fh.write('%s,%.5f\n' % (r.point, v))


if __name__ == '__main__':
    main()
