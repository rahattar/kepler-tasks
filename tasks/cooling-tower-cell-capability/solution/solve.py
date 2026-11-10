"""Reference solution for cooling-tower-cell-capability: rate each CT-2 cell by plant procedure TP-31 from the records in
/app/data and write cell,capability_pct.

    python3 solve.py DATA_DIR OUT_CSV

Every correction below is taken from the records themselves; the comments say which record shows it.
"""
import os
import sys

import numpy as np
import pandas as pd

CELLS = ["C%d" % i for i in range(1, 9)]
CPW = 4.186                  # kJ/kg K (TP-31)
RHO_W = 994.0                # kg/m3 (TP-31)
C_D, N = 1.4001, 0.65        # fill design sheet
G_D, P_D, RHO_D = 424.8, 160.0, 1.0654   # TP-31 / fill design sheet
GPM_PER_M3H = 4.402868
RECIRC_K, WEST = 2.0, (225.0, 315.0)     # 2025 survey: C8 inlet wet bulb in westerly wind
STACK_C8 = pd.Timestamp("2026-06-24 15:00")   # C8's taller fan stack (log); no recirculation since (see rate())
WIND_MAX, FAN_MIN = 4.5, 60.0            # TP-31 valid hours
DCS_UTC_OFFSET_H = 5                     # US Central daylight time, all of April to September


# ---- psychrometrics (TP-31) ----
def psat(t):
    """Saturation pressure over water, Pa (Hyland-Wexler)."""
    T = np.asarray(t, float) + 273.15
    return np.exp(-5.8002206e3 / T + 1.3914993 - 4.8640239e-2 * T + 4.1764768e-5 * T ** 2
                  - 1.4452093e-8 * T ** 3 + 6.5459673 * np.log(T))


def wsat(t, p):
    ps = psat(t)
    return 0.621945 * ps / (p - ps)


def hsat(t, p):
    return 1.006 * t + wsat(t, p) * (2501.0 + 1.86 * t)


def wet_bulb(tdb, rh, p):
    w = 0.621945 * rh / 100.0 * psat(tdb) / (p - rh / 100.0 * psat(tdb))
    lo, hi = tdb - 40.0, tdb.copy()
    for _ in range(60):
        twb = 0.5 * (lo + hi)
        ws = wsat(twb, p)
        wc = ((2501 - 2.326 * twb) * ws - 1.006 * (tdb - twb)) / (2501 + 1.86 * tdb - 4.186 * twb)
        hi = np.where(wc > w, twb, hi)
        lo = np.where(wc > w, lo, twb)
    return 0.5 * (lo + hi), w


def density(tdb, w, p):
    return p / (287.042 * (tdb + 273.15) * (1 + 1.607858 * w)) * (1 + w)


def merkel(th, tc, lg, h_in, p, n=40):
    s = np.linspace(0.0, 1.0, n + 1)
    t = tc[:, None] + (th - tc)[:, None] * s
    ha = h_in[:, None] + (lg * CPW)[:, None] * (t - tc[:, None])
    with np.errstate(divide="ignore", invalid="ignore"):
        f = CPW / (hsat(t, p[:, None]) - ha)
    w = np.ones(n + 1); w[1:-1:2] = 4; w[2:-1:2] = 2
    return (th - tc) / (3 * n) * np.sum(w * f, axis=1)


# ---- records ----
def load(data):
    d = pd.read_csv(os.path.join(data, "dcs_hourly.csv"), parse_dates=["time"])
    m = pd.read_csv(os.path.join(data, "met_station.csv"), parse_dates=["timestamp"])
    tags = pd.read_csv(os.path.join(data, "dcs_tags.csv")).set_index("tag")
    m["time"] = m.timestamp - pd.Timedelta(hours=DCS_UTC_OFFSET_H)      # met logger keeps UTC
    d = d.merge(m.drop(columns="timestamp"), on="time", how="left")
    q = {}
    for c in CELLS:
        f = d[c + "_riser_flow"].values.astype(float)
        q[c] = f / GPM_PER_M3H if tags.loc[c + "_riser_flow", "unit"].strip() == "US gpm" else f
    return d, q


def step_time(x, t, lo, hi):
    """Hour in [lo, hi) that best splits x into two medians (largest jump of 48 h medians either side)."""
    s = pd.Series(x, index=t)
    best, when = 0.0, None
    for k in np.flatnonzero((t >= lo) & (t < hi)):
        a, b = s.iloc[max(0, k - 48):k].median(), s.iloc[k:k + 48].median()
        if abs(b - a) > best:
            best, when = abs(b - a), k
    return when


def corrected_flows(d, q):
    t = pd.DatetimeIndex(d.time)
    hdr = d.header_flow_m3h.values.astype(float)
    # C3 meter zero: from 2026-07-06 to 2026-07-20 14:00 C3's riser was shut and blanked with a blind flange (log), yet
    # its meter still reads ~150 m3/h; that reading is the meter's zero error.
    shut = (t >= pd.Timestamp("2026-07-06")) & (t < pd.Timestamp("2026-07-20 14:00")) \
        & (q["C3"] < 0.3 * np.median(q["C3"])) & (d.C3_fan_pct.values == 0)
    z3 = float(np.median(q["C3"][shut]))
    q["C3"] = q["C3"] - z3
    # C6 meter: the header balance steps once (2026-06-01 00:00); C6 is the only riser whose reading jumps at that
    # hour, mid-week, with nothing else about the cell changing. Remove the step as a scale on C6.
    res = sum(q.values()) - hdr
    k = step_time(res, t, pd.Timestamp("2026-04-20"), pd.Timestamp("2026-09-25"))
    t6 = t[k]
    jumps = {c: np.median(q[c][k:k + 6]) - np.median(q[c][k - 6:k]) for c in CELLS}
    who = max(jumps, key=lambda c: jumps[c])
    k = k - 3 + int(np.argmax(np.diff(q[who][k - 4:k + 4])))     # the hour of the jump in that riser's own reading
    t6 = t[k]
    before = (t < t6) & (t >= pd.Timestamp("2026-04-16"))
    after = t >= t6
    step = np.median(res[after]) - np.median(res[before])
    scale = 1.0 + step / (np.median(q[who][after]) - step)
    q[who] = np.where(t >= t6, q[who] / scale, q[who])
    # C1 bypass: what the header meter sees beyond the eight risers
    B = hdr - sum(q.values())
    B = pd.Series(B).rolling(25, center=True, min_periods=6).median().values
    info = dict(c3_zero=z3, c3_shut_hours=int(shut.sum()), step_time=str(t6), step_cell=who, step_scale=scale,
                bypass_open=float(np.median(B[t < pd.Timestamp("2026-04-14")])),
                bypass_after=float(np.median(B[t >= pd.Timestamp("2026-04-15")])))
    return q, B, info


def rate(data):
    d, q = load(data)
    t = pd.DatetimeIndex(d.time)
    q, B, info = corrected_flows(d, q)
    p = d.pressure_kpa.values * 1000.0
    tdb, rh = d.dry_bulb_c.values, d.rh_pct.values
    wb, w = wet_bulb(tdb, rh, p)
    rho = density(tdb, w, p)
    west = (d.wind_from_deg.values >= WEST[0]) & (d.wind_from_deg.values <= WEST[1])
    th = {c: d[c + "_hw_in_c"].values.astype(float) for c in CELLS}
    tc = {c: d[c + "_cw_out_c"].values.astype(float) for c in CELLS}
    P = {c: d[c + "_fan_kw"].values.astype(float) for c in CELLS}
    spd = {c: d[c + "_fan_pct"].values.astype(float) for c in CELLS}
    run = {c: spd[c] >= FAN_MIN for c in CELLS}
    # C2: the replacement hot-water thermocouple (2026-06-20) reads a steady amount above the other risers, which
    # all share the header water; remove the change in its offset from their median.
    t2 = pd.Timestamp("2026-06-20")
    ref = np.median(np.vstack([th[c] for c in CELLS if c != "C2"]), axis=0)
    off = th["C2"] - ref
    th["C2"] = np.where(t >= t2, th["C2"] - (np.median(off[t >= t2]) - np.median(off[t < t2])), th["C2"])
    # C4: from the motor change (2026-06-15) its power at a given speed falls 20 % against the other fans while its
    # speed reference and water temperatures carry on as before: the new motor's power reading is low.
    t4 = pd.Timestamp("2026-06-15")
    norm = {c: P[c] / np.maximum(spd[c] / 100.0, 1e-3) ** 3 / rho for c in CELLS}
    peer = np.median(np.vstack([norm[c] for c in CELLS if c != "C4"]), axis=0)
    with np.errstate(divide="ignore", invalid="ignore"):
        r4 = norm["C4"] / peer
    ok4 = run["C4"]
    f4 = np.median(r4[ok4 & (t >= t4)]) / np.median(r4[ok4 & (t < t4)])
    P["C4"] = np.where(t >= t4, P["C4"] / f4, P["C4"])
    info["c4_power_factor"] = f4
    # C5: its "basin" sensor reads the common flume (the flow-weighted mean of every weir, the C1 bypass included);
    # take the other seven weirs out of the mix.
    q1_out = q["C1"] + B
    tot = sum(q.values()) + B
    others = q1_out * tc["C1"] + sum(q[c] * tc[c] for c in CELLS if c not in ("C1", "C5"))
    with np.errstate(divide="ignore", invalid="ignore"):
        tc["C5"] = (tot * tc["C5"] - others) / q["C5"]
    # C1: its weir reading mixes the fill water with the bypass water, which is at the header temperature.
    with np.errstate(divide="ignore", invalid="ignore"):
        tc["C1"] = ((q["C1"] + B) * tc["C1"] - B * th["C1"]) / q["C1"]
    out, end = {}, t.max()
    for c in CELLS:
        L = q[c] * RHO_W / 3600.0
        G = G_D * (np.maximum(P[c], 1e-6) / P_D) ** (1 / 3) * (rho / RHO_D) ** (2 / 3)
        wbi = wb + np.where((c == "C8") & west & (t < STACK_C8), RECIRC_K, 0.0)
        ok = run[c] & (d.wind_ms.values <= WIND_MAX) & np.isfinite(tc[c]) & (q[c] > 0) & (th[c] > tc[c])
        if c == "C3":
            ok &= t >= pd.Timestamp("2026-07-20 14:00")      # present fill: since the riser was reopened
        lg = L[ok] / G[ok]
        k = merkel(th[c][ok], tc[c][ok], lg, hsat(wbi[ok], p[ok]), p[ok])
        C = pd.Series(k * lg ** N, index=t[ok])
        C = C[np.isfinite(C)]
        if c == "C8":       # the stack ended the recirculation: westerly hours now rate like the others
            wst = pd.Series(west, index=t)[C.index].values
            aft = C.index >= STACK_C8
            info["c8_west_minus_other_after_stack_pct"] = 100 * (C[aft & wst].median() - C[aft & ~wst].median()) / C_D
            info["c8_west_minus_other_before_stack_pct"] = 100 * (C[~aft & wst].median() - C[~aft & ~wst].median()) / C_D
        # as it stands at the end of the record: straight line through the weekly medians, read at the last hour
        wk = C.groupby(C.index.to_period("W"))
        med, cnt = wk.median(), wk.size()
        med = med[cnt >= 10]
        x = np.array([((pr.start_time + pd.Timedelta(days=3.5)) - end) / pd.Timedelta(days=1) for pr in med.index])
        b = np.polyfit(x, med.values, 1)
        out[c] = 100.0 * np.polyval(b, 0.0) / C_D
    return out, info


def main():
    data = sys.argv[1] if len(sys.argv) > 1 else "/app/data"
    path = sys.argv[2] if len(sys.argv) > 2 else "/app/output/cell_capability.csv"
    out, info = rate(data)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w") as f:
        f.write("cell,capability_pct\n")
        for c in CELLS:
            f.write("%s,%.1f\n" % (c, out[c]))
    for k, v in info.items():
        print("%s: %s" % (k, v))
    for c in CELLS:
        print("%s %.1f" % (c, out[c]))


if __name__ == "__main__":
    main()
