"""The sealed method of MS-GB: grinding temperature (uniform band source moving over a semi-infinite body at high
Peclet number) and the burn-limited depth of cut.

theta_max(a) is the surface temperature rise 1.13 Rw q sqrt(lc / vw) / beta with lc = sqrt(a ds) and q = P / (b lc),
P = b (p0 + p1 V) + u b a vw; the rise first falls with depth (the sliding power over a short contact) and then rises.
a_max() is the largest depth at which the rise is within the allowed rise (the upper root), found on a logarithmic
grid of depths and refined by Brent's method."""
import numpy as np
from scipy.optimize import brentq

C_BAND = 1.13


def theta_max(a_um, v_mm_s, b_mm, ds_mm, p0_w_mm, u_j_mm3, Rw, beta):
    """Surface temperature rise (K) for depth a (um), work speed v (mm/s), width b (mm), wheel diameter ds (mm);
    net power P = b p0 + u Q (W), Q = b a v (mm3/s)."""
    a = a_um / 1000.0
    lc = np.sqrt(a * ds_mm)                       # mm
    P = b_mm * p0_w_mm + u_j_mm3 * b_mm * a * v_mm_s
    q = P / (b_mm * lc) * 1e6                     # W/m2
    return C_BAND * Rw * q * np.sqrt((lc / 1000) / (v_mm_s / 1000)) / beta


def a_max(v, b, ds, p0, u, Rw, beta, dT):
    """Largest depth (um) with theta_max <= dT (upper root); None if every depth burns."""
    f = lambda a: theta_max(a, v, b, ds, p0, u, Rw, beta) - dT
    grid = np.geomspace(0.1, 500, 2000)
    vals = f(grid)
    if vals.min() > 0:
        return None
    i = np.where(vals <= 0)[0][-1]
    if i == len(grid) - 1:
        return grid[-1]
    return brentq(f, grid[i], grid[i + 1], xtol=1e-9)
