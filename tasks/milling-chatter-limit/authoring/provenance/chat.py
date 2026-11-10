"""The sealed method of MS-CH: zero-order (Altintas-Budak 1995) milling stability at a given spindle speed.

limit() finds, for each eigenvalue branch of det(I + Lambda [alpha][G(i wc)]) = 0 and each lobe k, the chatter
frequencies wc at which the lobe passes through the speed (wc 60 / (N n) - eps(wc) = 2 pi k, eps = pi - 2 atan
(Lambda_I / Lambda_R)), and returns the lowest positive a_lim = -2 pi Lambda_R (1 + kappa^2) / (N Kt) among them,
interpolated linearly between grid points. abs_min() is the lowest a_lim over all frequencies (the speed-independent
bound, used only by the route study).

Feed along x, y normal to it; immersion angle measured from y in the direction of rotation. Up-milling: phi_st = 0,
phi_ex = acos(1 - 2 ae/D); down-milling: phi_st = acos(2 ae/D - 1), phi_ex = pi."""
import numpy as np


def frf(f, modes):
    w = 2 * np.pi * np.asarray(f, float)
    G = np.zeros_like(w, dtype=complex)
    for fn, z, k in modes:
        wn = 2 * np.pi * fn
        G += (wn ** 2 / k) / (wn ** 2 - w ** 2 + 2j * z * wn * w)
    return G


def immersion(ae, D, milling):
    if milling == "up":
        return 0.0, np.arccos(1 - 2 * ae / D)
    return np.arccos(2 * ae / D - 1), np.pi


def alphas(phst, phex, Kr):
    def F(p):
        return np.array([0.5 * (np.cos(2 * p) - 2 * Kr * p + Kr * np.sin(2 * p)),
                         0.5 * (-np.sin(2 * p) - 2 * p + Kr * np.cos(2 * p)),
                         0.5 * (-np.sin(2 * p) + 2 * p + Kr * np.cos(2 * p)),
                         0.5 * (-np.cos(2 * p) - 2 * Kr * p - Kr * np.sin(2 * p))])
    return F(phex) - F(phst)


def limit(n0, f, Gx, Gy, N, Kt, Kr, phst, phex, kmax=60):
    """Stability limit (m) at spindle speed n0 (rpm) from FRFs sampled at f (Hz): the lowest positive a_lim over the
    chatter frequencies whose lobe passes through n0."""
    axx, axy, ayx, ayy = alphas(phst, phex, Kr)
    a0 = Gx * Gy * (axx * ayy - axy * ayx)
    a1 = axx * Gx + ayy * Gy
    wc = 2 * np.pi * np.asarray(f, float)
    best = np.inf
    for sgn in (1, -1):
        L = -(a1 + sgn * np.sqrt(a1 ** 2 - 4 * a0 + 0j)) / (2 * a0)
        LR, LI = L.real, L.imag
        alim = -2 * np.pi * LR / (N * Kt) * (1 + (LI / LR) ** 2)
        eps = np.pi - 2 * np.arctan(LI / LR)
        x = wc * 60 / (N * n0) - eps            # = 2 pi k on the lobe through n0
        for k in range(kmax):
            h = x - 2 * np.pi * k
            idx = np.where((np.sign(h[:-1]) != np.sign(h[1:])) & (alim[:-1] > 0) & (alim[1:] > 0))[0]
            for i in idx:
                t = h[i] / (h[i] - h[i + 1])
                best = min(best, alim[i] + t * (alim[i + 1] - alim[i]))
    return best


def abs_min(f, Gx, Gy, N, Kt, Kr, phst, phex):
    axx, axy, ayx, ayy = alphas(phst, phex, Kr)
    a0 = Gx * Gy * (axx * ayy - axy * ayx); a1 = axx * Gx + ayy * Gy
    best = np.inf
    for sgn in (1, -1):
        L = -(a1 + sgn * np.sqrt(a1 ** 2 - 4 * a0 + 0j)) / (2 * a0)
        alim = -2 * np.pi * L.real / (N * Kt) * (1 + (L.imag / L.real) ** 2)
        best = min(best, alim[alim > 0].min())
    return best
