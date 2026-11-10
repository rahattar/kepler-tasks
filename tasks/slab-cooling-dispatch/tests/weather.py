"""Real weather: Chicago O'Hare TMY3 (NREL, via the EnergyPlus repository), resampled to 15 min,
with irradiance on a west-facing vertical facade from DNI/DHI/GHI (isotropic sky, ground albedo 0.2).

EPW times are local standard time; hour h covers (h-1, h]. Temperatures are treated as
instantaneous at the hour mark and interpolated linearly; irradiance components are hour
averages, held over the hour, with the incidence angle evaluated at each 15-min midpoint.
"""
import os
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
EPW = os.path.join(HERE, "chicago_tmy3.epw")
LAT, LON, TZ = 41.98, -87.92, -6.0
SPD = 96


def read_epw(path=EPW):
    rows = []
    with open(path) as f:
        for i, line in enumerate(f):
            if i < 8:
                continue
            p = line.strip().split(",")
            rows.append([float(p[1]), float(p[2]), float(p[3]), float(p[6]), float(p[7]),
                         float(p[13]), float(p[14]), float(p[15])])
    a = np.array(rows)
    assert a.shape[0] == 8760, a.shape
    return dict(month=a[:, 0], day=a[:, 1], hour=a[:, 2], T=a[:, 3], Tdp=a[:, 4],
                ghi=a[:, 5], dni=a[:, 6], dhi=a[:, 7])


def sun(doy, hour_lst):
    """Solar altitude sine and azimuth (deg from north, clockwise) at local standard time."""
    B = 2 * np.pi * (doy - 81) / 364.0
    eot = 9.87 * np.sin(2 * B) - 7.53 * np.cos(B) - 1.5 * np.sin(B)  # min
    decl = np.radians(23.45) * np.sin(2 * np.pi * (284 + doy) / 365.0)
    solar_t = hour_lst + (4 * (LON - 15 * TZ) + eot) / 60.0
    H = np.radians(15 * (solar_t - 12))
    lat = np.radians(LAT)
    sinalt = np.sin(lat) * np.sin(decl) + np.cos(lat) * np.cos(decl) * np.cos(H)
    alt = np.arcsin(np.clip(sinalt, -1, 1))
    cosaz = (np.sin(decl) - np.sin(alt) * np.sin(lat)) / (np.cos(alt) * np.cos(lat) + 1e-12)
    az = np.degrees(np.arccos(np.clip(cosaz, -1, 1)))
    az = np.where(H > 0, 360 - az, az)
    return sinalt, az


def year_15min(facade_az=270.0, albedo=0.2):
    w = read_epw()
    n = 365 * SPD
    t_h = np.arange(n) / 4.0                    # hours since Jan 1 00:00 LST
    # temperatures: value at hour mark k is EPW row k-1 (hour k of its day)
    hours = np.arange(1, 8761, dtype=float)
    T = np.interp(t_h, hours, w["T"], left=w["T"][0])
    Tdp = np.interp(t_h, hours, w["Tdp"], left=w["Tdp"][0])
    # irradiance: hour containing the 15-min midpoint
    tm = t_h + 0.125
    k = np.minimum(np.floor(tm).astype(int), 8759)
    dni, dhi, ghi = w["dni"][k], w["dhi"][k], w["ghi"][k]
    doy = np.floor(tm / 24.0) + 1
    sinalt, az = sun(doy, tm % 24.0)
    up = sinalt > 0.01
    cosinc = np.sqrt(1 - sinalt ** 2) * np.cos(np.radians(az - facade_az))
    beam = np.where(up, dni * np.clip(cosinc, 0, None), 0.0)
    Iv = beam + 0.5 * dhi + 0.5 * albedo * ghi
    return dict(Tout=T, Tdp=Tdp, Ivert=Iv, ghi=ghi, doy=doy.astype(int))


def dow(day_index):
    """TMY3 calendar in this file starts on a Sunday (EPW DATA PERIODS line). 0 = Monday."""
    return (day_index + 6) % 7


if __name__ == "__main__":
    y = year_15min()
    for name, d0, d1 in [("May20-Jul14 (logs)", 139, 195), ("Jul15-Sep08 (hidden)", 195, 251)]:
        s = slice(d0 * SPD, d1 * SPD)
        T = y["Tout"][s].reshape(-1, SPD)
        print(name, "Tout mean %.1f, mean daily max %.1f, max %.1f, min %.1f | facade I max %.0f, daily mean %.0f W/m2"
              % (T.mean(), T.max(1).mean(), T.max(), T.min(), y["Ivert"][s].max(), y["Ivert"][s].reshape(-1, SPD).mean(1).mean()))
        print("   weekly mean Tout:", np.round(T.reshape(-1, 7 * SPD).mean(1), 1),
              " dow of first day:", dow(d0))
