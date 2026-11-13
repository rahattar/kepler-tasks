#!/usr/bin/env python3
"""TS-2 heated oil line calculation for one site package.
Usage: python3 lines.py PACKAGE_DIR OUT_CSV
Pairs: the flow split is solved for equal pressure drop; where several stable
splits exist, the survey's history (records in hour order) selects the branch."""
import sys, csv, os
import numpy as np

def oilfun(o):
    T1, T2 = 323.15, 373.15
    y1 = np.log10(np.log10(o['nu50'] + 0.7)); y2 = np.log10(np.log10(o['nu100'] + 0.7))
    B = (y1 - y2) / (np.log10(T2) - np.log10(T1)); A = y1 + B * np.log10(T1)
    return lambda Tc: 10 ** (10 ** (A - B * np.log10(Tc + 273.15))) - 0.7

NS = 40
def pipe(m, Tin, Ta, D, L, Uo, o, nu, N=None):
    N = NS if N is None else N
    """Vectorised: returns (dp kPa, Tout C) for pipe mass flows m (kg/s)."""
    rho, cp, k = o['rho'], o['cp'], o['k']
    m = np.asarray(m, float)
    Tb = np.broadcast_to(np.asarray(Tin, float), m.shape).copy()
    Ta = np.broadcast_to(np.asarray(Ta, float), m.shape)
    u = m / (rho * np.pi * D * D / 4)
    xs = L * np.linspace(0, 1, N + 1) ** 3          # graded toward the entry
    Tlo = np.minimum(Ta, Tb); Thi = np.maximum(Ta, Tb)
    def rates(x, Tb):
        Tb = np.minimum(np.maximum(Tb, Tlo), Thi)
        nb = nu(Tb); Re = u * D / (nb * 1e-6); Pr = nb * 1e-6 * rho * cp / k
        Gz = Re * Pr * D / max(x, 1e-12)
        N0 = (3.66 ** 3 + 0.7 ** 3 + (1.077 * np.cbrt(Gz) - 0.7) ** 3) ** (1 / 3)
        Tw = Tb
        for _ in range(6):
            nw = nu(Tw)
            h = N0 * (nb / nw) ** 0.14 * k / D
            Tw = (h * Tb + Uo * Ta) / (h + Uo)
        nw = nu(Tw)
        q = np.pi * D * Uo * (Tw - Ta)
        f = 64 / Re * (nw / nb) ** 0.5
        return -q / (m * cp), f * rho * u * u / (2 * D)
    dp = np.zeros_like(m)
    for i in range(N):
        x0, x1 = xs[i], xs[i + 1]; hx = x1 - x0
        a1, g1 = rates(x0, Tb); a2, g2 = rates(x0 + hx / 2, Tb + hx / 2 * a1)
        a3, g3 = rates(x0 + hx / 2, Tb + hx / 2 * a2); a4, g4 = rates(x1, Tb + hx * a3)
        Tb = np.minimum(np.maximum(Tb + hx / 6 * (a1 + 2 * a2 + 2 * a3 + a4), Tlo), Thi); dp = dp + hx / 6 * (g1 + 2 * g2 + 2 * g3 + g4)
    return dp / 1e3, Tb

NG = 48
PHI = np.concatenate([np.geomspace(0.002, 0.1, 12), np.linspace(0.1, 0.5, NG - 11)[1:]])  # in (0, 0.5]

def pair_line(M, Ti, Ta, D, L, Uo, o, nu, NF=80):
    n = len(M)
    P = PHI[None, :]
    a, _ = pipe(M[:, None] * P, Ti[:, None], Ta[:, None], D, L, Uo, o, nu)
    b, _ = pipe(M[:, None] * (1 - P), Ti[:, None], Ta[:, None], D, L, Uo, o, nu)
    g = a - b                                         # g(0.5)=0
    # slope of single-pipe dp at the half flow, for stability of the even split
    eps = 1e-3
    s1, _ = pipe(M * (0.5 + eps), Ti, Ta, D, L, Uo, o, nu)
    s0, _ = pipe(M * (0.5 - eps), Ti, Ta, D, L, Uo, o, nu)
    sym_stable = s1 > s0
    # stable asymmetric roots: g crosses - to + in phi
    cand = []  # list per record of stable phis
    lo_l, hi_l, idx = [], [], []
    for r in range(n):
        for j in range(len(PHI) - 2):
            if g[r, j] < 0 <= g[r, j + 1] or (g[r, j] < 0 and g[r, j + 1] > 0):
                lo_l.append(PHI[j]); hi_l.append(PHI[j + 1]); idx.append(r)
    roots = [[] for _ in range(n)]
    if idx:
        idx = np.array(idx); lo = np.array(lo_l); hi = np.array(hi_l)
        for _ in range(30):
            mid = 0.5 * (lo + hi)
            a1, _ = pipe(M[idx] * mid, Ti[idx], Ta[idx], D, L, Uo, o, nu)
            b1, _ = pipe(M[idx] * (1 - mid), Ti[idx], Ta[idx], D, L, Uo, o, nu)
            neg = a1 - b1 < 0
            lo = np.where(neg, mid, lo); hi = np.where(neg, hi, mid)
        for r, p in zip(idx, 0.5 * (lo + hi)):
            roots[r].append(p)
    for r in range(n):
        if sym_stable[r]:
            roots[r].append(0.5)
        if not roots[r]:   # fallback (should not happen): least |g| point
            roots[r].append(0.5)
    # follow the branch through the survey
    phi = np.empty(n); prev = None
    for r in range(n):
        c = np.array(roots[r])
        if prev is None:
            p = 0.5 if sym_stable[r] else c[np.argmin(abs(c - 0.5))]
        else:
            p = c[np.argmin(abs(c - prev))]
        phi[r] = prev = p
    dpa, Ta_ = pipe(M * phi, Ti, Ta, D, L, Uo, o, nu, N=NF)
    dpb, Tb = pipe(M * (1 - phi), Ti, Ta, D, L, Uo, o, nu, N=NF)
    Tout = phi * Ta_ + (1 - phi) * Tb
    return 0.5 * (dpa + dpb), Tout, phi

def main(pkg, out):
    oils = {r['oil']: dict(rho=float(r['density_kg_m3']), cp=float(r['cp_J_kgK']), k=float(r['k_W_mK']),
                           nu50=float(r['nu50_cSt']), nu100=float(r['nu100_cSt']))
            for r in csv.DictReader(open(os.path.join(pkg, 'oils.csv')))}
    lines = {r['line']: r for r in csv.DictReader(open(os.path.join(pkg, 'lines.csv')))}
    recs = list(csv.DictReader(open(os.path.join(pkg, 'records.csv'))))
    res = {}
    groups = {}
    for i, r in enumerate(recs):
        groups.setdefault(r['line'], []).append(i)
    for ln, ids in groups.items():
        ids.sort(key=lambda i: float(recs[i]['hour']))
        Ld = lines[ln]; o = oils[Ld['oil']]; nu = oilfun(o)
        D = float(Ld['bore_mm']) / 1e3; L = float(Ld['length_m']); Uo = float(Ld['u_o_W_m2K'])
        M = np.array([float(recs[i]['flow_t_h']) for i in ids]) / 3.6
        Ti = np.array([float(recs[i]['t_in_C']) for i in ids])
        Ta = np.array([float(recs[i]['t_amb_C']) for i in ids])
        if int(Ld['pipes']) == 2:
            dp, T, _ = pair_line(M, Ti, Ta, D, L, Uo, o, nu)
        else:
            dp, T = pipe(M, Ti, Ta, D, L, Uo, o, nu, N=80)
        for i, a, b in zip(ids, dp, T):
            res[i] = (a, b)
    with open(out, 'w', newline='') as f:
        w = csv.writer(f); w.writerow(['record', 'dp_kPa', 't_out_C'])
        for i, r in enumerate(recs):
            w.writerow([r['record'], '%.6g' % res[i][0], '%.4f' % res[i][1]])

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
