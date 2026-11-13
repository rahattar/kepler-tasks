#!/usr/bin/env python3
"""ref_lines.py PACKAGE_DIR OUT_CSV: reference for the core. The line model of TS-2 section 3, every steady
division of a pair with its stability, and each pair followed through its survey hour by hour."""

import numpy as np

def walther(nu50_cSt, nu100_cSt):
    z = lambda nu: np.log10(np.log10(np.asarray(nu, float) + 0.7))
    T1, T2 = np.log10(323.15), np.log10(373.15)
    B = (z(nu50_cSt) - z(nu100_cSt)) / (T2 - T1); A = z(nu50_cSt) + B * T1
    return A, B

def nu_m2s(A, B, T_C):
    return (10.0 ** (10.0 ** (A - B * np.log10(T_C + 273.15))) - 0.7) * 1e-6

def march(mdot, D, L, Uo, Tin, Ta, rho, cp, k, A, B, n=240, grade=3.0):
    """pressure drop [Pa] and outlet bulk temperature [C]; midpoint rule on stations crowded to the inlet, each step taken with the local decay of (Tb - Ta) so that a nearly stagnant line stays stable."""
    mdot, D, L, Uo, Tin, Ta, rho, cp, k, A, B = np.broadcast_arrays(*[np.asarray(a, float) for a in (mdot, D, L, Uo, Tin, Ta, rho, cp, k, A, B)])
    s = np.linspace(0.0, 1.0, n + 1) ** grade
    v = mdot / (rho * np.pi * D * D / 4.0)
    Tb = Tin.copy(); dp = np.zeros(mdot.shape)
    c1 = 3.66 ** 3 + 0.7 ** 3

    def local(Tb, xm):
        nub = nu_m2s(A, B, Tb)
        Gz = (v * D / nub) * (nub * rho * cp / k) * D / xm
        Nu0 = (c1 + (1.077 * np.cbrt(Gz) - 0.7) ** 3) ** (1.0 / 3.0) * k / D
        Tw = (Nu0 * Tb + Uo * Ta) / (Nu0 + Uo)
        for _ in range(60):
            phi = nub / nu_m2s(A, B, Tw)
            hi = Nu0 * phi ** 0.14
            Tn = (hi * Tb + Uo * Ta) / (hi + Uo)
            done = np.max(np.abs(Tn - Tw)) < 1e-10
            Tw = Tn
            if done: break
        phi = nub / nu_m2s(A, B, Tw)
        hi = Nu0 * phi ** 0.14
        rate = np.pi * D * hi * Uo / (hi + Uo) / (mdot * cp)      # 1/m: d(Tb - Ta)/dx = -rate (Tb - Ta)
        grad = 32.0 * nub * rho * v / (D * D) / np.sqrt(phi)
        return rate, grad

    for i in range(n):
        h = (s[i + 1] - s[i]) * L; xm = 0.5 * (s[i] + s[i + 1]) * L
        r1, _ = local(Tb, xm)
        r2, g2 = local(Ta + (Tb - Ta) * np.exp(-0.5 * h * r1), xm)
        Tb = Ta + (Tb - Ta) * np.exp(-h * r2)
        dp = dp + h * g2
    return dp, Tb


import csv, os, sys

KEYS = ("D", "L", "Uo", "Tin", "Ta", "rho", "cp", "k", "A", "B")
N_STEPS = int(os.environ.get("REF_N", "140"))
FR = np.concatenate([np.geomspace(2e-4, 0.30, 44), np.linspace(0.32, 0.497, 12)])   # share of the lesser pipe


def one(m, par):
    return march(m, *[par[k] for k in KEYS], n=N_STEPS)


def pair_states(M, par):
    """even division of every record, and every uneven steady division with its stability."""
    R, J = len(M), len(FR)
    a = FR[None, :] * M[:, None]
    big = {k: np.repeat(par[k], J) for k in KEYS}
    f = (one(a.ravel(), big)[0] - one((M[:, None] - a).ravel(), big)[0]).reshape(R, J)
    dps, Ts = one(M / 2, par)
    r, j = np.nonzero(f[:, :-1] * f[:, 1:] < 0)
    if len(r) == 0:
        return dps, Ts, f[:, -1] < 0, r, None
    lo, hi, flo, fhi = a[r, j].copy(), a[r, j + 1].copy(), f[r, j].copy(), f[r, j + 1].copy()
    pr = {k: par[k][r] for k in KEYS}; Mr = M[r]; rising = flo < 0
    for _ in range(26):                                         # Illinois
        mid = (lo * fhi - hi * flo) / (fhi - flo)
        fm = one(mid, pr)[0] - one(Mr - mid, pr)[0]
        left = fm * flo > 0
        fhi = np.where(left, fhi * 0.5, fm); hi = np.where(left, hi, mid)
        flo2 = np.where(left, fm, flo * 0.5); lo = np.where(left, mid, lo); flo = flo2
        if np.max(np.abs(hi - lo) / Mr) < 1e-9: break
    root = (lo * fhi - hi * flo) / (fhi - flo)
    d1, T1 = one(root, pr); d2, T2 = one(Mr - root, pr)
    return dps, Ts, f[:, -1] < 0, r, (0.5 * (d1 + d2), (root * T1 + (Mr - root) * T2) / Mr, rising)


def main(pkg, out):
    oils = {r["oil"]: r for r in csv.DictReader(open(os.path.join(pkg, "oils.csv")))}
    lines = {r["line"]: r for r in csv.DictReader(open(os.path.join(pkg, "lines.csv")))}
    rec = list(csv.DictReader(open(os.path.join(pkg, "records.csv"))))
    L_ = [lines[r["line"]] for r in rec]; O_ = [oils[l["oil"]] for l in L_]
    A, B = walther(np.array([float(o["nu50_cSt"]) for o in O_]), np.array([float(o["nu100_cSt"]) for o in O_]))
    col = lambda rows, key, s=1.0: np.array([float(x[key]) for x in rows]) * s
    par = dict(D=col(L_, "bore_mm", 1e-3), L=col(L_, "length_m"), Uo=col(L_, "u_o_W_m2K"), Tin=col(rec, "t_in_C"), Ta=col(rec, "t_amb_C"),
               rho=col(O_, "density_kg_m3"), cp=col(O_, "cp_J_kgK"), k=col(O_, "k_W_mK"), A=A, B=B)
    M = col(rec, "flow_t_h") / 3.6; pipes = col(L_, "pipes")
    dp = np.zeros(len(rec)); T = np.zeros(len(rec))
    s = pipes == 1
    if s.any():
        dp[s], T[s] = one(M[s], {k: par[k][s] for k in KEYS})
    t = np.nonzero(pipes == 2)[0]
    if len(t):
        dps, Ts, sym_ok, r, un = pair_states(M[t], {k: par[k][t] for k in KEYS})
        uneven = {}
        if un is not None:
            for i in np.nonzero(un[2])[0]:
                uneven[int(r[i])] = i
        # a pair keeps the division it has while that division is steady and stable
        by_line = {}
        for q, idx in enumerate(t):
            by_line.setdefault(rec[idx]["line"], []).append((float(rec[idx]["hour"]), q))
        for seq in by_line.values():
            prev = 0
            for _, q in sorted(seq):
                has_u = q in uneven
                kind = (0 if sym_ok[q] or not has_u else 1) if prev == 0 else (1 if has_u else 0)
                if kind == 0: dp[t[q]], T[t[q]] = dps[q], Ts[q]
                else: dp[t[q]], T[t[q]] = un[0][uneven[q]], un[1][uneven[q]]
                prev = kind
    with open(out, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["record", "dp_kPa", "t_out_C"])
        for r_, a_, b_ in zip(rec, dp, T): w.writerow([r_["record"], "%.6g" % (a_ / 1e3), "%.4f" % b_])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
