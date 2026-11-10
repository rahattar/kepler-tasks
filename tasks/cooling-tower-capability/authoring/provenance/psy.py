"""Psychrometrics and the Merkel integral (SI). Temperatures degC, pressure Pa, enthalpy kJ/kg dry air."""
import numpy as np

CPW = 4.186


def psat(t):
    T = np.asarray(t, float) + 273.15
    return np.exp(-5.8002206e3 / T + 1.3914993 - 4.8640239e-2 * T + 4.1764768e-5 * T ** 2
                  - 1.4452093e-8 * T ** 3 + 6.5459673 * np.log(T))


def wsat(t, p):
    ps = psat(t)
    return 0.621945 * ps / (p - ps)


def enthalpy(t, w):
    return 1.006 * t + w * (2501.0 + 1.86 * t)


def hsat(t, p):
    return enthalpy(t, wsat(t, p))


def w_from_rh(tdb, rh, p):
    pw = rh / 100.0 * psat(tdb)
    return 0.621945 * pw / (p - pw)


def wet_bulb(tdb, rh, p):
    """Thermodynamic wet bulb from dry bulb, RH (%) and pressure, by bisection on the psychrometric relation."""
    tdb = np.asarray(tdb, float); rh = np.asarray(rh, float); p = np.asarray(p, float)
    w = w_from_rh(tdb, rh, p)
    lo, hi = tdb - 40.0, tdb.copy()
    for _ in range(60):
        twb = 0.5 * (lo + hi)
        ws = wsat(twb, p)
        w_calc = ((2501 - 2.326 * twb) * ws - 1.006 * (tdb - twb)) / (2501 + 1.86 * tdb - 4.186 * twb)
        hi = np.where(w_calc > w, twb, hi)
        lo = np.where(w_calc > w, lo, twb)
    return 0.5 * (lo + hi)


def density(tdb, w, p):
    """Moist air density, kg/m3 of mixture."""
    return p / (287.042 * (tdb + 273.15) * (1 + 1.607858 * w)) * (1 + w)


def merkel(th, tc, lg, h_in, p, n=40):
    """KaV/L by Simpson's rule over the water range (vectorised over the inputs); air enthalpy rises with the heat the
    water gives up."""
    th, tc, lg, h_in, p = np.broadcast_arrays(*[np.asarray(x, float) for x in (th, tc, lg, h_in, p)])
    s = np.linspace(0.0, 1.0, n + 1)
    t = tc[..., None] + (th - tc)[..., None] * s
    ha = h_in[..., None] + (lg * CPW)[..., None] * (t - tc[..., None])
    f = CPW / (hsat(t, p[..., None]) - ha)
    wts = np.ones(n + 1); wts[1:-1:2] = 4; wts[2:-1:2] = 2
    return (th - tc) / (3 * n) * np.sum(wts * f, axis=-1)


def cold_water(th, lg, h_in, p, kavl, n=40):
    """Cold water temperature at which the Merkel integral equals kavl (vectorised bisection). A driving force that
    vanishes anywhere in the fill makes the integral infinite, which counts as too much cooling."""
    th, lg, h_in, p, kavl = np.broadcast_arrays(*[np.asarray(x, float) for x in (th, lg, h_in, p, kavl)])
    lo, hi = th - 25.0, th - 1e-3
    s = np.linspace(0.0, 1.0, n + 1)
    for _ in range(50):
        tc = 0.5 * (lo + hi)
        t = tc[..., None] + (th - tc)[..., None] * s
        ha = h_in[..., None] + (lg * CPW)[..., None] * (t - tc[..., None])
        drive = hsat(t, p[..., None]) - ha
        bad = np.any(drive <= 0, axis=-1)
        with np.errstate(divide="ignore", invalid="ignore"):
            m = merkel(th, tc, lg, h_in, p, n)
        too_cold = bad | (m > kavl)
        lo = np.where(too_cold, tc, lo)
        hi = np.where(too_cold, hi, tc)
    return 0.5 * (lo + hi)
