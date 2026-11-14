#!/usr/bin/env python3
"""TS-2 heated oil line calculation for one site package."""
import sys, os, csv, json, math, subprocess
import numpy as np

LN10 = math.log(10)
N = int(os.environ.get("TS2_N", 40))  # march steps


def read(path):
    with open(path, newline='') as f:
        return list(csv.DictReader(f))


class Oil:
    def __init__(s, r):
        s.rho = float(r['density_kg_m3']); s.cp = float(r['cp_J_kgK']); s.k = float(r['k_W_mK'])
        v1, v2 = float(r['nu50_cSt']), float(r['nu100_cSt'])
        T1, T2 = math.log10(323.15), math.log10(373.15)
        y1, y2 = math.log10(math.log10(v1 + 0.7)), math.log10(math.log10(v2 + 0.7))
        s.B = (y1 - y2) / (T2 - T1); s.A = y1 + s.B * T1


class P:
    """Vectorised set of pipe cases (all arrays of equal length)."""
    def __init__(s, oils, D, L):
        s.A = np.array([o.A for o in oils]); s.B = np.array([o.B for o in oils])
        s.rho = np.array([o.rho for o in oils]); s.cp = np.array([o.cp for o in oils])
        s.k = np.array([o.k for o in oils]); s.D = np.asarray(D, float); s.L = np.asarray(L, float)

    def nu(s, T):
        return (np.exp(LN10 * np.exp(LN10 * (s.A - s.B * np.log10(T + 273.15)))) - 0.7) * 1e-6


def pipe(c, m, Tin, Ta, Uo):
    """Returns (Tout C, dp Pa) for mass flow m kg/s.  Marches th = ln(Tb - Ta)."""
    D, rho, cp, k = c.D, c.rho, c.cp, c.k
    Ar = math.pi * D * D / 4
    u = m / (rho * Ar)
    piDU = math.pi * D * Uo
    th = np.log(np.asarray(Tin, float) - Ta)
    GzK = u * D * D * rho * cp / k   # Re*Pr*D = u D^2 rho cp / k (independent of nu)
    fK = 64 * rho * u / (2 * D * D)  # f rho u^2/(2D) = 64 nu/(uD) * rho u^2 /(2D) * sqrt(r)

    def rates(x, th):
        dT = np.exp(th); Tb = Ta + dT
        nub = c.nu(Tb)
        if x is not None:
            nu0 = (3.66 ** 3 + 0.7 ** 3 + (1.077 * np.cbrt(GzK / x) - 0.7) ** 3) ** (1 / 3) * k / D
            r = 1.0
            for _ in range(4):
                h = nu0 * r ** -0.14
                w = h / (h + Uo)          # (Tw-Ta)/(Tb-Ta)
                r = c.nu(Ta + w * dT) / nub
        else:
            w = 1.0; r = 1.0
        return -piDU * w / (m * cp), fK * nub * np.sqrt(r)

    dp = np.zeros_like(th)
    for i in range(N):
        x0 = c.L * (i / N) ** 2; x1 = c.L * ((i + 1) / N) ** 2; hx = x1 - x0; xm = x0 + hx / 2
        a1, g1 = rates(x0 if i else None, th)
        a2, g2 = rates(xm, th + hx / 2 * a1)
        a3, g3 = rates(xm, th + hx / 2 * a2)
        a4, g4 = rates(x1, th + hx * a3)
        th = th + hx / 6 * (a1 + 2 * a2 + 2 * a3 + a4)
        dp = dp + hx / 6 * (g1 + 2 * g2 + 2 * g3 + g4)
    return Ta + np.exp(th), dp


def fit_uo(c, m, Tin, Ta, Tout):
    lo = np.full(m.shape, -1.0); hi = np.full(m.shape, 2.5)  # log10 Uo
    for _ in range(26):
        mid = (lo + hi) / 2
        T, _ = pipe(c, m, Tin, Ta, 10 ** mid)
        big = T < Tout
        hi = np.where(big, mid, hi); lo = np.where(big, lo, mid)
    return 10 ** ((lo + hi) / 2)


S_GRID = np.linspace(-9.5, 9.5, int(os.environ.get("TS2_G", 77)))   # logit of the split to pipe A


def pairs(oils, lines, recs, pair, m, Tin, Ta, uA, uB, T, dp):
    """Pairs: the split follows the line's history.  From the split of the
    previous hour, the flow shifts away from the pipe with the higher pressure
    drop until the two drops are equal (a stable split)."""
    seq = {}
    for i in np.where(pair)[0]:
        seq.setdefault(recs[i]['line'], []).append(i)
    for ln in seq:
        seq[ln].sort(key=lambda i: float(recs[i]['hour']))
    names = list(seq)
    nl = len(names)
    oil = [oils[lines[n]['oil']] for n in names]
    D = np.array([float(lines[n]['bore_mm']) / 1000 for n in names])
    L = np.array([float(lines[n]['length_m']) for n in names])
    prev = np.zeros(nl)          # logit of split, start even
    G = len(S_GRID)
    cg = P(oil * G * 2, np.tile(D, 2 * G), np.tile(L, 2 * G))
    nmax = max(len(v) for v in seq.values())

    def g_of(cc, idx, s):
        fr = 1 / (1 + np.exp(-s))
        k = len(s)
        TT, DD = pipe(cc, np.concatenate([m[idx] * fr, m[idx] * (1 - fr)]), np.tile(Tin[idx], 2),
                      np.tile(Ta[idx], 2), np.concatenate([uA[idx], uB[idx]]))
        return np.log(DD[:k] / DD[k:]), fr, TT[:k], TT[k:], DD[:k], DD[k:]

    for step in range(nmax):
        act = [j for j in range(nl) if step < len(seq[names[j]])]
        idx = np.array([seq[names[j]][step] for j in act])
        na = len(act)
        aj = np.array(act)
        # grid evaluation (last block: the previous split); layout [grid point][line]
        p = prev[aj]
        ii = np.tile(idx, G + 1); ss = np.concatenate([np.repeat(S_GRID, na), p])
        cc = P([oil[j] for j in aj] * (G + 1) * 2, np.tile(D[aj], 2 * G + 2), np.tile(L[aj], 2 * G + 2))
        gall = g_of(cc, ii, ss)[0]
        gg = gall[:G * na].reshape(G, na); g0 = gall[G * na:]
        c1 = P([oil[j] for j in aj] * 2, np.tile(D[aj], 2), np.tile(L[aj], 2))
        lo = np.empty(na); hi = np.empty(na); glo = np.empty(na); ghi = np.empty(na)
        for q in range(na):
            col = gg[:, q]
            if g0[q] > 0:   # too much in A: the split moves down to the first g <= 0
                below = np.where((S_GRID < p[q]) & ~(col > 0))[0]
                if len(below):
                    j = below[-1]; lo[q] = S_GRID[j]; glo[q] = col[j]
                    if S_GRID[j + 1] < p[q]: hi[q] = S_GRID[j + 1]; ghi[q] = col[j + 1]
                    else: hi[q] = p[q]; ghi[q] = g0[q]
                else:
                    lo[q] = hi[q] = S_GRID[0]; glo[q] = ghi[q] = 0.0
            else:
                above = np.where((S_GRID > p[q]) & (col > 0))[0]
                if len(above):
                    j = above[0]; hi[q] = S_GRID[j]; ghi[q] = col[j]
                    if S_GRID[j - 1] > p[q]: lo[q] = S_GRID[j - 1]; glo[q] = col[j - 1]
                    else: lo[q] = p[q]; glo[q] = g0[q]
                else:
                    lo[q] = hi[q] = S_GRID[-1]; glo[q] = ghi[q] = 0.0
        # Illinois regula falsi on the bracket (g(lo) <= 0 < g(hi))
        side = np.zeros(na)
        for _ in range(12):
            den = ghi - glo
            ok = den > 0
            mid = np.where(ok, lo - glo * (hi - lo) / np.where(ok, den, 1), lo)
            if np.all(hi - lo < 1e-7) or np.all(np.abs(np.minimum(-glo, ghi)) < 1e-9):
                break
            gm = g_of(c1, idx, mid)[0]
            up = gm > 0
            hi = np.where(up, mid, hi); ghi = np.where(up, gm, ghi)
            lo = np.where(up, lo, mid); glo = np.where(up, glo, gm)
            glo = np.where(up & (side == 1), glo / 2, glo)
            ghi = np.where(~up & (side == -1), ghi / 2, ghi)
            side = np.where(up, 1, -1)
        den = ghi - glo
        s = np.where(den > 0, lo - glo * (hi - lo) / np.where(den > 0, den, 1), lo)
        _, fr, TA, TB, dA, dB = g_of(c1, idx, s)
        prev[aj] = s
        T[idx] = fr * TA + (1 - fr) * TB
        dp[idx] = np.sqrt(dA * dB)
    return T, dp


def main():
    pkg, out = sys.argv[1], sys.argv[2]
    site = json.load(open(os.path.join(pkg, 'site.json')))
    oils = {r['oil']: Oil(r) for r in read(os.path.join(pkg, 'oils.csv'))}
    lines = {r['line']: r for r in read(os.path.join(pkg, 'lines.csv'))}
    surveys = read(os.path.join(pkg, 'surveys.csv'))
    work = read(os.path.join(pkg, 'work_log.csv'))
    recs = read(os.path.join(pkg, 'records.csv'))

    pipeline = {}
    for ln, r in lines.items():
        for s in 'AB'[:int(r['pipes'])]:
            pipeline[f'{ln}-{s}'] = ln
    # last covering work per pipe
    lastwork = {}
    for w in work:
        job = w['job'].lower()
        if any(t in job for t in ('cover', 'lag', 'insul', 'clad')):
            p = w['pipe'].strip().upper()
            lastwork[p] = max(lastwork.get(p, ''), w['date'])
    valid = {p: [] for p in pipeline}
    for s in surveys:
        p = s['pipe']
        if p in valid and s['date'] > lastwork.get(p, ''):
            valid[p].append(s)
    need = [p for p in pipeline if not valid[p]]
    if need:
        allow = int(site.get('survey_allowance', 0))
        order = need[:allow]
        try:
            res = subprocess.run(['heatsurvey', pkg] + order, capture_output=True, text=True, timeout=30)
            if res.returncode != 0 or res.stderr.strip():
                print('heatsurvey:', res.stderr.strip(), file=sys.stderr)
            rows = list(csv.DictReader(res.stdout.strip().splitlines()))
            for s in rows:
                if s.get('pipe') in valid:
                    valid[s['pipe']].append(s)
        except Exception as e:
            print('heatsurvey failed:', e, file=sys.stderr)
    def geom(p):
        r = lines[pipeline[p]]
        return oils[r['oil']], float(r['bore_mm']) / 1000, float(r['length_m'])
    for p in pipeline:
        if not valid[p]:   # no survey of the covering as it stands: fall back to the latest on file
            old = [s for s in surveys if s['pipe'] == p]
            print('warning: no survey of the present covering of', p, file=sys.stderr)
            if old:
                last = max(s['date'] for s in old)
                valid[p] = [s for s in old if s['date'] == last]
            else:
                sys.exit('no survey for ' + p)
    S = [(p, s) for p, ss in valid.items() for s in ss]
    g = [geom(p) for p, _ in S]
    c = P([x[0] for x in g], [x[1] for x in g], [x[2] for x in g])
    F = lambda key: np.array([float(s[key]) for _, s in S])
    u = fit_uo(c, F('flow_t_h') / 3.6, F('t_in_C'), F('t_amb_C'), F('t_out_C'))
    acc = {}
    for (p, _), x in zip(S, u):
        acc.setdefault(p, []).append(x)
    Uo = {p: float(np.mean(v)) for p, v in acc.items()}
    for p, v in acc.items():
        print(p, ' '.join('%.4f' % x for x in v), file=sys.stderr)

    # records: single pipes and pairs, all at once
    n = len(recs)
    L_ = [lines[x['line']] for x in recs]
    c = P([oils[r['oil']] for r in L_], [float(r['bore_mm']) / 1000 for r in L_], [float(r['length_m']) for r in L_])
    m = np.array([float(x['flow_t_h']) for x in recs]) / 3.6
    Tin = np.array([float(x['t_in_C']) for x in recs]); Ta = np.array([float(x['t_amb_C']) for x in recs])
    pair = np.array([int(r['pipes']) == 2 for r in L_])
    uA = np.array([Uo[x['line'] + '-A'] for x in recs])
    uB = np.array([Uo.get(x['line'] + '-B', 1.0) for x in recs])
    T = np.zeros(n); dp = np.zeros(n)
    sg = ~pair
    if sg.any():
        cs = P([oils[r['oil']] for r, s in zip(L_, sg) if s], c.D[sg], c.L[sg])
        T[sg], dp[sg] = pipe(cs, m[sg], Tin[sg], Ta[sg], uA[sg])
    if pair.any():
        T, dp = pairs(oils, lines, recs, pair, m, Tin, Ta, uA, uB, T, dp)
    res = {x['record']: (d / 1000, t) for x, d, t in zip(recs, dp, T)}
    with open(out, 'w') as f:
        f.write('record,dp_kPa,t_out_C\n')
        for x in recs:
            d, t = res[x['record']]
            f.write('%s,%.4f,%.4f\n' % (x['record'], d, t))


if __name__ == '__main__':
    main()
