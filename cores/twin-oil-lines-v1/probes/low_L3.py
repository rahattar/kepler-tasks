import sys, os, csv, json, subprocess
import numpy as np

NSTEP = int(os.environ.get('NSTEP', 40))
LAGWORDS = ('cover', 'insul', 'lag', 'clad', 'jacket', 'wrap', 'sheath')


def rd(path):
    with open(path, newline='') as f:
        return list(csv.DictReader(f))


class Oils:
    def __init__(self, rows):
        self.p = {}
        for r in rows:
            rho = float(r['density_kg_m3']); cp = float(r['cp_J_kgK']); k = float(r['k_W_mK'])
            v1, v2 = float(r['nu50_cSt']), float(r['nu100_cSt'])
            T1, T2 = np.log10(323.15), np.log10(373.15)
            y1, y2 = np.log10(np.log10(v1 + 0.7)), np.log10(np.log10(v2 + 0.7))
            B = (y1 - y2) / (T2 - T1); A = y1 + B * T1
            self.p[r['oil'].strip()] = (rho, cp, k, A, B)


def nu_si(A, B, T):
    # kinematic viscosity m2/s, T in C
    return (10.0 ** (10.0 ** (A - B * np.log10(T + 273.15))) - 0.7) * 1e-6


def integrate(m, Tin, Ta, Uo, D, L, rho, cp, k, A, B, n=NSTEP):
    """Vectorised over arrays. m kg/s. Returns (dp Pa, Tout C)."""
    m = np.asarray(m, float); Tin = np.asarray(Tin, float) + 0 * m
    Ta = Ta + 0 * m; Uo = Uo + 0 * m; D = D + 0 * m; L = L + 0 * m
    rho = rho + 0 * m; cp = cp + 0 * m; k = k + 0 * m; A = A + 0 * m; B = B + 0 * m
    area = np.pi * D * D / 4
    u = m / (rho * area)
    Tw = [Tin.copy()]

    def rhs(s, Tb):
        Tb = np.clip(Tb, np.minimum(Ta, Tin), np.maximum(Ta, Tin))
        x = L * s ** 3
        dxds = 3 * L * s * s
        nub = nu_si(A, B, Tb)
        Re = u * D / nub
        Pr = nub * rho * cp / k
        tw = Tw[0]
        if s <= 0:
            # infinite h: wall at bulk
            tw = Tb.copy(); Tw[0] = tw
            f = 64 / Re
            dp = f * rho * u * u / (2 * D) * dxds
            return np.zeros_like(Tb), dp
        Gz = Re * Pr * D / x
        base = (3.66 ** 3 + 0.7 ** 3 + (1.077 * np.cbrt(Gz) - 0.7) ** 3) ** (1 / 3)
        for _ in range(6):
            nuw = nu_si(A, B, tw)
            h = base * (nub / nuw) ** 0.14 * k / D
            tw = (h * Tb + Uo * Ta) / (h + Uo)
        nuw = nu_si(A, B, tw)
        h = base * (nub / nuw) ** 0.14 * k / D
        Tw[0] = tw
        q = np.pi * D * h * (Tb - tw)
        dT = -q / (m * cp) * dxds
        f = 64 / Re * (nuw / nub) ** 0.5
        dp = f * rho * u * u / (2 * D) * dxds
        return dT, dp

    Tb = Tin.copy(); p = np.zeros_like(Tb)
    hs = 1.0 / n
    for i in range(n):
        s = i * hs
        k1, p1 = rhs(s, Tb)
        k2, p2 = rhs(s + hs / 2, Tb + hs / 2 * k1)
        k3, p3 = rhs(s + hs / 2, Tb + hs / 2 * k2)
        k4, p4 = rhs(s + hs, Tb + hs * k3)
        Tb = np.clip(Tb + hs / 6 * (k1 + 2 * k2 + 2 * k3 + k4), np.minimum(Ta, Tin), np.maximum(Ta, Tin))
        p = p + hs / 6 * (p1 + 2 * p2 + 2 * p3 + p4)
    return p, Tb


def fit_uo(m, Tin, Tout, Ta, D, L, op):
    m = np.asarray(m, float)
    lo = np.full(m.shape, -12.0); hi = np.full(m.shape, 6.0)  # log Uo
    for _ in range(45):
        mid = (lo + hi) / 2
        _, T = integrate(m, Tin, Ta, np.exp(mid), D, L, *op)
        big = T < Tout  # too much loss
        hi = np.where(big, mid, hi); lo = np.where(big, lo, mid)
    return np.exp((lo + hi) / 2)

GRID = np.concatenate([np.geomspace(1e-4, 0.1, 10), np.linspace(0.13, 0.87, 13), 1 - np.geomspace(0.1, 1e-4, 10)])


def pairF(fr, ii, m, Tin, Ta, UA, UB, D, L, op):
    M = m[ii]; o = op[:, ii]
    pa, ta = integrate(M * fr, Tin[ii], Ta[ii], UA[ii], D[ii], L[ii], *o)
    pb, tb = integrate(M * (1 - fr), Tin[ii], Ta[ii], UB[ii], D[ii], L[ii], *o)
    return pa - pb, pa, pb, ta, tb


def solve_pairs(idx, recs, m, Tin, Ta, UA, UB, D, L, op, dp, To):
    args = (m, Tin, Ta, UA, UB, D, L, op)
    n = len(idx); ng = len(GRID)
    rep = np.repeat(idx, ng); fr = np.tile(GRID, n)
    Fg = pairF(fr, rep, *args)[0].reshape(n, ng)
    # all stable brackets: F goes from <=0 to >0
    cand = []  # (record pos, g)
    for k in range(n):
        for g in range(ng - 1):
            if Fg[k, g] <= 0 < Fg[k, g + 1]:
                cand.append((k, g))
        if not any(c[0] == k for c in cand[-ng:]):
            # no stable crossing: take the end the flow drifts to
            g = 0 if Fg[k, 0] > 0 else ng - 2
            cand.append((k, g))
    ck = np.array([c[0] for c in cand]); cg = np.array([c[1] for c in cand])
    ii = idx[ck]
    lo = GRID[cg].copy(); hi = GRID[cg + 1].copy()
    flo = Fg[ck, cg].copy(); fhi = Fg[ck, cg + 1].copy()
    side = np.zeros(len(ii))
    for _ in range(10):
        x = (lo * fhi - hi * flo) / (fhi - flo)
        x = np.where(np.isfinite(x) & (x > lo) & (x < hi), x, 0.5 * (lo + hi))
        fx = pairF(x, ii, *args)[0]
        neg = fx <= 0
        lo = np.where(neg, x, lo); flo = np.where(neg, fx, flo)
        hi = np.where(neg, hi, x); fhi = np.where(neg, fhi, fx)
        fhi = np.where(neg & (side == -1), fhi / 2, fhi)
        flo = np.where(~neg & (side == 1), flo / 2, flo)
        side = np.where(neg, -1, 1)
    x = (lo * fhi - hi * flo) / (fhi - flo)
    x = np.where(np.isfinite(x) & (x >= lo) & (x <= hi), x, 0.5 * (lo + hi))
    _, pa, pb, ta, tb = pairF(x, ii, *args)
    roots = {}
    for j, k in enumerate(ck):
        roots.setdefault(int(k), []).append(j)
    pos = {int(i): k for k, i in enumerate(idx)}
    groups = {}
    for i in idx:
        groups.setdefault(recs[i]['line'].strip(), []).append(int(i))
    seqs = [sorted(v, key=lambda i: float(recs[i]['hour'])) for v in groups.values()]
    prev = np.full(len(seqs), 0.5)
    lg = lambda v: np.log(v / (1 - v))
    for step in range(max(len(s) for s in seqs)):
        act = [q for q in range(len(seqs)) if step < len(seqs[q])]
        ri = np.array([seqs[q][step] for q in act])
        Fp = pairF(prev[act], ri, *args)[0]
        for q, i, f in zip(act, ri, Fp):
            pv = prev[q]
            xs = [(x[j], j) for j in roots[pos[int(i)]]]
            near = [t for t in xs if abs(lg(t[0]) - lg(pv)) < 1e-6]
            if near:
                pick = near[0]
            elif f > 0:
                below = [t for t in xs if t[0] <= pv]
                pick = max(below) if below else min(xs)
            else:
                above = [t for t in xs if t[0] >= pv]
                pick = min(above) if above else max(xs)
            j = pick[1]; xv = x[j]
            dp[i] = 0.5 * (pa[j] + pb[j]); To[i] = xv * ta[j] + (1 - xv) * tb[j]
            prev[q] = xv


def main():
    pkg, out = sys.argv[1], sys.argv[2]
    site = json.load(open(os.path.join(pkg, 'site.json')))
    oils = Oils(rd(os.path.join(pkg, 'oils.csv')))
    lines = {r['line'].strip(): r for r in rd(os.path.join(pkg, 'lines.csv'))}
    surveys = rd(os.path.join(pkg, 'surveys.csv'))
    work = rd(os.path.join(pkg, 'work_log.csv'))
    recs = rd(os.path.join(pkg, 'records.csv'))

    pipes = {}
    for ln, r in lines.items():
        for j in range(int(r['pipes'])):
            pipes[ln + '-' + 'AB'[j]] = ln
    lastjob = {}
    for w in work:
        job = w['job'].lower()
        if any(t in job for t in LAGWORDS):
            pp = w['pipe'].strip()
            lastjob[pp] = max(lastjob.get(pp, ''), w['date'].strip())
    valid = {p: [] for p in pipes}
    for s in surveys:
        pp = s['pipe'].strip()
        if pp in valid and s['date'].strip() > lastjob.get(pp, ''):
            valid[pp].append(s)
    need = [p for p in pipes if not valid[p]]
    if need:
        allow = int(site.get('survey_allowance', 0))
        order = need[:allow]
        try:
            res = subprocess.run(['heatsurvey', pkg] + order, capture_output=True, text=True, timeout=40)
            for r in csv.DictReader(res.stdout.strip().splitlines()):
                if r.get('pipe', '').strip() in valid:
                    r['date'] = '9999'
                    valid[r['pipe'].strip()].append(r)
        except Exception as e:
            sys.stderr.write('heatsurvey failed: %s\n' % e)
        for p in need:
            if not valid[p]:
                # no survey of the covering as it stands: fall back to the latest on file
                sys.stderr.write('no valid survey for %s, using older surveys\n' % p)
                old = sorted((s for s in surveys if s['pipe'].strip() == p), key=lambda s: s['date'])
                valid[p] = old[-1:]

    # fit Uo for every valid survey, vectorised
    sl = [(p, s) for p in pipes for s in valid[p]]
    def geo(p):
        r = lines[pipes[p]]
        return float(r['bore_mm']) / 1000, float(r['length_m']), oils.p[r['oil'].strip()]
    Uo = {}
    if sl:
        G = [geo(p) for p, _ in sl]
        D = np.array([g[0] for g in G]); L = np.array([g[1] for g in G])
        op = [np.array([g[2][i] for g in G]) for i in range(5)]
        m = np.array([float(s['flow_t_h']) for _, s in sl]) / 3.6
        u = fit_uo(m, np.array([float(s['t_in_C']) for _, s in sl]),
                   np.array([float(s['t_out_C']) for _, s in sl]),
                   np.array([float(s['t_amb_C']) for _, s in sl]), D, L, op)
        for (p, s), v in zip(sl, u):
            Uo.setdefault(p, []).append((s['date'], v))
    U = {}
    for p in pipes:
        if p in Uo:
            U[p] = float(np.mean([v for _, v in Uo[p]]))
        else:
            U[p] = float(np.mean([v for l in Uo.values() for _, v in l]))
    if os.environ.get('LINES_DEBUG'):
        for p in pipes:
            sys.stderr.write('%s %s\n' % (p, ' '.join('%s:%.4f' % t for t in Uo.get(p, []))))

    n = len(recs)
    D = np.zeros(n); L = np.zeros(n); op = np.zeros((5, n)); npp = np.zeros(n, int)
    UA = np.zeros(n); UB = np.zeros(n)
    m = np.array([float(r['flow_t_h']) for r in recs]) / 3.6
    Tin = np.array([float(r['t_in_C']) for r in recs]); Ta = np.array([float(r['t_amb_C']) for r in recs])
    for i, r in enumerate(recs):
        ln = r['line'].strip(); lr = lines[ln]
        D[i] = float(lr['bore_mm']) / 1000; L[i] = float(lr['length_m'])
        op[:, i] = oils.p[lr['oil'].strip()]
        npp[i] = int(lr['pipes'])
        UA[i] = U[ln + '-A']; UB[i] = U.get(ln + '-B', UA[i])
    dp = np.zeros(n); To = np.zeros(n)
    s1 = npp == 1
    if s1.any():
        a, b = integrate(m[s1], Tin[s1], Ta[s1], UA[s1], D[s1], L[s1], *op[:, s1])
        dp[s1] = a; To[s1] = b
    s2 = np.where(~s1)[0]
    if len(s2):
        solve_pairs(s2, recs, m, Tin, Ta, UA, UB, D, L, op, dp, To)
    with open(out, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['record', 'dp_kPa', 't_out_C'])
        for r, a, b in zip(recs, dp, To):
            w.writerow([r['record'], '%.6g' % (a / 1000), '%.4f' % b])


if __name__ == '__main__':
    main()
