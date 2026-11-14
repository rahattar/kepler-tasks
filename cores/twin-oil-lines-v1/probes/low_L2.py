#!/usr/bin/env python3
"""TS-2 heated oil line calculation for one site package.
Usage: python3 lines.py PACKAGE_DIR OUT_CSV"""
import sys, csv, json, re, subprocess
import numpy as np
np.seterr(all="ignore")

N_STEPS = 60


def d341(n50, n100):
    T1, T2 = 323.15, 373.15
    y1 = np.log10(np.log10(n50 + 0.7)); y2 = np.log10(np.log10(n100 + 0.7))
    B = (y1 - y2) / (np.log10(T2) - np.log10(T1))
    return y1 + B * np.log10(T1), B


def visc(A, B, TC):
    return (10 ** (10 ** (A - B * np.log10(TC + 273.15))) - 0.7) * 1e-6


def march(m, Tin, Ta, Uo, D, L, rho, cp, k, A, B, N=N_STEPS):
    """Vectorised integration of TS-2 section 3. m in kg/s. Returns dp [Pa], Tout [C].
    Heat balance written as dTb/dx = -beta (Tb - Ta) and stepped exponentially, so that
    nearly stagnant pipes stay stable; pressure gradient by Simpson's rule per step."""
    m, Tin, Ta, Uo, D, L, rho, cp, k, A, B = np.broadcast_arrays(
        *[np.asarray(v, float) for v in (m, Tin, Ta, Uo, D, L, rho, cp, k, A, B)])
    s = np.linspace(0, 1, N + 1) ** 3          # grid clustered at the inlet
    u = 4 * m / (np.pi * D ** 2 * rho)
    c0 = np.pi * D / (m * cp)
    Tb = Tin.copy(); dp = np.zeros_like(Tb)
    st = {'Tw': Tin.copy()}

    def rates(x, Tb):
        nb = visc(A, B, Tb)
        Re = u * D / nb; Pr = nb * rho * cp / k
        g = (1.077 * (Re * Pr * D / x) ** (1 / 3) - 0.7) ** 3
        Nu0 = (3.66 ** 3 + 0.7 ** 3 + g) ** (1 / 3)
        Tw = st['Tw']
        for _ in range(4):
            nw = visc(A, B, Tw)
            h = Nu0 * (nb / nw) ** 0.14 * k / D
            Tw = (h * Tb + Uo * Ta) / (h + Uo)
        st['Tw'] = Tw
        nw = visc(A, B, Tw)
        beta = c0 * h * Uo / (h + Uo)
        dP = 64 / Re * np.sqrt(nw / nb) * rho * u ** 2 / (2 * D)
        return beta, dP

    _, p0 = rates(s[1] * L * 1e-3, Tb)
    for i in range(N):
        x0 = s[i] * L; x1 = s[i + 1] * L; dx = x1 - x0; xm = 0.5 * (x0 + x1)
        b0, _ = rates(xm * 1e-2 if i == 0 else x0, Tb)
        Tm = Ta + (Tb - Ta) * np.exp(-0.5 * dx * b0)
        bm, pm = rates(xm, Tm)
        Tm = Ta + (Tb - Ta) * np.exp(-0.5 * dx * bm)
        Tb = Ta + (Tb - Ta) * np.exp(-dx * bm)
        _, p1 = rates(x1, Tb)
        dp = dp + dx * (p0 + 4 * pm + p1) / 6
        p0 = p1
    return dp, Tb


def read(path):
    with open(path, newline='') as f:
        return [{k.strip(): (v or '').strip() for k, v in r.items()} for r in csv.DictReader(f)]


COVER = re.compile(r'cover|lag|insulat|clad|jacket|wrap', re.I)


def main():
    P, out = sys.argv[1], sys.argv[2]
    site = json.load(open(f'{P}/site.json'))
    oils = {o['oil']: o for o in read(f'{P}/oils.csv')}
    lines = {l['line']: l for l in read(f'{P}/lines.csv')}
    surveys = read(f'{P}/surveys.csv')
    jobs = read(f'{P}/work_log.csv')
    recs = read(f'{P}/records.csv')

    def props(ln):
        l = lines[ln]; o = oils[l['oil']]
        A, B = d341(float(o['nu50_cSt']), float(o['nu100_cSt']))
        return (float(l['bore_mm']) / 1e3, float(l['length_m']), float(o['density_kg_m3']),
                float(o['cp_J_kgK']), float(o['k_W_mK']), A, B)

    pipes = []
    for ln, l in lines.items():
        pipes += [f'{ln}-A'] + ([f'{ln}-B'] if int(float(l['pipes'])) == 2 else [])

    # last covering work on each pipe
    lastwork = {}
    for j in jobs:
        p = j['pipe'].upper()
        if COVER.search(j['job']):
            lastwork[p] = max(lastwork.get(p, ''), j['date'])
    # valid surveys: those after the covering's last renewal/repair (TS-2 5.3)
    valid = {p: [] for p in pipes}
    for s in surveys:
        p = s['pipe'].upper()
        if p in valid and s['date'] > lastwork.get(p, ''):
            valid[p].append(s)
    need = [p for p in pipes if not valid[p]]
    if need:
        allow = int(site.get('survey_allowance', 0))
        order = need[:allow]
        try:
            r = subprocess.run(['heatsurvey', P] + order, capture_output=True, text=True, timeout=40)
            for row in csv.DictReader(r.stdout.strip().splitlines()):
                row = {k.strip(): v.strip() for k, v in row.items()}
                p = row['pipe'].upper()
                if p in valid:
                    row['date'] = '9999'
                    valid[p].append(row)
        except Exception as e:
            print('survey failed:', e, file=sys.stderr)
        for p in pipes:
            if not valid[p]:   # fall back to the latest survey of any kind
                old = [s for s in surveys if s['pipe'].upper() == p]
                print(f'warning: no valid survey for {p}', file=sys.stderr)
                valid[p] = old[-1:] if old else []

    # fit Uo for every valid survey (TS-2 5.2), average per pipe
    rows = [(p, s) for p in pipes for s in valid[p]]
    pr = np.array([props(p[:-2]) for p, _ in rows]).T
    f = lambda key: np.array([float(s[key]) for _, s in rows])
    m, ti, to, ta = f('flow_t_h') / 3.6, f('t_in_C'), f('t_out_C'), f('t_amb_C')
    lo = np.full(len(rows), 1e-3); hi = np.full(len(rows), 500.)
    for _ in range(45):
        mid = np.sqrt(lo * hi)
        _, T = march(m, ti, ta, mid, *pr)
        cold = T < to
        hi = np.where(cold, mid, hi); lo = np.where(cold, lo, mid)
    Ufit = np.sqrt(lo * hi)
    U = {}
    for (p, _), u in zip(rows, Ufit):
        U.setdefault(p, []).append(u)
    U = {p: float(np.mean(v)) for p, v in U.items()}

    # records
    R = len(recs)
    ln = [r['line'] for r in recs]
    pr = np.array([props(l) for l in ln]).T
    M = np.array([float(r['flow_t_h']) for r in recs]) / 3.6
    Ti = np.array([float(r['t_in_C']) for r in recs])
    Ta = np.array([float(r['t_amb_C']) for r in recs])
    UA = np.array([U[f'{l}-A'] for l in ln])
    pair = np.array([int(float(lines[l]['pipes'])) == 2 for l in ln])
    UB = np.array([U.get(f'{l}-B', U[f'{l}-A']) for l in ln])

    dp = np.zeros(R); To = np.zeros(R)
    s = ~pair
    if s.any():
        dp[s], To[s] = march(M[s], Ti[s], Ta[s], UA[s], *pr[:, s])
    if pair.any():
        # The split of a pair can have several steady states (TS-2 4): find every
        # stable one on a grid of splits and follow the line's run of records,
        # keeping to the branch the line was on at the previous reading.
        idx = np.nonzero(pair)[0]; n = len(idx)
        G = 81
        t = np.linspace(0, 1, G)
        ag = 0.0005 + 0.999 * (0.5 - 0.5 * np.cos(np.pi * t))   # dense near the ends
        Ar = np.repeat(ag[None, :], n, 0).ravel()
        rep = lambda v: np.repeat(v[idx], G)
        prr = np.repeat(pr[:, idx], G, axis=1)
        Mr, Tir, Tar = rep(M), rep(Ti), rep(Ta)
        dA, _ = march(Ar * Mr, Tir, Tar, rep(UA), *prr)
        dB, _ = march((1 - Ar) * Mr, Tir, Tar, rep(UB), *prr)
        g = (dA - dB).reshape(n, G)
        # stable roots: g (dp of A less dp of B) rises through zero with the share of A
        roots = [np.nonzero((g[i, :-1] < 0) & (g[i, 1:] >= 0))[0] for i in range(n)]
        choice = np.zeros(n, int); prev = {}
        order = sorted(range(n), key=lambda i: (ln[idx[i]], float(recs[idx[i]]['hour'])))
        for i in order:
            c = roots[i]; l = ln[idx[i]]
            if len(c) == 0:          # no interior steady state on the grid
                choice[i] = int(np.argmin(np.abs(g[i])))
                choice[i] = min(choice[i], G - 2)
                prev[l] = ag[choice[i]]
                print(f'warning: no steady split found for {recs[idx[i]]["record"]}', file=sys.stderr)
                continue
            a0 = prev.get(l, 0.5)
            if l not in prev and len(c) > 1:
                print(f'warning: {len(c)} steady states at first record of {l}', file=sys.stderr)
            # the split moves from where it stood towards equal pressure drops:
            # it settles in the steady state whose basin holds the previous split
            gi = np.interp(a0, ag, g[i])
            mids = 0.5 * (ag[c] + ag[c + 1])
            if gi > 0:
                cand = c[mids <= a0]
                j = cand[-1] if len(cand) else c[0]
            else:
                cand = c[mids >= a0]
                j = cand[0] if len(cand) else c[-1]
            choice[i] = j
            prev[l] = 0.5 * (ag[j] + ag[j + 1])
        # refine, then record the split for the next reading
        lo = ag[choice]; hi = ag[choice + 1]
        q = idx; prq = pr[:, q]; Mq = M[q]
        for _ in range(22):
            a = 0.5 * (lo + hi)
            dA, _ = march(a * Mq, Ti[q], Ta[q], UA[q], *prq)
            dB, _ = march((1 - a) * Mq, Ti[q], Ta[q], UB[q], *prq)
            big = dA > dB
            hi = np.where(big, a, hi); lo = np.where(big, lo, a)
        a = 0.5 * (lo + hi)
        dA, TA = march(a * Mq, Ti[q], Ta[q], UA[q], *prq)
        dB, TB = march((1 - a) * Mq, Ti[q], Ta[q], UB[q], *prq)
        dp[q] = 0.5 * (dA + dB)
        To[q] = a * TA + (1 - a) * TB   # constant cp: mixed-stream temperature
    with open(out, 'w', newline='') as fo:
        w = csv.writer(fo)
        w.writerow(['record', 'dp_kPa', 't_out_C'])
        for r, d, t in zip(recs, dp, To):
            w.writerow([r['record'], f'{d / 1e3:.4f}', f'{t:.3f}'])


if __name__ == '__main__':
    main()
