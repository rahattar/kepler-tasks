"""HT-5 as the sites' results were calculated: a round steel bar quenched in oil, radial conduction with
temperature-dependent properties and the oil's boiling curve at the surface.

This is the sealed definition the truth comes from. sites.py calls it for all loads of a site on 64 radial
intervals and about 5 600 time steps: finite volumes in r, the trapezoidal rule in time after four backward
Euler steps, properties and surface coefficient at the mid-step temperature by three passes, time steps that
grow from 1e-4 to 1e-3 of R^2 / (6e-6 m2/s). authoring/evidence/convergence.txt sets it against 200 intervals
and 22 000 steps. The reference solution in solution/ is its own program, on a coarser grid and with far
fewer steps.
"""
import numpy as np

RHO = 7800.0
PROBE = 14200.0            # J/m2K: converts a cooling rate of the standard probe to a heat flux per kelvin
STEELS = {
    "C45": dict(k=((20.0, 300.0, 600.0, 800.0, 900.0), (50.0, 44.0, 34.0, 26.0, 26.0)),
                cp=((20.0, 300.0, 600.0, 720.0, 800.0, 900.0), (470.0, 560.0, 750.0, 900.0, 650.0, 650.0))),
    "42CrMo4": dict(k=((20.0, 300.0, 600.0, 800.0, 900.0), (43.0, 40.0, 33.0, 27.0, 27.0)),
                    cp=((20.0, 300.0, 600.0, 720.0, 800.0, 900.0), (460.0, 550.0, 720.0, 850.0, 640.0, 640.0))),
}
RESULTS = ("t85_core_s", "cr700_core_K_s", "dT_max_K", "ts_core500_C", "t150_core_s")


def film(ts, cr_max, t_crmax, cr_300):
    """Heat transfer coefficient at surface temperature ts (HT-5 section 4), W/m2K."""
    h_p = PROBE * cr_max / (t_crmax - 40.0)
    h_3 = PROBE * cr_300 / 260.0
    lo = 0.6 * h_3
    top = 0.15 * h_p
    a = lo + (h_3 - lo) * (ts - 100.0) / 200.0
    b = h_3 + (h_p - h_3) * (ts - 300.0) / (t_crmax - 300.0)
    c = h_p + (top - h_p) * (ts - t_crmax) / 120.0
    return np.where(ts <= 100.0, lo, np.where(ts <= 300.0, a, np.where(ts <= t_crmax, b, np.where(ts <= t_crmax + 120.0, c, top))))


def solve(steel, diameter_mm, furnace_C, bath_C, cr_max, t_crmax, cr_300, nodes=64, f0=1e-4, growth=1.012, fmax=1e-3):
    """Results for loads of one steel, arrays of equal length. Returns {name: array}."""
    R = (np.asarray(diameter_mm, float) / 2000.0)[:, None]
    L, N = R.shape[0], nodes
    tb = np.asarray(bath_C, float)
    oil = [np.asarray(v, float) for v in (cr_max, t_crmax, cr_300)]
    kx, ky = (np.array(v) for v in STEELS[steel]["k"])
    cx, cy = (np.array(v) for v in STEELS[steel]["cp"])
    j = np.arange(N + 1)
    dr = R / N
    rf = (j[:-1] + 0.5) * dr                                  # faces, (L, N)
    vol = np.empty((L, N + 1))
    vol[:, 0] = rf[:, 0] ** 2
    vol[:, 1:-1] = rf[:, 1:] ** 2 - rf[:, :-1] ** 2
    vol[:, -1] = R[:, 0] ** 2 - rf[:, -1] ** 2
    area = 2.0 * rf / dr
    T = np.repeat(np.asarray(furnace_C, float)[:, None], N + 1, axis=1)
    tau = R[:, 0] ** 2 / 6.0e-6
    now = np.zeros(L)
    marks = {800.0: None, 725.0: None, 700.0: None, 675.0: None, 500.0: None, 150.0: None}
    when = {m: np.full(L, np.nan) for m in marks}
    ts500 = np.full(L, np.nan)
    dmax = np.zeros(L)
    n = 0
    while np.isnan(when[150.0]).any():
        f = min(f0 * growth ** n, fmax)
        dt = tau * f
        theta = 1.0 if n < 4 else 0.5
        Tm = T
        for _ in range(3):
            cap = RHO * np.interp(Tm, cx, cy) * vol / dt[:, None]
            kf = np.interp(0.5 * (Tm[:, 1:] + Tm[:, :-1]), kx, ky) * area
            hs = film(Tm[:, -1], *oil) * 2.0 * R[:, 0]
            lower = np.zeros((L, N + 1)); upper = np.zeros((L, N + 1))
            lower[:, 1:] = -theta * kf
            upper[:, :-1] = -theta * kf
            diag = cap - lower - upper
            diag[:, -1] += theta * hs
            flux = np.zeros((L, N + 1))
            g = kf * (T[:, 1:] - T[:, :-1])
            flux[:, :-1] += g
            flux[:, 1:] -= g
            flux[:, -1] -= hs * (T[:, -1] - tb)
            rhs = cap * T + (1.0 - theta) * flux
            rhs[:, -1] += theta * hs * tb
            cp_ = np.empty((L, N + 1)); dp = np.empty((L, N + 1))
            cp_[:, 0] = upper[:, 0] / diag[:, 0]
            dp[:, 0] = rhs[:, 0] / diag[:, 0]
            for i in range(1, N + 1):
                den = diag[:, i] - lower[:, i] * cp_[:, i - 1]
                cp_[:, i] = upper[:, i] / den
                dp[:, i] = (rhs[:, i] - lower[:, i] * dp[:, i - 1]) / den
            new = np.empty((L, N + 1))
            new[:, -1] = dp[:, -1]
            for i in range(N - 1, -1, -1):
                new[:, i] = dp[:, i] - cp_[:, i] * new[:, i + 1]
            Tm = theta * new + (1.0 - theta) * T if theta < 1.0 else new
        c0, c1 = T[:, 0], new[:, 0]
        for m in marks:
            hit = np.isnan(when[m]) & (c0 > m) & (c1 <= m)
            if hit.any():
                frac = (c0[hit] - m) / (c0[hit] - c1[hit])
                when[m][hit] = now[hit] + frac * dt[hit]
                if m == 500.0:
                    ts500[hit] = T[hit, -1] + frac * (new[hit, -1] - T[hit, -1])
        dmax = np.maximum(dmax, new[:, 0] - new[:, -1])
        now = now + dt
        T = new
        n += 1
        if n > 400000:
            raise RuntimeError("no end")
    return {"t85_core_s": when[500.0] - when[800.0], "cr700_core_K_s": 50.0 / (when[675.0] - when[725.0]),
            "dT_max_K": dmax, "ts_core500_C": ts500, "t150_core_s": when[150.0]}
