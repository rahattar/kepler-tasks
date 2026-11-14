#!/usr/bin/env python3
"""District airflow to VS-4.

Usage: python3 airflow.py PACKAGE_DIR OUT_CSV
"""
import sys, os, shutil, json, subprocess, io
from collections import deque
import numpy as np
import pandas as pd
import scipy.sparse as sp
import scipy.linalg as sla


def load(pkg):
    rd = lambda f: pd.read_csv(os.path.join(pkg, f), dtype={'setting': str})
    return dict(
        dist=json.load(open(os.path.join(pkg, 'district.json'))),
        br=pd.read_csv(os.path.join(pkg, 'branches.csv')),
        sv=pd.read_csv(os.path.join(pkg, 'surveys.csv')),
        wk=pd.read_csv(os.path.join(pkg, 'work_log.csv')),
        reg=pd.read_csv(os.path.join(pkg, 'regulators.csv')),
        door=pd.read_csv(os.path.join(pkg, 'doors.csv')),
        fans=pd.read_csv(os.path.join(pkg, 'fans.csv')),
        curves=pd.read_csv(os.path.join(pkg, 'fan_curves.csv')),
        log=rd('log.csv'),
        pts=pd.read_csv(os.path.join(pkg, 'points.csv')),
    )


def airway_resistances(pkg, d):
    br, sv, wk = d['br'], d['sv'], d['wk']
    airways = list(br.loc[br.kind == 'airway', 'branch'])
    sv = sv.sort_values('date', kind='stable')
    last = {}
    for r in sv.itertuples(index=False):
        last[r.branch] = (r.date, r.dp_Pa, r.q_m3_s)
    work = wk[wk.work.isin(['RESUPPORTED', 'ENLARGED'])].groupby('branch').date.max().to_dict()
    need = [a for a in airways if a in work and (a not in last or last[a][0] <= work[a])]
    need += [a for a in airways if a not in last and a not in need]
    R = {a: v[1] / (v[2] * abs(v[2])) for a, v in last.items() if v[2] != 0}
    allow = int(d['dist'].get('survey_allowance', 0))
    order = need[:allow]
    if order:
        try:
            exe = shutil.which('pqsurvey') or '/tmp/vfc_lb/app/pqsurvey'
            out = subprocess.run([exe, pkg] + order, capture_output=True, text=True, timeout=25)
            df = pd.read_csv(io.StringIO(out.stdout))
            for r in df.itertuples(index=False):
                if r.q_m3_s != 0:
                    R[str(r.branch)] = r.dp_Pa / (r.q_m3_s * abs(r.q_m3_s))
        except Exception as e:
            sys.stderr.write('survey order failed: %r\n' % (e,))
    return R


class Fan:
    def __init__(self, q, p, Rd):
        q = np.asarray(q, float); p = np.asarray(p, float)
        self.Rd = Rd
        n = len(q)
        # dip: first local minimum; peak: following local maximum
        i = 1
        while i < n - 1 and not (p[i] <= p[i - 1] and p[i] < p[i + 1]):
            i += 1
        dip = i
        j = dip + 1
        while j < n - 1 and not (p[j] >= p[j - 1] and p[j] > p[j + 1]):
            j += 1
        peak = j
        self.qdip, self.qpeak = q[dip], q[peak]
        K = max(np.max(np.abs(np.diff(p) / np.diff(q))), 1.0) * 3
        big = 1e5
        # part 0: beyond peak (high flow); part 1: short of dip (low flow)
        qh = q[peak:]; ph = p[peak:]
        s_end = (ph[-1] - ph[-2]) / (qh[-1] - qh[-2])
        qh2 = np.r_[-big, qh, big]
        ph2 = np.r_[ph[0] + K * (qh[0] + big), ph, ph[-1] + s_end * (big - qh[-1])]
        ql = q[:dip + 1]; pl = p[:dip + 1]
        s0 = (pl[1] - pl[0]) / (ql[1] - ql[0])
        ql2 = np.r_[-big, ql, big]
        pl2 = np.r_[pl[0] - s0 * (ql[0] + big), pl, pl[-1] - K * (big - ql[-1])]
        self.parts = []
        for qq, pp in ((qh2, ph2), (ql2, pl2)):
            sl = np.diff(pp) / np.diff(qq)
            cum = np.r_[0, np.cumsum(0.5 * (pp[1:] + pp[:-1]) * np.diff(qq))]
            # shift so integral is relative to q=0
            k0 = np.searchsorted(qq, 0.0, side='right') - 1
            c0 = cum[k0] + pp[k0] * (0 - qq[k0]) + 0.5 * sl[k0] * (0 - qq[k0]) ** 2
            self.parts.append((qq, pp, sl, cum - c0))

    def eval(self, part, q):
        qq, pp, sl, cum = self.parts[part]
        k = np.clip(np.searchsorted(qq, q, side='right') - 1, 0, len(sl) - 1)
        dq = q - qq[k]
        P = pp[k] + sl[k] * dq
        I = cum[k] + pp[k] * dq + 0.5 * sl[k] * dq * dq
        return P, sl[k], I

    def outside(self, part, q, tol=1e-9):
        if part == 0:
            return q < self.qpeak - tol
        return q > self.qdip + tol


class Network:
    def __init__(self, br, fans_by_branch):
        names = list(br.branch)
        self.nb = len(names)
        fr = list(br.from_node); to = list(br.to_node)
        nodes = sorted(set(fr) | set(to))
        idx = {n: i for i, n in enumerate(nodes)}
        f = np.array([idx[x] for x in fr]); t = np.array([idx[x] for x in to])
        adj = [[] for _ in nodes]
        for b in range(self.nb):
            adj[f[b]].append(b); adj[t[b]].append(b)
        root = idx.get('ATM', 0)
        parent = [-1] * len(nodes); pb = [-1] * len(nodes); depth = [0] * len(nodes)
        seen = [False] * len(nodes); seen[root] = True
        tree = np.zeros(self.nb, bool)
        # prefer low-resistance-ish branches in tree: fans/airways first
        dq = deque([root])
        while dq:
            u = dq.popleft()
            for b in adj[u]:
                v = t[b] if f[b] == u else f[b]
                if not seen[v]:
                    seen[v] = True; parent[v] = u; pb[v] = b; depth[v] = depth[u] + 1
                    tree[b] = True; dq.append(v)
        chords = np.where(~tree)[0]
        C = np.zeros((self.nb, len(chords)))
        for l, c in enumerate(chords):
            C[c, l] = 1.0
            # loop: chord from f->t, then path t -> f through tree
            a, bnode = t[c], f[c]
            # walk a up and b up to LCA; path from a to b
            pa, pbn = [], []
            while depth[a] > depth[bnode]:
                pa.append((a, True)); a = parent[a]
            while depth[bnode] > depth[a]:
                pbn.append((bnode, False)); bnode = parent[bnode]
            while a != bnode:
                pa.append((a, True)); a = parent[a]
                pbn.append((bnode, False)); bnode = parent[bnode]
            # going from t[c] upward: traverse tree branch pb[v] from v to parent[v]
            for v, _ in pa:
                e = pb[v]
                C[e, l] += 1.0 if f[e] == v else -1.0
            # going downward from LCA to f[c]: traverse from parent[v] to v
            for v, _ in pbn:
                e = pb[v]
                C[e, l] += 1.0 if t[e] == v else -1.0
        self.C = C
        self.Cs = sp.csr_matrix(C)
        self.CsT = sp.csr_matrix(C.T)
        self.fanb = fans_by_branch  # list of (branch index, Fan)
        self.isfan = np.zeros(self.nb, bool)
        for b, _ in fans_by_branch:
            self.isfan[b] = True

    def solve(self, R, parts, x0):
        C = self.Cs
        CT = self.CsT
        x = x0.copy()

        def ev(x):
            q = C @ x
            h = R * q * np.abs(q)
            dh = 2 * R * np.abs(q)
            phi = np.sum(R * np.abs(q) ** 3) / 3.0
            for (b, fan), part in zip(self.fanb, parts):
                P, s, I = fan.eval(part, q[b])
                h[b] -= P; dh[b] -= s; phi -= I
            return q, h, dh, phi

        q, h, dh, phi = ev(x)
        for it in range(200):
            g = CT @ h
            Dm = np.maximum(dh, 1e-7)
            J = (CT @ sp.diags(Dm) @ C).toarray()
            try:
                step = -sla.cho_solve(sla.cho_factor(J, check_finite=False), g, check_finite=False)
            except np.linalg.LinAlgError:
                step = -np.linalg.solve(J + 1e-9 * np.eye(len(g)), g)
            a = 1.0
            slope = g @ step
            while True:
                xn = x + a * step
                qn, hn, dhn, phin = ev(xn)
                if phin <= phi + 1e-4 * a * slope or a < 1e-8:
                    break
                a *= 0.5
            dx = np.max(np.abs(a * step))
            x, q, h, dh, phi = xn, qn, hn, dhn, phin
            if dx < 1e-7 * max(1.0, np.max(np.abs(q))) and a == 1.0:
                break
            if dx < 1e-11:
                break
        return x, q


def main():
    pkg, out = sys.argv[1], sys.argv[2]
    d = load(pkg)
    br = d['br']
    names = list(br.branch)
    bidx = {n: i for i, n in enumerate(names)}
    Rair = airway_resistances(pkg, d)

    regtab = {}
    for r in d['reg'].itertuples(index=False):
        regtab.setdefault(r.regulator, {})[int(r.setting)] = r.resistance_Ns2_m8
    doortab = {r.door: (r.resistance_closed_Ns2_m8, r.resistance_open_Ns2_m8)
               for r in d['door'].itertuples(index=False)}
    curves = d['curves']
    fanlist = []
    for r in d['fans'].itertuples(index=False):
        c = curves[(curves.model == r.model) & (curves.blade_setting.astype(str) == str(r.blade_setting))]
        b = bidx[r.branch]
        Rd = br.resistance_Ns2_m8.iloc[b]
        Rd = 0.0 if pd.isna(Rd) else float(Rd)
        fanlist.append((b, Fan(c.flow_m3_s.values, c.pressure_Pa.values, Rd)))

    R = np.zeros(len(names))
    item_branches = {}
    for i, r in enumerate(br.itertuples(index=False)):
        if r.kind == 'airway':
            R[i] = Rair.get(r.branch, 0.0)
        elif r.kind in ('stopping', 'fan'):
            R[i] = 0.0 if pd.isna(r.resistance_Ns2_m8) else float(r.resistance_Ns2_m8)
        if isinstance(r.item, str) and r.kind in ('regulator', 'door'):
            item_branches.setdefault(r.item, []).append(i)

    def item_R(item, setting):
        s = str(setting).strip()
        if item in doortab:
            return doortab[item][0] if s.lower() == 'closed' else doortab[item][1]
        return regtab[item][int(float(s))]

    log = d['log']
    times = sorted(log.time.unique())
    groups = {t: g for t, g in log.groupby('time')}
    for r in groups[times[0]].itertuples(index=False):
        for b in item_branches.get(r.item, []):
            R[b] = item_R(r.item, r.setting)

    net = Network(br, fanlist)
    nl = net.C.shape[1]
    parts = [0] * len(fanlist)

    def settle(R, parts, x):
        # solve; if a fan has left its part, switch the worst one and re-settle
        for _ in range(4 * len(parts) + 2):
            x, q = net.solve(R, parts, x)
            worst, wv = -1, 0.0
            for k, (b, fan) in enumerate(fanlist):
                if fan.outside(parts[k], q[b]):
                    v = (fan.qpeak - q[b]) if parts[k] == 0 else (q[b] - fan.qdip)
                    if v > wv:
                        worst, wv = k, v
            if worst < 0:
                return x, q, parts
            parts = list(parts); parts[worst] = 1 - parts[worst]
        return x, q, parts

    # initial guess: share fan flow through one loop each
    x = np.zeros(nl)
    for b, fan in fanlist:
        cols = np.where(net.C[b] != 0)[0]
        if len(cols):
            x[cols[0]] += 0.5 * (fan.qpeak + fan.parts[0][0][-2]) * net.C[b, cols[0]]
    x, q, parts = settle(R, parts, x)
    states = [(times[0], q.copy())]
    for t in times[1:]:
        g = groups[t]
        Rold = R.copy()
        for r in g.itertuples(index=False):
            for b in item_branches.get(r.item, []):
                R[b] = item_R(r.item, r.setting)
        xn, qn = net.solve(R, parts, x)
        crossed = any(fan.outside(parts[k], qn[b]) for k, (b, fan) in enumerate(fanlist))
        if crossed:
            # follow the change gradually to find which fan reaches its end first
            Rn = R.copy()
            lo, hi = np.log(np.maximum(Rold, 1e-12)), np.log(np.maximum(Rn, 1e-12))
            xs = x
            nsub = 24
            for s in range(1, nsub + 1):
                Rs = np.where(Rold == Rn, Rn, np.exp(lo + (hi - lo) * s / nsub))
                if s == nsub:
                    Rs = Rn
                xs, qs, parts = settle(Rs, parts, xs)
            x, q = xs, qs
        else:
            x, q = xn, qn
        states.append((t, q.copy()))

    st_times = np.array([s[0] for s in states])
    Q = np.array([s[1] for s in states])
    pts = d['pts']
    k = np.searchsorted(st_times, pts.time.values.astype(str), side='right') - 1
    k = np.clip(k, 0, len(states) - 1)
    bi = np.array([bidx[b] for b in pts.branch])
    vals = Q[k, bi]
    with open(out, 'w') as fh:
        fh.write('point,flow_m3_s\n')
        for p, v in zip(pts.point, vals):
            fh.write('%s,%.5f\n' % (p, v))


if __name__ == '__main__':
    main()
