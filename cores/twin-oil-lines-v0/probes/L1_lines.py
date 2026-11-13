import sys, csv
import numpy as np
np.seterr(all='ignore')

class Oil:
    def __init__(s, o):
        s.rho = float(o['density_kg_m3']); s.cp = float(o['cp_J_kgK']); s.k = float(o['k_W_mK'])
        y1 = np.log10(np.log10(float(o['nu50_cSt']) + .7)); y2 = np.log10(np.log10(float(o['nu100_cSt']) + .7))
        x1 = np.log10(323.15); x2 = np.log10(373.15)
        s.B = (y1 - y2) / (x2 - x1); s.A = y1 + s.B * x1
    def nu(s, T):  # m2/s, ASTM D341
        return (10 ** (10 ** (s.A - s.B * np.log10(T + 273.15))) - .7) * 1e-6

def pipe(oil, D, L, Uo, m, Tin, Ta, N=60):
    """One pipe, vectorised over arrays. Integrates in s = x^(1/3) (RK4). Returns dp [Pa], Tout [C]."""
    m = np.asarray(m, float); T = np.asarray(Tin, float) + 0 * m; Ta = np.asarray(Ta, float) + 0 * m
    rho, cp, k = oil.rho, oil.cp, oil.k
    u = m / (rho * np.pi * D * D / 4)
    hs = L ** (1 / 3) / N
    def rhs(s, T):
        x = max(s, 1e-12) ** 3
        nub = oil.nu(T); Re = u * D / nub; Pr = nub * rho * cp / k; Gz = Re * Pr * D / x
        N0 = (3.66 ** 3 + .7 ** 3 + (1.077 * np.cbrt(Gz) - .7) ** 3) ** (1 / 3)
        Tw = (T + Ta) / 2
        for _ in range(40):
            h = N0 * (nub / oil.nu(Tw)) ** .14 * k / D
            Tn = (h * T + Uo * Ta) / (h + Uo)
            done = np.max(np.abs(Tn - Tw)) < 1e-8
            Tw = Tn
            if done: break
        r = nub / oil.nu(Tw); h = N0 * r ** .14 * k / D
        q = np.pi * D * h * (T - Tw)
        dpdx = (64 / Re) * r ** -.5 * rho * u * u / (2 * D)
        j = 3 * s * s
        return -q / (m * cp) * j, dpdx * j
    p = np.zeros_like(m); s = 0.0
    for _ in range(N):
        k1, p1 = rhs(s, T); k2, p2 = rhs(s + hs / 2, np.maximum(T + hs / 2 * k1, Ta))
        k3, p3 = rhs(s + hs / 2, np.maximum(T + hs / 2 * k2, Ta)); k4, p4 = rhs(s + hs, np.maximum(T + hs * k3, Ta))
        T = np.maximum(T + hs / 6 * (k1 + 2 * k2 + 2 * k3 + k4), Ta); p = p + hs / 6 * (p1 + 2 * p2 + 2 * p3 + p4); s += hs
    return p, T

FR = np.concatenate([np.linspace(0.5, 0.9, 33)[:-1], 1 - np.geomspace(0.1, 0.0005, 30)])  # share of the flow in the larger-flow pipe

def pair(oil, D, L, Uo, M, Tin, Ta):
    """Split of a pair, record by record in time order. Only stable splits are taken; where more than one
    is possible the split follows the previous hour's state. Returns dp [Pa], mixed Tout [C]."""
    n = len(M); nf = len(FR)
    MM = np.repeat(M[:, None], nf, 1); TI = np.repeat(Tin[:, None], nf, 1); TA = np.repeat(Ta[:, None], nf, 1)
    F = np.repeat(FR[None, :], n, 0)
    p1, _ = pipe(oil, D, L, Uo, (MM * F).ravel(), TI.ravel(), TA.ravel(), N=30)
    p2, _ = pipe(oil, D, L, Uo, (MM * (1 - F)).ravel(), TI.ravel(), TA.ravel(), N=30)
    g = (p1 - p2).reshape(n, nf)
    lo = np.full(n, 0.5); hi = np.full(n, 0.5); prev = 0.5
    for i in range(n):
        gi = g[i]
        cands = []
        if gi[1] > 0:
            cands.append((0.5, 0.5, 0.5))
        for j in range(1, nf - 1):
            if gi[j] < 0 <= gi[j + 1]:
                cands.append((0.5 * (FR[j] + FR[j + 1]), FR[j], FR[j + 1]))
        if not cands:
            cands = [(0.5, 0.5, 0.5)]
        c = min(cands, key=lambda c: abs(c[0] - prev))
        lo[i], hi[i] = c[1], c[2]; prev = c[0]
    asym = hi > lo
    if asym.any():
        a, b = lo[asym].copy(), hi[asym].copy(); Ma, Ti_, Ta_ = M[asym], Tin[asym], Ta[asym]
        for _ in range(16):
            c = 0.5 * (a + b)
            pp, _ = pipe(oil, D, L, Uo, np.concatenate([Ma * c, Ma * (1 - c)]),
                         np.concatenate([Ti_, Ti_]), np.concatenate([Ta_, Ta_]), N=60)
            k = len(c); gc = pp[:k] - pp[k:]
            a = np.where(gc < 0, c, a); b = np.where(gc < 0, b, c)
        lo[asym] = 0.5 * (a + b)
    fr = lo
    pa, ta = pipe(oil, D, L, Uo, np.concatenate([M * fr, M * (1 - fr)]), np.concatenate([Tin, Tin]),
                  np.concatenate([Ta, Ta]), N=120)
    return 0.5 * (pa[:n] + pa[n:]), fr * ta[:n] + (1 - fr) * ta[n:]

def main(pk, out):
    rd = lambda f: list(csv.DictReader(open(f"{pk}/{f}", newline='')))
    oils = {o['oil'].strip(): Oil(o) for o in rd('oils.csv')}
    lines = {l['line'].strip(): l for l in rd('lines.csv')}
    recs = rd('records.csv')
    res = {}
    by = {}
    for i, r in enumerate(recs):
        by.setdefault(r['line'].strip(), []).append(i)
    for ln, idx in by.items():
        l = lines[ln]; o = oils[l['oil'].strip()]
        idx.sort(key=lambda i: float(recs[i]['hour']))
        D = float(l['bore_mm']) / 1000; L = float(l['length_m']); Uo = float(l['u_o_W_m2K'])
        M = np.array([float(recs[i]['flow_t_h']) for i in idx]) / 3.6
        Ti = np.array([float(recs[i]['t_in_C']) for i in idx]); Ta = np.array([float(recs[i]['t_amb_C']) for i in idx])
        if int(float(l['pipes'])) == 2:
            dp, To = pair(o, D, L, Uo, M, Ti, Ta)
        else:
            dp, To = pipe(o, D, L, Uo, M, Ti, Ta, N=120)
        for j, i in enumerate(idx):
            res[i] = (dp[j], To[j])
    with open(out, 'w', newline='') as f:
        w = csv.writer(f); w.writerow(['record', 'dp_kPa', 't_out_C'])
        for i, r in enumerate(recs):
            w.writerow([r['record'], '%.6g' % (res[i][0] / 1e3), '%.4f' % res[i][1]])

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
