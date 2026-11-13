"""sym_lines.py PACKAGE_DIR OUT_CSV: every pair taken to divide evenly."""

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

def main(pkg, out):
    oils = {r["oil"]: r for r in csv.DictReader(open(os.path.join(pkg, "oils.csv")))}
    lines = {r["line"]: r for r in csv.DictReader(open(os.path.join(pkg, "lines.csv")))}
    rec = list(csv.DictReader(open(os.path.join(pkg, "records.csv"))))
    g = lambda f: np.array([f(r) for r in rec], float)
    L_ = [lines[r["line"]] for r in rec]; O_ = [oils[l["oil"]] for l in L_]
    pipes = np.array([float(l["pipes"]) for l in L_])
    A, B = walther(np.array([float(o["nu50_cSt"]) for o in O_]), np.array([float(o["nu100_cSt"]) for o in O_]))
    dp, T = march(g(lambda r: float(r["flow_t_h"])) / 3.6 / pipes, np.array([float(l["bore_mm"]) for l in L_]) / 1e3,
                  np.array([float(l["length_m"]) for l in L_]), np.array([float(l["u_o_W_m2K"]) for l in L_]),
                  g(lambda r: float(r["t_in_C"])), g(lambda r: float(r["t_amb_C"])),
                  np.array([float(o["density_kg_m3"]) for o in O_]), np.array([float(o["cp_J_kgK"]) for o in O_]),
                  np.array([float(o["k_W_mK"]) for o in O_]), A, B, n=200)
    with open(out, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["record", "dp_kPa", "t_out_C"])
        for r, a, b in zip(rec, dp, T): w.writerow([r["record"], "%.6g" % (a / 1e3), "%.4f" % b])

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
