#!/usr/bin/env python3
"""Airflow at every survey point of a district package, to VS-4."""
import sys, os, json, subprocess, io
import numpy as np
import pandas as pd
import scipy.sparse as sp
from scipy.sparse.linalg import splu


def main():
    pkg, out = sys.argv[1], sys.argv[2]
    rd = lambda f: pd.read_csv(os.path.join(pkg, f), dtype={'setting': str})
    br = rd('branches.csv')
    surveys = rd('surveys.csv')
    work = rd('work_log.csv')
    regs = rd('regulators.csv')
    doors = rd('doors.csv')
    fans = rd('fans.csv')
    curves = rd('fan_curves.csv')
    log = rd('log.csv')
    pts = rd('points.csv')
    try:
        allowance = int(json.load(open(os.path.join(pkg, 'district.json'))).get('survey_allowance', 0))
    except Exception:
        allowance = 0

    nb = len(br)
    bidx = {b: i for i, b in enumerate(br.branch)}
    kind = br.kind.values
    item = br['item'].fillna('').astype(str).values

    # ---- airway resistances (VS-4 s.3)
    surveys = surveys.sort_values('date', kind='stable')
    last = {}
    for r in surveys.itertuples(index=False):
        last[r.branch] = (r.date, float(r.dp_Pa), float(r.q_m3_s))
    changed = {}
    for r in work.itertuples(index=False):
        if str(r.work).strip().upper() in ('RESUPPORTED', 'ENLARGED'):
            changed[r.branch] = max(changed.get(r.branch, ''), str(r.date))
    R = np.zeros(nb)
    need = []
    for i in range(nb):
        b = br.branch[i]
        if kind[i] == 'airway':
            s = last.get(b)
            if s is None or (b in changed and s[0] <= changed[b]):
                need.append(b)
            if s is not None and s[2] != 0:
                R[i] = s[1] / (s[2] * abs(s[2]))
        elif kind[i] in ('stopping', 'fan'):
            v = br.resistance_Ns2_m8[i]
            R[i] = 0.0 if pd.isna(v) else float(v)
    if need and allowance > 0:
        order = need[:allowance]
        try:
            res = subprocess.run(['pqsurvey', pkg] + order, capture_output=True, text=True, timeout=20)
            if res.returncode == 0:
                df = pd.read_csv(io.StringIO(res.stdout))
                for r in df.itertuples(index=False):
                    q = float(r.q_m3_s)
                    if r.branch in bidx and q != 0:
                        R[bidx[r.branch]] = float(r.dp_Pa) / (q * abs(q))
            else:
                sys.stderr.write(res.stdout + res.stderr)
        except Exception as e:
            sys.stderr.write('pqsurvey failed: %s\n' % e)

    # ---- regulators / doors
    regR = {(r.regulator, str(r.setting).strip()): float(r.resistance_Ns2_m8) for r in regs.itertuples(index=False)}
    regR.update({(k[0], str(int(float(k[1])))): v for k, v in list(regR.items())})
    doorR = {r.door: (float(r.resistance_closed_Ns2_m8), float(r.resistance_open_Ns2_m8)) for r in doors.itertuples(index=False)}
    item_branches = {}
    for i in range(nb):
        if kind[i] in ('regulator', 'door') and item[i]:
            item_branches.setdefault(item[i], []).append(i)

    def setting_R(it, st):
        st = str(st).strip()
        if it in doorR:
            return doorR[it][0] if st.lower() == 'closed' else doorR[it][1]
        key = (it, st)
        if key not in regR:
            key = (it, str(int(float(st))))
        return regR[key]

    # ---- fans (VS-4 s.4): full catalogue characteristic and its descending segments
    fan_br = {}
    for r in fans.itertuples(index=False):
        c = curves[(curves.model == r.model) & (curves.blade_setting.astype(str) == str(r.blade_setting))]
        x = c.flow_m3_s.values.astype(float); y = c.pressure_Pa.values.astype(float)
        segs = []  # (ka, kb): table points ka..kb with pressure falling
        k = 0
        n = len(x)
        while k < n - 1:
            if y[k + 1] < y[k]:
                j = k
                while j < n - 1 and y[j + 1] < y[j]:
                    j += 1
                segs.append((k, j)); k = j
            else:
                k += 1
        fan_br[bidx[r.branch]] = (x, y, segs)
    fan_idx = np.array(sorted(fan_br), dtype=int)
    nf = len(fan_idx)

    def curve(x, y, q, ka, kb):
        j = int(np.clip(np.searchsorted(x[ka:kb + 1], q) - 1, 0, kb - ka - 1)) + ka
        s_ = (y[j + 1] - y[j]) / (x[j + 1] - x[j])
        return y[j] + s_ * (q - x[j]), s_

    def fanP(qf, seg):
        P = np.zeros(nf); dP = np.zeros(nf)
        for k, i in enumerate(fan_idx):
            x, y, segs = fan_br[i]
            if seg is None:
                P[k], dP[k] = curve(x, y, qf[k], 0, len(x) - 1)
            else:
                ka, kb = segs[seg[k]]
                P[k], dP[k] = curve(x, y, qf[k], ka, kb)
        return P, dP

    def classify(qf):
        """Index of the descending segment each fan stands on, or None if on a rising part."""
        out = []
        for k, i in enumerate(fan_idx):
            x, y, segs = fan_br[i]
            hit = None
            for m, (ka, kb) in enumerate(segs):
                lo = x[ka] if m > 0 else -np.inf
                hi = x[kb] if m < len(segs) - 1 else np.inf
                if lo - 1e-9 <= qf[k] <= hi + 1e-9:
                    hit = m; break
            if hit is None:
                return None
            out.append(hit)
        return out

    # ---- network
    nodes = sorted(set(br.from_node) | set(br.to_node))
    nodes.remove('ATM')
    nid = {n: k for k, n in enumerate(nodes)}
    nn = len(nodes)
    rows, cols, vals = [], [], []
    for i in range(nb):
        f, t = br.from_node[i], br.to_node[i]
        if f != 'ATM':
            rows.append(i); cols.append(nid[f]); vals.append(1.0)
        if t != 'ATM':
            rows.append(i); cols.append(nid[t]); vals.append(-1.0)
    A = sp.csr_matrix((vals, (rows, cols)), shape=(nb, nn))
    AT = A.T.tocsr()

    def step(R, q, seg, inert):
        f = R * q * np.abs(q)
        D = 2 * R * np.abs(q)
        if nf:
            P, dP = fanP(q[fan_idx], seg)
            f[fan_idx] -= P
            D[fan_idx] -= dP
        if inert:
            D = D + inert
            D = np.maximum(D, 0.05 * inert)
        else:
            D = np.maximum(D, 1e-6)
        Di = 1.0 / D
        L = (AT @ sp.diags(Di) @ A).tocsc()
        rhs = AT @ (Di * f - q)
        p = splu(L).solve(rhs)
        return (A @ p - f) * Di, p, f

    def newton(R, q, seg):
        """Newton on the network with each fan held to one descending segment (unique solution)."""
        q = q.copy()
        for it in range(100):
            dq, _, _ = step(R, q, seg, 0.0)
            lim = 0.5 * np.maximum(np.abs(q), 1.0)
            a = min(1.0, float(np.min(lim / np.maximum(np.abs(dq), 1e-300))))
            q = q + (dq if a >= 1 or it > 40 else max(a, 0.25) * dq)
            if np.max(np.abs(dq) / np.maximum(np.abs(q), 1e-2)) < 1e-9:
                return q, True
        return q, False

    def residual(R, q):
        _, p, f = step(R, q, None, 0.0)
        return np.max(np.abs(A @ p - f))

    def transient(R, q):
        """Pseudo-transient relaxation (air inertia) with the full fan characteristic."""
        q = q.copy()
        h_inv = 50.0
        for it in range(3000):
            dq, _, _ = step(R, q, None, h_inv)
            q = q + dq
            rel = np.max(np.abs(dq) / np.maximum(np.abs(q), 1e-2))
            if rel < 1e-3:
                h_inv *= 0.7
            if rel < 1e-10 and h_inv < 1e-6:
                break
            if h_inv < 1e-8:
                seg = classify(q[fan_idx])
                if seg is not None:
                    q2, ok = newton(R, q, seg)
                    if ok and classify(q2[fan_idx]) == seg:
                        return q2
        return q

    def advance(Rold, Rnew, q, seg):
        """Follow the steady state while the settings move from Rold to Rnew."""
        q2, ok = newton(Rnew, q, seg)
        if ok and classify(q2[fan_idx]) == seg:
            return q2, seg
        # the operating point leaves its branch: ramp the change and follow it
        lo = np.log(np.maximum(Rold, 1e-12)); hi = np.log(np.maximum(Rnew, 1e-12))
        N = 40
        for k in range(1, N + 1):
            Rk = np.where(Rold == Rnew, Rnew, np.exp(lo + (hi - lo) * k / N))
            if k == N:
                Rk = Rnew
            q2, ok = newton(Rk, q, seg)
            if ok and classify(q2[fan_idx]) == seg:
                q = q2
                continue
            q = transient(Rk, q)
            seg = classify(q[fan_idx])
            if seg is None:
                seg = [len(fan_br[i][2]) - 1 for i in fan_idx]
            q, _ = newton(Rk, q, seg)
        return q, seg

    # ---- timeline (VS-4 s.5)
    log = log.copy()
    log['time'] = log['time'].astype(str).str.strip()
    times = sorted(log.time.unique())
    pts = pts.copy()
    pts['time'] = pts['time'].astype(str).str.strip()
    groups = {t: g for t, g in log.groupby('time')}
    pend = list(pts.sort_values('time', kind='stable').itertuples(index=False))

    def apply(Rv, t):
        Rv = Rv.copy()
        for r in groups[t].itertuples(index=False):
            for i in item_branches.get(r.item, []):
                Rv[i] = setting_R(r.item, r.setting)
        return Rv

    cur = apply(R, times[0])
    q = np.full(nb, 1.0)
    seg = [len(fan_br[i][2]) - 1 for i in fan_idx]  # fans start on their normal (right-hand) branch
    for k, i in enumerate(fan_idx):
        x, y, segs = fan_br[i]
        q[i] = 0.5 * (x[segs[-1][0]] + x[segs[-1][1]])
    q, _ = newton(cur, q, seg)
    applied = 0
    result = {}
    pi = 0
    while pi < len(pend):
        tp = pend[pi].time
        while applied + 1 < len(times) and times[applied + 1] < tp:
            applied += 1
            new = apply(cur, times[applied])
            q, seg = advance(cur, new, q, seg)
            cur = new
        while pi < len(pend) and pend[pi].time == tp:
            r = pend[pi]
            result[r.point] = q[bidx[r.branch]] if r.branch in bidx else 0.0
            pi += 1
    with open(out, 'w') as fh:
        fh.write('point,flow_m3_s\n')
        for p in pts.point:
            fh.write('%s,%.5f\n' % (p, result[p]))


if __name__ == '__main__':
    main()
