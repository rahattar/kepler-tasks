#!/usr/bin/env python3
"""District airflow to VS-4."""
import sys, os, json, subprocess
import numpy as np, pandas as pd
import scipy.sparse as sp
from scipy.sparse.linalg import splu

STEEP = 2000.0  # Pa per m3/s for monotone extension outside a fan part


def main():
    pkg, out = sys.argv[1], sys.argv[2]
    rd = lambda f: pd.read_csv(os.path.join(pkg, f), dtype=str, keep_default_na=False)
    dist = json.load(open(os.path.join(pkg, 'district.json')))
    br = rd('branches.csv'); sv = rd('surveys.csv'); wl = rd('work_log.csv')
    regs = rd('regulators.csv'); doors = rd('doors.csv'); fans = rd('fans.csv')
    curves = rd('fan_curves.csv'); log = rd('log.csv'); pts = rd('points.csv')

    names = list(br.branch); bidx = {n: i for i, n in enumerate(names)}
    nb = len(names); kind = list(br.kind); item = list(br.item)
    R = np.zeros(nb)

    # --- airway resistances from surveys
    sv['dp'] = sv.dp_Pa.astype(float); sv['q'] = sv.q_m3_s.astype(float)
    sv = sv.sort_values('date', kind='stable')
    last = sv.groupby('branch').tail(1).set_index('branch')
    work = wl[wl.work.isin(['RESUPPORTED', 'ENLARGED'])].groupby('branch').date.max()
    need = []
    for i, n in enumerate(names):
        if kind[i] == 'airway':
            if n not in last.index or (n in work.index and work[n] >= last.loc[n, 'date']):
                need.append(n)
            else:
                r = last.loc[n]; R[i] = r.dp / (r.q * abs(r.q))
        elif kind[i] in ('stopping', 'fan'):
            R[i] = float(br.resistance_Ns2_m8[i])
    if need:
        allow = int(dist.get('survey_allowance', len(need)))
        res = subprocess.run(['pqsurvey', pkg] + need[:allow], capture_output=True, text=True)
        for line in res.stdout.strip().splitlines():
            p = line.strip().split(',')
            if len(p) < 3 or p[0] == 'branch' or p[0] not in bidx:
                continue
            try:
                dp, q = float(p[1]), float(p[2])
            except ValueError:
                continue
            R[bidx[p[0]]] = dp / (q * abs(q))
        for n in need:  # fallback: old survey if crew did not answer
            i = bidx[n]
            if R[i] == 0 and n in last.index:
                r = last.loc[n]; R[i] = r.dp / (r.q * abs(r.q))

    regtab = {(r.regulator, int(r.setting)): float(r.resistance_Ns2_m8) for r in regs.itertuples()}
    doortab = {d.door: (float(d.resistance_closed_Ns2_m8), float(d.resistance_open_Ns2_m8)) for d in doors.itertuples()}
    itm_br = {}
    for i in range(nb):
        if kind[i] in ('regulator', 'door'):
            itm_br.setdefault(item[i], []).append(i)

    def item_R(it, s):
        if it in doortab:
            return doortab[it][0] if s.strip().lower() == 'closed' else doortab[it][1]
        return regtab[(it, int(float(s)))]

    # --- fans
    fan_list = []  # (branch idx, qarr, parr, parts)
    for f in fans.itertuples():
        c = curves[(curves.model == f.model) & (curves.blade_setting.astype(float) == float(f.blade_setting))]
        qa = c.flow_m3_s.astype(float).values; pa = c.pressure_Pa.astype(float).values
        o = np.argsort(qa, kind='stable'); qa, pa = qa[o], pa[o]
        d = np.diff(pa)
        # dip: first local min; peak: following local max
        k = 0
        while k < len(d) and d[k] < 0: k += 1
        idip = k
        while k < len(d) and d[k] >= 0: k += 1
        ipk = k
        fan_list.append((bidx[f.branch], qa, pa, idip, ipk))
    nf = len(fan_list)

    def fan_eval(fi, part, q):
        """part 1 = beyond peak, 0 = short of dip. Returns P, dP/dq on monotone extension."""
        _, qa, pa, idip, ipk = fan_list[fi]
        lo, hi = (ipk, len(qa) - 1) if part == 1 else (0, idip)
        if q <= qa[lo]:
            if part == 1:
                return pa[lo] + STEEP * (qa[lo] - q), -STEEP
            s = (pa[lo + 1] - pa[lo]) / (qa[lo + 1] - qa[lo]); return pa[lo] + s * (q - qa[lo]), s
        if q >= qa[hi]:
            if part == 0:
                return pa[hi] - STEEP * (q - qa[hi]), -STEEP
            s = (pa[hi] - pa[hi - 1]) / (qa[hi] - qa[hi - 1]); return pa[hi] + s * (q - qa[hi]), s
        j = np.searchsorted(qa, q, side='right') - 1
        j = min(max(j, lo), hi - 1)
        s = (pa[j + 1] - pa[j]) / (qa[j + 1] - qa[j]); return pa[j] + s * (q - qa[j]), s

    def fan_ok(fi, part, q):
        _, qa, pa, idip, ipk = fan_list[fi]
        return (q >= qa[ipk]) if part == 1 else (q <= qa[idip])

    def fan_content(fi, part, q):  # integral of P from 0 to q (piecewise numeric)
        _, qa, pa, idip, ipk = fan_list[fi]
        xs = np.linspace(0, q, 401); ps = np.array([fan_eval(fi, part, x)[0] for x in xs])
        return np.trapezoid(ps, xs)

    # --- network incidence
    nodes = sorted(set(br.from_node) | set(br.to_node) - {'ATM'})
    nodes = [n for n in nodes if n != 'ATM']
    nid = {n: i for i, n in enumerate(nodes)}; nn = len(nodes)
    rows, cols, vals = [], [], []
    for i in range(nb):
        a, b = br.from_node[i], br.to_node[i]
        if a != 'ATM': rows.append(nid[a]); cols.append(i); vals.append(-1.0)  # leaves a
        if b != 'ATM': rows.append(nid[b]); cols.append(i); vals.append(1.0)
    A = sp.csr_matrix((vals, (rows, cols)), shape=(nn, nb))  # A q = net inflow
    # branch eq: p_from - p_to = h(q);  p_from - p_to = -(A^T p)
    AT = A.T.tocsr()
    fidx = np.array([f[0] for f in fan_list], dtype=int)

    def h_and_d(q, Rv, parts):
        h = Rv * q * np.abs(q); d = 2 * Rv * np.abs(q)
        for fi in range(nf):
            P, s = fan_eval(fi, parts[fi], q[fidx[fi]]); h[fidx[fi]] -= P; d[fidx[fi]] -= s
        return h, np.maximum(d, 1e-9 + 1e-6 * Rv)

    def solve(Rv, parts, q0):
        q = q0.copy()
        # initial: project onto conservation is done by Newton itself (exact for linear constraint)
        for it in range(200):
            h, d = h_and_d(q, Rv, parts)
            Di = 1.0 / d
            L = (A @ sp.diags(Di) @ AT).tocsc()
            rhs = A @ (q - Di * h)
            p = splu(L).solve(-rhs) if False else None
            # dq = (-(A^T p) - h)/d ; A(q+dq)=0 -> -A Di A^T p = A(Di h - q)
            p = splu(L).solve(A @ (q - Di * h))
            dq = (-(AT @ p) - h) * Di
            # damping
            step = 1.0
            mx = np.max(np.abs(dq) / (np.abs(q) + 1.0))
            if mx > 0.5: step = 0.5 / mx
            q = q + step * dq
            if step == 1.0 and np.max(np.abs(dq) / (np.abs(q) + 1e-3)) < 1e-7:
                break
        return q

    # settings
    log['t'] = log.time
    times = sorted(log.t.unique())
    cur = {}
    first = log[log.t == times[0]]
    for r in first.itertuples(): cur[r.item] = r.setting

    def Rvec(settings):
        Rv = R.copy()
        for it, ii in itm_br.items():
            if it in settings:
                for i in ii: Rv[i] = item_R(it, settings[it])
        return Rv

    parts = [1] * nf
    Rv = Rvec(cur)
    q = np.zeros(nb)
    # initial guess: some flow through fans
    q = solve(Rv, parts, np.full(nb, 1.0))
    states = [(times[0], q.copy())]
    grouped = {t: g for t, g in log.groupby('t')}

    def valid(qv, prt):
        return [fi for fi in range(nf) if not fan_ok(fi, prt[fi], qv[fidx[fi]])]

    for t in times[1:]:
        new = dict(cur)
        for r in grouped[t].itertuples(): new[r.item] = r.setting
        R0, R1 = Rv, Rvec(new)
        qn = solve(R1, parts, q)
        bad = valid(qn, parts)
        if bad:
            # homotopy in log-resistance from old to new settings
            l0, l1 = np.log(R0), np.log(R1)
            Rt = lambda s: np.exp(l0 + s * (l1 - l0))
            t0, qa_ = 0.0, q
            guard = 0
            while bad and guard < 20:
                guard += 1
                lo, hi, qlo = t0, 1.0, qa_
                for _ in range(30):
                    mid = 0.5 * (lo + hi)
                    qm = solve(Rt(mid), parts, qlo)
                    if valid(qm, parts): hi = mid
                    else: lo, qlo = mid, qm
                qh = solve(Rt(hi), parts, qlo)
                bh = valid(qh, parts)
                # choose fan furthest out at hi
                def excess(fi):
                    _, qa, pa, idip, ipk = fan_list[fi]; x = qh[fidx[fi]]
                    return (qa[ipk] - x) if parts[fi] == 1 else (x - qa[idip])
                fi = max(bh, key=excess) if bh else bad[0]
                parts[fi] = 1 - parts[fi]
                if os.environ.get('AF_DEBUG'): print('flip', t, fi, parts, file=sys.stderr)
                t0 = hi
                qs = solve(Rt(t0), parts, qh)
                while True:  # cascade at the switch point
                    bb = valid(qs, parts)
                    if not bb: break
                    parts[bb[0]] = 1 - parts[bb[0]]
                    qs = solve(Rt(t0), parts, qs)
                    guard += 1
                    if guard > 40: break
                qa_ = qs
                qn = solve(R1, parts, qs)
                bad = valid(qn, parts)
        q, Rv, cur = qn, R1, new
        states.append((t, q.copy()))

    st_t = [s[0] for s in states]
    with open(out, 'w') as fo:
        fo.write('point,flow_m3_s\n')
        for r in pts.itertuples():
            k = np.searchsorted(st_t, r.time, side='right') - 1
            k = max(k, 0)
            fo.write('%s,%.4f\n' % (r.point, states[k][1][bidx[r.branch]]))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        import traceback; traceback.print_exc()
        try:
            if not os.path.exists(sys.argv[2]):
                p = pd.read_csv(os.path.join(sys.argv[1], 'points.csv'), dtype=str)
                with open(sys.argv[2], 'w') as fo:
                    fo.write('point,flow_m3_s\n')
                    for x in p.point: fo.write('%s,0.0\n' % x)
        except Exception:
            pass
    sys.exit(0)
