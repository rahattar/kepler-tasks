"""line.py: sealed definition of one heated-oil line to TS-2 (steady, laminar, level).
Bulk energy balance along the line; a local inside film for thermally developing laminar flow with the
wall-viscosity correction, in series with the outside coefficient; laminar friction corrected for the wall
viscosity; viscosity by ASTM D341 through two points. Every argument may be an array (one entry per case)."""
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

if __name__ == "__main__":
    import time
    np.set_printoptions(precision=5, suppress=True, linewidth=160)
    A, B = walther(180.0, 25.0)
    m = np.geomspace(0.002, 3.0, 5000)
    for n in (60, 120, 240, 480, 960):
        t = time.process_time(); dp, To = march(m, 0.08, 600.0, 6.0, 75.0, 10.0, 950.0, 1900.0, 0.13, A, B, n=n); dt = time.process_time() - t
        if n == 60: ref = None
        print(n, "%.2fs for 5000 cases" % dt, dp[[0, 1000, 2500, 4999]] / 1e5, To[[0, 1000, 2500, 4999]])
        if n > 60: print("    max rel change in dp %.2e, max change in T %.2e" % (np.max(np.abs(dp / last[0] - 1)), np.max(np.abs(To - last[1]))))
        last = (dp, To)
