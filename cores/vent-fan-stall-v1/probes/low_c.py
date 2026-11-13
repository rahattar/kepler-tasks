#!/usr/bin/env python3
"""Airflow at every survey point of a district package, to VS-4."""
import sys, os, json, csv, subprocess
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spl


def rcsv(path):
    with open(path, newline='') as f:
        return list(csv.DictReader(f))


def main():
    pkg, out = sys.argv[1], sys.argv[2]
    P = lambda n: os.path.join(pkg, n)
    dist = json.load(open(P('district.json')))
    allowance = int(dist.get('survey_allowance', 0))
    branches = rcsv(P('branches.csv'))
    surveys = rcsv(P('surveys.csv'))
    work = rcsv(P('work_log.csv'))
    regs = {}
    for r in rcsv(P('regulators.csv')):
        regs.setdefault(r['regulator'], {})[int(float(r['setting']))] = float(r['resistance_Ns2_m8'])
    doors = {r['door']: (float(r['resistance_closed_Ns2_m8']), float(r['resistance_open_Ns2_m8']))
             for r in rcsv(P('doors.csv'))}
    fans = {r['fan']: r for r in rcsv(P('fans.csv'))}
    curves = {}
    for r in rcsv(P('fan_curves.csv')):
        curves.setdefault((r['model'], r['blade_setting'].strip()), []).append(
            (float(r['flow_m3_s']), float(r['pressure_Pa'])))
    log = rcsv(P('log.csv'))
    points = rcsv(P('points.csv'))

    # --- airway resistances (VS-4 s3) ---
    last = {}
    for s in surveys:
        b = s['branch']
        if b not in last or s['date'] >= last[b]['date']:
            last[b] = s
    lastwork = {}
    for w in work:
        if w['work'].strip().upper() in ('RESUPPORTED', 'ENLARGED'):
            b = w['branch']
            lastwork[b] = max(lastwork.get(b, ''), w['date'])
    airways = [b['branch'] for b in branches if b['kind'] == 'airway']
    need = []
    Rair = {}
    for a in airways:
        s = last.get(a)
        if s is None or (a in lastwork and lastwork[a] >= s['date']):
            need.append(a)
        if s is not None:
            q = float(s['q_m3_s'])
            Rair[a] = float(s['dp_Pa']) / (q * abs(q)) if q != 0 else 0.0
    if need:
        order = need[:allowance] if allowance > 0 else []
        if order:
            try:
                res = subprocess.run(['pqsurvey', pkg] + order, capture_output=True,
                                     text=True, timeout=25)
                for row in csv.DictReader(res.stdout.strip().splitlines()):
                    try:
                        q = float(row['q_m3_s'])
                        Rair[row['branch'].strip()] = float(row['dp_Pa']) / (q * abs(q))
                    except Exception:
                        pass
            except Exception as e:
                sys.stderr.write('pqsurvey failed: %s\n' % e)
        missing = [a for a in need if a not in Rair]
        if missing:
            sys.stderr.write('no resistance for %s\n' % missing)
            for a in missing:
                Rair[a] = 0.0

    # --- network ---
    nodes = {'ATM': -1}
    for b in branches:
        for n in (b['from_node'], b['to_node']):
            if n not in nodes:
                nodes[n] = len(nodes) - 1
    nN = len(nodes) - 1
    nB = len(branches)
    bidx = {b['branch']: i for i, b in enumerate(branches)}
    fr = np.array([nodes[b['from_node']] for b in branches])
    to = np.array([nodes[b['to_node']] for b in branches])
    rows, cols, vals = [], [], []
    for i in range(nB):
        if fr[i] >= 0:
            rows.append(fr[i]); cols.append(i); vals.append(-1.0)  # out of from node
        if to[i] >= 0:
            rows.append(to[i]); cols.append(i); vals.append(1.0)
    A = sp.csr_matrix((vals, (rows, cols)), shape=(nN, nB))  # A q = 0
    # p_from - p_to = D^T-like: dp = -A^T p
    AT = (-A.T).tocsr()

    fanb = []  # (branch idx, qs, ps)
    for i, b in enumerate(branches):
        if b['kind'] == 'fan':
            f = fans[b['item']]
            c = sorted(curves[(f['model'], f['blade_setting'].strip())])
            fanb.append((i, np.array([x[0] for x in c]), np.array([x[1] for x in c])))

    def fanP(qs, ps, q):
        k = np.clip(np.searchsorted(qs, q) - 1, 0, len(qs) - 2)
        sl = (ps[k + 1] - ps[k]) / (qs[k + 1] - qs[k])
        return ps[k] + sl * (q - qs[k]), sl

    def resist(state):
        R = np.zeros(nB)
        for i, b in enumerate(branches):
            k = b['kind']
            if k == 'airway':
                R[i] = Rair[b['branch']]
            elif k in ('stopping', 'fan'):
                R[i] = float(b['resistance_Ns2_m8'])
            elif k == 'regulator':
                R[i] = regs[b['item']][int(float(state[b['item']]))]
            elif k == 'door':
                c, o = doors[b['item']]
                R[i] = o if state[b['item']].strip().lower() == 'open' else c
        return R

    def residual(q, p, R):
        Pf = np.zeros(nB); dPf = np.zeros(nB)
        for i, qs, ps in fanb:
            Pf[i], dPf[i] = fanP(qs, ps, q[i])
        fb = AT @ p - R * q * np.abs(q) + Pf
        fn = A @ q
        return np.concatenate([fb, fn]), dPf

    def solve(R, q0, p0):
        q, p = q0.copy(), p0.copy()
        F, dPf = residual(q, p, R)
        nrm = np.linalg.norm(F)
        for it in range(200):
            d = -2 * R * np.maximum(np.abs(q), 1e-3) + dPf
            J = sp.bmat([[sp.diags(d), AT], [A, None]], format='csc')
            try:
                dx = spl.spsolve(J, -F)
            except Exception:
                dx = np.linalg.lstsq(J.toarray(), -F, rcond=None)[0]
            dq, dp = dx[:nB], dx[nB:]
            t = 1.0
            while True:
                qn, pn = q + t * dq, p + t * dp
                Fn, dPfn = residual(qn, pn, R)
                nn = np.linalg.norm(Fn)
                if nn < nrm or t < 1e-4:
                    break
                t *= 0.5
            q, p, F, dPf, nrm = qn, pn, Fn, dPfn, nn
            if np.max(np.abs(dq) * t) < 1e-9 * max(1.0, np.max(np.abs(q))) and nrm < 1e-6:
                break
        return q, p

    # --- states from the log ---
    log.sort(key=lambda r: r['time'])
    times = sorted(set(r['time'] for r in log))
    state = {}
    states = []
    j = 0
    for t in times:
        while j < len(log) and log[j]['time'] == t:
            state[log[j]['item']] = log[j]['setting']
            j += 1
        states.append((t, dict(state)))
    tlist = [t for t, _ in states]

    import bisect
    need_states = {}
    for pt in points:
        k = bisect.bisect_right(tlist, pt['time']) - 1
        need_states.setdefault(max(k, 0), []).append(pt)

    def newton(R, q0, p0, maxit=8, tol=1e-7):
        q, p = q0.copy(), p0.copy()
        for it in range(maxit):
            F, dPf = residual(q, p, R)
            if np.max(np.abs(F)) < tol:
                return q, p, True
            d = -2 * R * np.maximum(np.abs(q), 1e-4) + dPf
            J = sp.bmat([[sp.diags(d), AT], [A, None]], format='csc')
            dx = spl.spsolve(J, -F)
            if not np.all(np.isfinite(dx)):
                return q, p, False
            q = q + dx[:nB]; p = p + dx[nB:]
        F, _ = residual(q, p, R)
        return q, p, bool(np.max(np.abs(F)) < tol)

    fanidx = np.array([i for i, _, _ in fanb], dtype=int)
    Lin = np.ones(nB)

    def transient(R, q, p, tmax=400.0):
        # backward Euler of L dq/dt = dp - R q|q| + Pf(q), A q = 0
        dt = 0.02
        t = 0.0
        while t < tmax:
            qo = q.copy()
            qn, pn = q.copy(), p.copy()
            ok = False
            for it in range(20):
                F, dPf = residual(qn, pn, R)
                Fb = F[:nB] - Lin * (qn - qo) / dt
                G = np.concatenate([Fb, F[nB:]])
                if np.max(np.abs(G)) < 1e-8:
                    ok = True; break
                d = -2 * R * np.maximum(np.abs(qn), 1e-4) + dPf - Lin / dt
                J = sp.bmat([[sp.diags(d), AT], [A, None]], format='csc')
                dx = spl.spsolve(J, -G)
                qn = qn + dx[:nB]; pn = pn + dx[nB:]
            q, p = qn, pn
            t += dt
            F, _ = residual(q, p, R)
            if np.max(np.abs(F[:nB])) < 1e-3:
                break
            dt = min(dt * 1.05, 0.05)
        q, p, _ = newton(R, q, p, maxit=30)
        return q, p

    def Rpath(R0, R1, s):
        lo0 = np.log(np.maximum(R0, 1e-12)); lo1 = np.log(np.maximum(R1, 1e-12))
        Rs = np.exp(lo0 + s * (lo1 - lo0))
        return np.where(R0 == R1, R0, Rs)

    def track(R0, R1, q, p):
        s, h = 0.0, 1.0
        while s < 1.0:
            hh = min(h, 1.0 - s)
            Rs = Rpath(R0, R1, s + hh)
            qn, pn, ok = newton(Rpath(R0, R1, s + hh), q, p)
            if ok and (len(fanidx) == 0 or np.max(np.abs(qn[fanidx] - q[fanidx])) < 3.0):
                q, p, s = qn, pn, s + hh
                h = min(hh * 2, 1.0)
            elif hh > 2e-4:
                h = hh / 2
            else:
                q, p = transient(Rs, q, p)
                s = s + hh
                h = 0.01
        return q, p

    # initial state: fans started from rest
    R = resist(states[0][1])
    q, p = transient(R, np.zeros(nB), np.zeros(nN), tmax=2000.0)
    Rprev = R
    results = {}
    for k in range(len(states)):
        R = resist(states[k][1])
        if k > 0:
            q, p = track(Rprev, R, q, p)
        Rprev = R
        for pt in need_states.get(k, []):
            results[pt['point']] = q[bidx[pt['branch']]]

    with open(out, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['point', 'flow_m3_s'])
        for pt in points:
            w.writerow([pt['point'], '%.6f' % results[pt['point']]])


if __name__ == '__main__':
    main()
