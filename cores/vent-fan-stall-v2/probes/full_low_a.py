#!/usr/bin/env python3
"""Airflow at every survey point of a district package, to VS-4."""
import sys, os, json, subprocess
import numpy as np
import pandas as pd
import scipy.sparse as sp
import scipy.sparse.linalg as spla

P0 = 1000.0  # reference fan-house suction for the passive (mine) solve


def load(pkg, do_survey=True):
    P = lambda f: os.path.join(pkg, f)
    D = {}
    dist = json.load(open(P('district.json')))
    br = pd.read_csv(P('branches.csv'), dtype={'item': str, 'branch': str, 'from_node': str, 'to_node': str})
    br['kind'] = br.kind.str.strip().str.lower()
    sv = pd.read_csv(P('surveys.csv'), dtype={'date': str, 'branch': str})
    wl = pd.read_csv(P('work_log.csv'), dtype={'date': str, 'branch': str, 'work': str})
    regs = pd.read_csv(P('regulators.csv'), dtype={'regulator': str})
    doors = pd.read_csv(P('doors.csv'), dtype={'door': str})
    fans = pd.read_csv(P('fans.csv'), dtype={'fan': str, 'branch': str, 'model': str})
    curves = pd.read_csv(P('fan_curves.csv'), dtype={'model': str})
    log = pd.read_csv(P('log.csv'), dtype={'time': str, 'setting': str, 'item': str})
    pts = pd.read_csv(P('points.csv'), dtype={'time': str, 'point': str, 'branch': str})

    nb = len(br)
    bidx = {b: i for i, b in enumerate(br.branch)}
    kinds = br.kind.values

    # ---- airway resistances (VS-4 s3) ----
    sv = sv.sort_values('date', kind='stable')
    latest = {}
    for r in sv.itertuples():
        latest[r.branch] = (r.date, float(r.dp_Pa), float(r.q_m3_s))
    lastwork = {}
    for r in wl.itertuples():
        if str(r.work).strip().upper() in ('RESUPPORTED', 'ENLARGED'):
            if r.date > lastwork.get(r.branch, ''):
                lastwork[r.branch] = r.date
    need = [b for b in br.branch[br.kind == 'airway']
            if b not in latest or lastwork.get(b, '') >= latest[b][0]]
    allow = int(dist.get('survey_allowance', 0))
    fresh = {}
    if need and allow > 0 and do_survey:
        # unsurveyed airways first, then the most recently worked
        need.sort(key=lambda b: (b in latest,))
        order = need[:allow]
        try:
            res = subprocess.run(['pqsurvey', pkg] + order, capture_output=True, text=True, timeout=25)
            for line in res.stdout.strip().splitlines():
                parts = [x.strip() for x in line.split(',')]
                if len(parts) != 3:
                    continue
                try:
                    fresh[parts[0]] = (float(parts[1]), float(parts[2]))
                except ValueError:
                    pass
        except Exception:
            pass
        if len(fresh) < len(order):
            sys.stderr.write('pqsurvey answered %d of %d\n' % (len(fresh), len(order)))
    if len(need) > allow:
        sys.stderr.write('%d airways need survey, allowance %d\n' % (len(need), allow))

    def rof(dp, q):
        return abs(dp / (q * abs(q))) if q != 0 else np.nan

    R = np.zeros(nb)
    for i, r in enumerate(br.itertuples()):
        if r.kind == 'airway':
            v = np.nan
            if r.branch in fresh:
                v = rof(*fresh[r.branch])
            elif r.branch in latest:
                v = rof(latest[r.branch][1], latest[r.branch][2])
            R[i] = v if np.isfinite(v) and v > 0 else 1e-6
        elif r.kind in ('stopping', 'fan'):
            R[i] = float(r.resistance_Ns2_m8) if pd.notna(r.resistance_Ns2_m8) else 0.0

    regtab = {(a, int(s)): float(v) for a, s, v in regs[['regulator', 'setting', 'resistance_Ns2_m8']].itertuples(index=False)}
    doortab = {d: (float(c), float(o)) for d, c, o in doors.itertuples(index=False)}

    def item_R(item, setting):
        s = str(setting).strip().lower()
        if item in doortab:
            return doortab[item][0] if s.startswith('c') else doortab[item][1]
        return regtab[(item, int(round(float(s))))]

    item_to_br = {}
    for i in range(nb):
        if kinds[i] in ('regulator', 'door'):
            item_to_br.setdefault(br.item.iloc[i], []).append(i)

    # fans
    fanlist = []  # (branch index, x, y, Rduct)
    for f in fans.itertuples():
        c = curves[(curves.model == f.model) & (curves.blade_setting.astype(float) == float(f.blade_setting))]
        c = c.sort_values('flow_m3_s', kind='stable')
        i = bidx[f.branch]
        fanlist.append((i, c.flow_m3_s.values.astype(float), c.pressure_Pa.values.astype(float), R[i]))

    D.update(br=br, nb=nb, bidx=bidx, R=R, item_R=item_R, item_to_br=item_to_br,
             fanlist=fanlist, log=log, pts=pts)
    return D


class Mine:
    """Passive network with the fans replaced by a fixed suction P0 at the fan house."""

    def __init__(self, D):
        br = D['br']; nb = D['nb']
        self.fidx = np.array([f[0] for f in D['fanlist']], dtype=int)
        self.fh = set(br.from_node.iloc[self.fidx]) | set(br.to_node.iloc[self.fidx])
        self.fh.discard('ATM')
        nodes = sorted((set(br.from_node) | set(br.to_node)) - {'ATM'})
        nidx = {n: k for k, n in enumerate(nodes)}
        self.nn = len(nodes)
        rows, cols, vals = [], [], []
        for i, r in enumerate(br.itertuples()):
            if r.from_node != 'ATM':
                rows.append(nidx[r.from_node]); cols.append(i); vals.append(1.0)
            if r.to_node != 'ATM':
                rows.append(nidx[r.to_node]); cols.append(i); vals.append(-1.0)
        self.A = sp.csr_matrix((vals, (rows, cols)), shape=(self.nn, nb))
        self.AT = self.A.T.tocsr()
        self.nb = nb
        self.sgn = np.zeros(nb)  # fan direction sign
        for i in self.fidx:
            self.sgn[i] = 1.0

    def solve(self, Rv, q0):
        """Fan branches: constant pressure P0, negligible resistance. Returns q."""
        Rv = Rv.copy()
        Rv[self.fidx] = 1e-9
        Pf = np.zeros(self.nb); Pf[self.fidx] = P0
        q = q0.copy(); p = np.zeros(self.nn)
        A, AT = self.A, self.AT
        for it in range(100):
            f1 = AT @ p - Rv * q * np.abs(q) + Pf
            f2 = A @ q
            if it > 0 and np.abs(f1).max() < 1e-9 * P0 and np.abs(f2).max() < 1e-9 * max(1.0, np.abs(q).max()):
                break
            d = -2 * Rv * np.maximum(np.abs(q), 1e-4)
            Dinv = 1.0 / d
            S = (A @ sp.diags(Dinv) @ AT).tocsc()
            rhs = -f2 + A @ (Dinv * f1)
            dp = spla.spsolve(-S, rhs)
            dq = -(f1 + AT @ dp) * Dinv
            m = np.abs(dq).max()
            lim = max(0.5 * np.abs(q).max(), 1.0)
            a = 1.0 if m <= lim else lim / m
            q = q + a * dq; p = p + a * dp
        return q


def fan_h(x, y, Rd):
    """Fan-house suction delivered by a fan with its ducting, as segments of q."""
    return x, y - Rd * x * x


def build_states(D):
    log = D['log'].copy()
    log['_o'] = np.arange(len(log))
    log = log.sort_values(['time', '_o'], kind='stable')
    R = D['R'].copy()
    states = []
    for t, g in log.groupby('time', sort=True):
        ch = []
        for r in g.itertuples():
            for i in D['item_to_br'].get(r.item, []):
                ch.append((i, R[i], D['item_R'](r.item, r.setting)))
                R[i] = ch[-1][2]
        states.append((t, R.copy(), ch))
    return states


def fan_states(D, Req):
    """Quasi-steady following of the fans from state to state (VS-4 s4-5): the fans carry
    their operating point from the previous state, so a stalled fan stays stalled until
    its stalled operating point no longer exists, and vice versa."""
    from scipy.integrate import solve_ivp
    F = D['fanlist']

    def H(q):
        return np.array([np.interp(qq, x, y) - Rd * qq * qq for qq, (i, x, y, Rd) in zip(q, F)])

    def dH(q):
        out = []
        for qq, (i, x, y, Rd) in zip(q, F):
            k = int(np.clip(np.searchsorted(x, qq) - 1, 0, len(x) - 2))
            out.append((y[k + 1] - y[k]) / (x[k + 1] - x[k]) - 2 * Rd * qq)
        return np.array(out)

    def rhs(t, q, r):
        return (H(q) - r * q.sum() ** 2) / 50.0

    q = np.array([f[1][-1] * 0.8 for f in F])
    res = []
    prev_r = None
    for r in Req:
        if prev_r is None or abs(r - prev_r) > 1e-12 * r:
            s = solve_ivp(rhs, (0, 500), q, args=(r,), method='LSODA', rtol=1e-9, atol=1e-7)
            qn = s.y[:, -1]
            # polish with Newton on the same operating branch
            for _ in range(20):
                f = H(qn) - r * qn.sum() ** 2
                J = np.diag(dH(qn)) - 2 * r * qn.sum()
                try:
                    dq = np.linalg.solve(J, -f)
                except np.linalg.LinAlgError:
                    break
                if np.abs(dq).max() > 1.0:
                    break
                qn = qn + dq
                if np.abs(dq).max() < 1e-10:
                    break
            q = qn
        prev_r = r
        res.append(q.copy())
    return res


def main():
    pkg, out = sys.argv[1], sys.argv[2]
    D = load(pkg)
    M = Mine(D)
    S = build_states(D)
    st_times = [s[0] for s in S]
    pts = D['pts']
    kpt = np.maximum(np.searchsorted(st_times, pts.time.values, side='right') - 1, 0)
    needed = set(kpt.tolist())
    q = np.ones(D['nb'])
    Req = []
    U = {}
    for k, (t, R, ch) in enumerate(S):
        q = M.solve(R, q)
        Q = q[M.fidx].sum()
        Req.append(P0 / Q ** 2)
        if k in needed:
            U[k] = q.copy()
    FQ = fan_states(D, Req)
    fidx = M.fidx
    bidx = D['bidx']
    with open(out, 'w') as fh:
        fh.write('point,flow_m3_s\n')
        cache = {}
        for pt, br_, k in zip(pts.point.values, pts.branch.values, kpt):
            if k not in cache:
                qf = FQ[k]
                ptot = Req[k] * qf.sum() ** 2
                v = U[k] * np.sqrt(ptot / P0)
                v[fidx] = qf
                cache[k] = v
            fh.write('%s,%.4f\n' % (pt, cache[k][bidx[br_]]))


if __name__ == '__main__':
    main()
