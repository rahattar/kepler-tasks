#!/usr/bin/env python3
"""TS-2 heated oil line calculation for one site package.
Usage: python3 lines.py PACKAGE_DIR OUT_CSV
Pairs: the flow split is any split giving both pipes the same pressure drop
(TS-2 s.4). Where several exist, only hydraulically stable ones
(dp1'(m1)+dp2'(m2) > 0) can persist; the survey's hours are followed in order
and the split stays on the branch it was on in the previous hour."""
import sys, os, csv, json
import numpy as np

NSTEP = 30

def visc_coef(n50, n100):
    T1, T2 = 323.15, 373.15
    y1 = np.log10(np.log10(n50 + 0.7)); y2 = np.log10(np.log10(n100 + 0.7))
    B = (y1 - y2) / (np.log10(T2) - np.log10(T1))
    return y1 + B * np.log10(T1), B

def nu(T, A, B):
    return (10.0 ** (10.0 ** (A - B * np.log10(T + 273.15))) - 0.7) * 1e-6

def pipe(m, Tin, Ta, D, L, Uo, oil):
    """Vectorised over m, Tin, Ta. Returns dp [kPa], outlet T [C]."""
    rho, cp, k, A, B = oil
    m = np.asarray(m, float)
    Tb = np.broadcast_to(np.asarray(Tin, float), m.shape).copy()
    Ta = np.broadcast_to(np.asarray(Ta, float), m.shape)
    xs = L * (np.arange(NSTEP + 1) / NSTEP) ** 3
    u = m / (rho * np.pi * D * D / 4)
    RePrD = u * D * D * cp * rho / k  # Re*Pr*D (independent of viscosity)
    Th0 = Tb - Ta  # oil above surroundings (sign kept); integrate ln|Th|
    sg = np.where(Th0 < 0, -1.0, 1.0)
    Th0 = np.where(np.abs(Th0) < 1e-9, 1e-9 * sg, Th0)
    def f(x, z):
        Tb = Ta + sg * np.exp(z)
        nub = nu(Tb, A, B)
        if x <= 0:
            Tw = Tb; nuw = nub; c = Uo
        else:
            G = (1.077 * (RePrD / x) ** (1 / 3) - 0.7)
            N0 = (3.66 ** 3 + 0.7 ** 3 + np.maximum(G, 0) ** 3 * np.sign(G)) ** (1 / 3) * k / D
            Tw = Tb - 0.3 * (Tb - Ta)
            for _ in range(40):
                nuw = nu(Tw, A, B)
                h = N0 * (nub / nuw) ** 0.14
                Tn = (h * Tb + Uo * Ta) / (h + Uo)
                d = np.max(np.abs(Tn - Tw))
                Tw = Tn
                if d < 1e-7:
                    break
            nuw = nu(Tw, A, B)
            h = N0 * (nub / nuw) ** 0.14
            c = Uo * h / (h + Uo)
        dz = -np.pi * D * c / (m * cp)
        dp = 32.0 * rho * u * nub / (D * D) * (nuw / nub) ** 0.5
        return dz, dp
    z = np.log(np.abs(Th0))
    P = np.zeros_like(m)
    for i in range(NSTEP):
        x0, x1 = xs[i], xs[i + 1]; hh = x1 - x0
        k1, p1 = f(x0, z)
        k2, p2 = f(x0 + hh / 2, z + hh / 2 * k1)
        k3, p3 = f(x0 + hh / 2, z + hh / 2 * k2)
        k4, p4 = f(x1, z + hh * k3)
        z = z + hh / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
        P = P + hh / 6 * (p1 + 2 * p2 + 2 * p3 + p4)
    Tb = Ta + sg * np.exp(z)
    return P / 1000.0, Tb

def solve_pair(M, Tin, Ta, args):
    """M,Tin,Ta arrays (records in time order). Returns dp, Tout arrays."""
    n = len(M)
    # fraction grid on (0, 0.5): dense near 0
    s = np.linspace(0.0, 1.0, 41)[1:]
    a_lo = 0.5 * (np.expm1(4 * s) / np.expm1(4))
    a_lo[-1] = 0.5
    a = np.concatenate([a_lo, 1 - a_lo[-2::-1]])  # (0,1) symmetric grid
    na = len(a)
    mm = (M[:, None] * a[None, :])
    dpg, _ = pipe(mm.ravel(), np.repeat(Tin, na), np.repeat(Ta, na), *args)
    dpg = dpg.reshape(n, na)
    nh = len(a_lo)  # index nh-1 is a=0.5
    F = dpg[:, :nh] - dpg[:, ::-1][:, :nh]   # dp(a)-dp(1-a), a in a_lo
    # candidate roots: brackets in a_lo[:-1] (excluding a=0.5 itself)
    cand = []  # (rec, lo, hi)
    for i in range(n):
        for j in range(nh - 2):
            if F[i, j] == 0 or F[i, j] * F[i, j + 1] < 0:
                cand.append((i, a_lo[j], a_lo[j + 1]))
    roots = [[] for _ in range(n)]
    if cand:
        ci = np.array([c[0] for c in cand]); lo = np.array([c[1] for c in cand]); hi = np.array([c[2] for c in cand])
        def Fv(x):
            d, _ = pipe(np.concatenate([x * M[ci], (1 - x) * M[ci]]),
                        np.concatenate([Tin[ci], Tin[ci]]), np.concatenate([Ta[ci], Ta[ci]]), *args)
            k = len(x); return d[:k] - d[k:]
        flo = Fv(lo)
        for _ in range(28):
            mid = 0.5 * (lo + hi); fm = Fv(mid)
            left = np.sign(fm) == np.sign(flo)
            lo = np.where(left, mid, lo); flo = np.where(left, fm, flo); hi = np.where(left, hi, mid)
        r = 0.5 * (lo + hi)
        for c, x in zip(ci, r):
            roots[c].append(x)
    # stability: S(a) = dp'(aM) + dp'((1-a)M) > 0 ; evaluate by finite difference
    allr = [(i, x) for i in range(n) for x in roots[i] + [0.5]]
    ri = np.array([t[0] for t in allr]); rx = np.array([t[1] for t in allr])
    e = np.minimum(1e-3, rx * 0.01)
    m1 = rx * M[ri]; m2 = (1 - rx) * M[ri]; dm = e * M[ri]
    mvals = np.concatenate([m1 - dm, m1 + dm, m2 - dm, m2 + dm, m1, m2])
    T6 = np.tile(Tin[ri], 6); A6 = np.tile(Ta[ri], 6)
    dv, tv = pipe(mvals, T6, A6, *args)
    k = len(rx); dv = dv.reshape(6, k); tv = tv.reshape(6, k)
    stab = (dv[1] - dv[0]) + (dv[3] - dv[2]) > 0
    dpr = 0.5 * (dv[4] + dv[5])
    tr = rx * tv[4] + (1 - rx) * tv[5]
    sols = [[] for _ in range(n)]
    for j in range(k):
        sols[ri[j]].append((rx[j], bool(stab[j]), dpr[j], tr[j]))
    dp = np.empty(n); T = np.empty(n)
    prev = 0.5  # start-up: the pair starts balanced
    for i in range(n):
        st = [s_ for s_ in sols[i] if s_[1]] or sols[i]
        best = min(st, key=lambda s_: abs(s_[0] - prev))
        prev = best[0]; dp[i] = best[2]; T[i] = best[3]
    return dp, T

def main(pkg, out):
    rd = lambda f: list(csv.DictReader(open(os.path.join(pkg, f), newline='')))
    oils = {r['oil'].strip(): r for r in rd('oils.csv')}
    lines = {r['line'].strip(): r for r in rd('lines.csv')}
    recs = rd('records.csv')
    res = {}
    bylin = {}
    for idx, r in enumerate(recs):
        bylin.setdefault(r['line'].strip(), []).append(idx)
    for ln, idxs in bylin.items():
        l = lines[ln]; o = oils[l['oil'].strip()]
        A, B = visc_coef(float(o['nu50_cSt']), float(o['nu100_cSt']))
        oil = (float(o['density_kg_m3']), float(o['cp_J_kgK']), float(o['k_W_mK']), A, B)
        idxs = sorted(idxs, key=lambda i: float(recs[i]['hour']))
        M = np.array([float(recs[i]['flow_t_h']) for i in idxs]) / 3.6
        Tin = np.array([float(recs[i]['t_in_C']) for i in idxs])
        Ta = np.array([float(recs[i]['t_amb_C']) for i in idxs])
        args = (float(l['bore_mm']) / 1000, float(l['length_m']), float(l['u_o_W_m2K']), oil)
        if int(float(l['pipes'])) == 2:
            dp, T = solve_pair(M, Tin, Ta, args)
        else:
            dp, T = pipe(M, Tin, Ta, *args)
        for j, i in enumerate(idxs):
            res[i] = (dp[j], T[j])
    with open(out, 'w', newline='') as fh:
        w = csv.writer(fh); w.writerow(['record', 'dp_kPa', 't_out_C'])
        for i, r in enumerate(recs):
            w.writerow([r['record'], '%.6g' % res[i][0], '%.4f' % res[i][1]])

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
