"""Truth physics of the carburizing core: CD-2 (core/data/docs/cd2_case_depth.md), batched over loads."""
import numpy as np

R_CAL = 1.987
RHO = 7.85e-3          # g/mm^3


def diffusivity(C, T_C):
    """Tibbetts: carbon in austenite, mm^2/s; C in wt %, T in C."""
    T = T_C + 273.15
    return 47.0 * np.exp(-1.6 * C) * np.exp(-(37000.0 - 6600.0 * C) / (R_CAL * T))


def run(T, Cp_eff, active, L, C0, beta, n=100, sub=4, picard=2, dt_rec=60.0):
    """All loads at once. T, Cp_eff, active: (loads, steps) at the record's 1 min steps; L: depth of each load's
    domain (mm, zero flux at its end); C0: core carbon; beta: mm/s. Returns final profiles (loads, n+1), the
    grid spacing, and the carbon taken up by each load per record step (g/mm^2 of surface)."""
    m, K = T.shape
    dx = L / n
    C = np.repeat(C0[:, None], n + 1, axis=1).astype(float)
    dt = dt_rec / sub
    uptake = np.zeros((m, K))
    vol = np.ones(n + 1); vol[0] = vol[-1] = 0.5
    for k in range(K):
        Tk, Ck, on = T[:, k], Cp_eff[:, k], active[:, k]
        b_eff = np.where(on, beta, 0.0)
        for _ in range(sub):
            Cold = C
            Cit = C
            for _ in range(picard):
                Cm = 0.5 * (Cit[:, 1:] + Cit[:, :-1])
                Df = np.where(on[:, None], diffusivity(Cm, Tk[:, None]), 0.0)     # faces (m, n)
                g = Df / (dx[:, None] ** 2)
                r = dt / vol[None, :]
                lo = np.zeros((m, n + 1)); up = np.zeros((m, n + 1)); di = np.ones((m, n + 1))
                up[:, :-1] = -r[:, :-1] * g
                lo[:, 1:] = -r[:, 1:] * g
                di[:, :-1] += r[:, :-1] * g
                di[:, 1:] += r[:, 1:] * g
                di[:, 0] += r[:, 0] * b_eff / dx
                rhs = Cold.copy()
                rhs[:, 0] += r[:, 0] * b_eff / dx * Ck
                # Thomas, vectorised over loads
                cp_ = np.empty((m, n + 1)); dp = np.empty((m, n + 1))
                cp_[:, 0] = up[:, 0] / di[:, 0]; dp[:, 0] = rhs[:, 0] / di[:, 0]
                for j in range(1, n + 1):
                    den = di[:, j] - lo[:, j] * cp_[:, j - 1]
                    cp_[:, j] = up[:, j] / den
                    dp[:, j] = (rhs[:, j] - lo[:, j] * dp[:, j - 1]) / den
                Cn = np.empty((m, n + 1)); Cn[:, n] = dp[:, n]
                for j in range(n - 1, -1, -1):
                    Cn[:, j] = dp[:, j] - cp_[:, j] * Cn[:, j + 1]
                Cit = Cn
            uptake[:, k] += b_eff * (Ck - Cit[:, 0]) * dt / 100.0 * RHO      # g per mm^2
            C = Cit
    return C, dx, uptake


def case_depth(C, dx, level=0.35):
    out = np.empty(len(C))
    for i, c in enumerate(C):
        j = np.flatnonzero(c < level)
        if len(j) == 0:
            out[i] = dx[i] * (len(c) - 1)
            continue
        j = j[0]
        if j == 0:
            out[i] = 0.0
            continue
        out[i] = dx[i] * (j - 1 + (c[j - 1] - level) / (c[j - 1] - c[j]))
    return out
