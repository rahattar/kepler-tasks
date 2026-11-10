"""A second implementation of the rating, written apart from solution/solve.py and sharing no code with it.

    python3 authoring/evidence/independent.py > authoring/evidence/independent.txt

Different choices throughout: IAPWS-IF97 saturation pressure; wet bulb by Newton iteration on the adiabatic
saturation balance; air density from partial pressures; the Merkel integral by 12-point Gauss-Legendre quadrature;
the met clock converted with the America/Chicago time zone; C3's meter zero from the C3 outage (riser valve shut);
C6's meter error by least squares on the header balance; the bypass flow as a 12-hour mean of the balance; C2's
offset against the mean of its neighbours C1 and C3 over 10 days either side; C4's power error from hours with every
fan at full speed; the end-of-record value from a Theil-Sen line through daily medians.
"""
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
DATA = os.path.join(ROOT, "environment", "data")
sys.path.insert(0, os.path.join(ROOT, "tests"))
import ct2  # noqa: E402

NAMES = ["C%d" % i for i in range(1, 9)]


def p_sat(t_c):
    """IAPWS-IF97 region 4 saturation pressure, Pa."""
    n = [0.11670521452767e4, -0.72421316703206e6, -0.17073846940092e2, 0.12020824702470e5, -0.32325550322333e7,
         0.14915108613530e2, -0.48232657361591e4, 0.40511340542057e6, -0.23855557567849, 0.65017534844798e3]
    T = np.asarray(t_c, float) + 273.15
    th = T + n[8] / (T - n[9])
    A = th ** 2 + n[0] * th + n[1]
    Bc = n[2] * th ** 2 + n[3] * th + n[4]
    C = n[5] * th ** 2 + n[6] * th + n[7]
    return (2 * C / (-Bc + np.sqrt(Bc ** 2 - 4 * A * C))) ** 4 * 1e6


def w_of(pv, p):
    return 0.621945 * pv / (p - pv)


def h_air(t, w):
    return 1.006 * t + w * (2501.0 + 1.86 * t)


def h_saturated(t, p):
    return h_air(t, w_of(p_sat(t), p))


def wet_bulb(tdb, w, p):
    """Newton on f(twb) = h(tdb, w) + (ws(twb) - w) 4.186 twb - h_sat(twb) = 0."""
    x = tdb - 5.0
    for _ in range(30):
        f = h_air(tdb, w) + (w_of(p_sat(x), p) - w) * 4.186 * x - h_saturated(x, p)
        e = 1e-4
        f2 = h_air(tdb, w) + (w_of(p_sat(x + e), p) - w) * 4.186 * (x + e) - h_saturated(x + e, p)
        x = x - f / ((f2 - f) / e)
    return x


def rho_moist(tdb, w, p):
    pv = p * w / (0.621945 + w)
    T = tdb + 273.15
    return (p - pv) / (287.055 * T) + pv / (461.52 * T)


GL_X, GL_W = np.polynomial.legendre.leggauss(12)


def kavl(th, tc, lg, h1, p):
    t = 0.5 * (th + tc)[:, None] + 0.5 * (th - tc)[:, None] * GL_X
    ha = h1[:, None] + 4.186 * lg[:, None] * (t - tc[:, None])
    with np.errstate(divide="ignore", invalid="ignore"):
        return 0.5 * (th - tc) * np.sum(GL_W * 4.186 / (h_saturated(t, p[:, None]) - ha), axis=1)


def theil_sen_end(day_x, y):
    i, j = np.triu_indices(len(day_x), 1)
    s = np.median((y[j] - y[i]) / (day_x[j] - day_x[i]))
    b = np.median(y - s * day_x)
    return b       # value at x = 0 (the last hour)


def main():
    dcs = pd.read_csv(os.path.join(DATA, "dcs_hourly.csv"))
    dcs.index = pd.to_datetime(dcs.time)
    met = pd.read_csv(os.path.join(DATA, "met_station.csv"))
    utc = pd.to_datetime(met.timestamp).dt.tz_localize("UTC")
    met.index = utc.dt.tz_convert("America/Chicago").dt.tz_localize(None)
    x = dcs.join(met.drop(columns="timestamp"), how="left")
    idx = x.index
    tags = pd.read_csv(os.path.join(DATA, "dcs_tags.csv")).set_index("tag")["unit"]
    flow = {}
    for c in NAMES:
        v = x[c + "_riser_flow"].astype(float)
        flow[c] = v * 0.2271247 if "gpm" in tags[c + "_riser_flow"] else v
    header = x.header_flow_m3h.astype(float)
    # C3 meter zero: C3's riser blanked from 2026-07-06 (log) until it reopened 07-20 14:00
    shut = (idx > "2026-07-07") & (idx < "2026-07-20 12:00")
    vals = np.sort(flow["C3"][shut].values)
    zero = vals[len(vals) // 10:-len(vals) // 10].mean()
    flow["C3"] = flow["C3"] - zero
    # C6: residual = bypass - b * C6 reading after its step; fit on the hours from 04-16
    resid = header - sum(flow.values())
    fit = idx >= "2026-04-16"
    after = (idx >= "2026-06-01").astype(float)
    A = np.column_stack([np.ones(fit.sum()), -(after * flow["C6"])[fit]])
    coef = np.linalg.lstsq(A, resid[fit].values, rcond=None)[0]
    frac = coef[1]                           # share of the reading that is not water
    flow["C6"] = flow["C6"] * np.where(after > 0, 1 - frac, 1.0)
    byp = (header - sum(flow.values())).rolling(12, center=True, min_periods=4).mean()
    # psychrometrics
    p = x.pressure_kpa.values * 1000
    tdb = x.dry_bulb_c.values
    pv = x.rh_pct.values / 100 * p_sat(tdb)
    w = w_of(pv, p)
    wb = wet_bulb(tdb, w, p)
    rho = rho_moist(tdb, w, p)
    hot = {c: x[c + "_hw_in_c"].values.astype(float) for c in NAMES}
    cold = {c: x[c + "_cw_out_c"].values.astype(float) for c in NAMES}
    kw = {c: x[c + "_fan_kw"].values.astype(float) for c in NAMES}
    sp = {c: x[c + "_fan_pct"].values.astype(float) for c in NAMES}
    # C2 thermocouple
    nb = 0.5 * (hot["C1"] + hot["C3"])
    d2 = hot["C2"] - nb
    t2 = pd.Timestamp("2026-06-20")
    w_b = (idx >= t2 - pd.Timedelta(days=10)) & (idx < t2)
    w_a = (idx >= t2) & (idx < t2 + pd.Timedelta(days=10))
    hot["C2"] = np.where(idx >= t2, hot["C2"] - (np.median(d2[w_a]) - np.median(d2[w_b])), hot["C2"])
    # C4 power: hours with all eight fans at full speed
    full = np.all(np.vstack([sp[c] == 100 for c in NAMES]), axis=0)
    others = np.mean(np.vstack([kw[c] for c in NAMES if c != "C4"]), axis=0)
    with np.errstate(divide="ignore", invalid="ignore"):
        r = kw["C4"] / others
    t4 = pd.Timestamp("2026-06-15")
    k4 = np.median(r[full & (idx >= t4)]) / np.median(r[full & (idx < t4)])
    kw["C4"] = np.where(idx >= t4, kw["C4"] / k4, kw["C4"])
    # C1: fill water from the weir mix; C5: from the flume mix of all eight basins (C1's basin incl. the bypass)
    q = {c: flow[c].values for c in NAMES}
    bq = byp.values
    with np.errstate(divide="ignore", invalid="ignore"):
        fill1 = (cold["C1"] * (q["C1"] + bq) - hot["C1"] * bq) / q["C1"]
        basin_heat = cold["C1"] * (q["C1"] + bq) + sum(q[c] * cold[c] for c in NAMES if c not in ("C1", "C5"))
        cold["C5"] = (cold["C5"] * (sum(q.values()) + bq) - basin_heat) / q["C5"]
    cold["C1"] = fill1
    west = (x.wind_from_deg.values >= 225) & (x.wind_from_deg.values <= 315)
    calm = x.wind_ms.values <= 4.5
    last = idx.max()
    out = {}
    for c in NAMES:
        L = q[c] * 994.0 / 3600.0
        G = 424.8 * (np.clip(kw[c], 1e-6, None) / 160.0) ** (1 / 3) * (rho / 1.0654) ** (2 / 3)
        wbi = wb + (2.0 * (west & (idx < pd.Timestamp("2026-06-24 15:00"))) if c == "C8" else 0.0)
        use = (sp[c] >= 60) & calm & np.isfinite(cold[c]) & (L > 0) & (hot[c] > cold[c])
        if c == "C3":
            use &= idx >= pd.Timestamp("2026-07-20 14:00")
        lg = L[use] / G[use]
        C = kavl(hot[c][use], cold[c][use], lg, h_saturated(wbi[use], p[use]), p[use]) * lg ** 0.65
        s = pd.Series(C, index=idx[use]).replace([np.inf, -np.inf], np.nan).dropna()
        daily = s.groupby(s.index.floor("D")).agg(["median", "size"])
        daily = daily[daily["size"] >= 4]
        dx = ((daily.index + pd.Timedelta(hours=12)) - last) / pd.Timedelta(days=1)
        out[c] = 100 * theil_sen_end(np.asarray(dx, float), daily["median"].values) / 1.4001
    print("Independent implementation: capability at the end of the record, percent of design\n")
    print("cell  reported   true   miss (pp)")
    worst = 0.0
    for c in NAMES:
        m = out[c] - ct2.CAPABILITY[c]
        worst = max(worst, abs(m))
        print("%-4s  %8.1f  %5.1f  %+6.1f" % (c, out[c], ct2.CAPABILITY[c], m))
    print("\nC3 meter zero %.1f m3/h; C6 reading %.1f %% not water after 06-01; C4 power factor %.3f; bypass after 04-15 "
          "%.0f m3/h" % (zero, 100 * frac, k4, np.median(byp[idx >= "2026-04-15"])))
    print("Largest miss: %.1f pp" % worst)


if __name__ == "__main__":
    main()
