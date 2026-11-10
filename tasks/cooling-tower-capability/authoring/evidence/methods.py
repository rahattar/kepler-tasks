"""The reference pipeline (solution/solve.py) with one step changed at a time, for route_study.py (traps) and
method_spread.py (other sound choices). capability(opts) returns {cell: percent}; opts switches:

  wrong-side (traps): db_as_wb, std_pressure, no_wind_filter, no_gpm, utc=<hours>, no_c3_zero, c6_trusted,
      c6_by_subtraction, no_bypass, no_unmix, c2_trusted, c4_trusted, recirc_always, flume_trusted, keep_old_fill,
      end='median'
  not a trap: no_recirc (C8's recirculation left out altogether)
  sound alternatives: end='last21' | 'last28' | 'daily', b_window=<hours>, c3_zero_from='mean' | 'inner',
      c2_ref='mean' | 'C1', simpson=<n>, c4_window=<days>, c6_before_from=<date>
"""
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "solution"))
import solve as S          # noqa: E402  (psychrometrics, Merkel, constants)
sys.path.insert(0, os.path.join(ROOT, "tests"))
import ct2                 # noqa: E402  (sealed values)

DATA = os.path.join(ROOT, "environment", "data")
CELLS = S.CELLS
TRUE = ct2.CAPABILITY
_RAW = {}


def raw():
    if not _RAW:
        _RAW["d"] = pd.read_csv(os.path.join(DATA, "dcs_hourly.csv"), parse_dates=["time"])
        _RAW["m"] = pd.read_csv(os.path.join(DATA, "met_station.csv"), parse_dates=["timestamp"])
    return _RAW["d"], _RAW["m"]


def endpoint(C, end, how):
    if len(C) < 20:
        return np.nan                     # (almost) no valid hours: no rating
    if how == "median":
        return np.median(C.values)
    if how in ("last21", "last28"):
        n = 21 if how == "last21" else 28
        return np.median(C[C.index >= end - pd.Timedelta(days=n)].values)
    if how == "daily":
        g = C.groupby(C.index.floor("D"))
        med = g.median()[g.size() >= 4]
        x = (med.index + pd.Timedelta(hours=12) - end) / pd.Timedelta(days=1)
        return np.polyval(np.polyfit(np.asarray(x, float), med.values, 1), 0.0)
    g = C.groupby(C.index.to_period("W"))
    med = g.median()[g.size() >= 10]
    if len(med) < 2:
        return np.median(C.values)
    x = np.array([((p.start_time + pd.Timedelta(days=3.5)) - end) / pd.Timedelta(days=1) for p in med.index])
    return np.polyval(np.polyfit(x, med.values, 1), 0.0)


def capability(o=None):
    o = o or {}
    d0, m0 = raw()
    m = m0.copy()
    m["time"] = m.timestamp - pd.Timedelta(hours=o.get("utc", 5))
    d = d0.merge(m.drop(columns="timestamp"), on="time", how="left")
    d[["dry_bulb_c", "rh_pct", "pressure_kpa", "wind_ms", "wind_from_deg"]] = \
        d[["dry_bulb_c", "rh_pct", "pressure_kpa", "wind_ms", "wind_from_deg"]].ffill().bfill()
    t = pd.DatetimeIndex(d.time)
    q = {}
    for c in CELLS:
        f = d[c + "_riser_flow"].values.astype(float)
        q[c] = f / S.GPM_PER_M3H if (c in ("C1", "C2", "C3", "C4") and not o.get("no_gpm")) else f
    hdr = d.header_flow_m3h.values.astype(float)
    if not o.get("no_c3_zero"):
        shut = (t >= pd.Timestamp("2026-07-06")) & (t < pd.Timestamp("2026-07-20 14:00")) \
            & (q["C3"] < 0.3 * np.median(q["C3"])) & (d.C3_fan_pct.values == 0)
        if o.get("c3_zero_from") == "mean":
            z = np.mean(q["C3"][shut])
        elif o.get("c3_zero_from") == "inner":
            z = np.median(q["C3"][(t >= pd.Timestamp("2026-07-08")) & (t < pd.Timestamp("2026-07-18"))])
        else:
            z = np.median(q["C3"][shut])
        q["C3"] = q["C3"] - z
    t6 = pd.Timestamp("2026-06-01 00:00")
    if o.get("c6_by_subtraction"):
        q["C6"] = np.where(t >= t6, hdr - sum(q[c] for c in CELLS if c != "C6"), q["C6"])
    elif not o.get("c6_trusted"):
        res = sum(q.values()) - hdr
        before = (t < t6) & (t >= pd.Timestamp(o.get("c6_before_from", "2026-04-16")))
        after = t >= t6
        step = np.median(res[after]) - np.median(res[before])
        scale = 1.0 + step / (np.median(q["C6"][after]) - step)
        q["C6"] = np.where(t >= t6, q["C6"] / scale, q["C6"])
    B = hdr - sum(q.values())
    win = o.get("b_window", 25)
    if win == "daily":
        B = pd.Series(B, index=t).groupby(t.floor("D")).transform("median").values
    else:
        B = pd.Series(B).rolling(win, center=True, min_periods=6).median().values
    if o.get("no_bypass"):
        B = np.zeros(len(t))
    p = d.pressure_kpa.values * 1000.0 if not o.get("std_pressure") else np.full(len(d), 101325.0)
    tdb, rh = d.dry_bulb_c.values, d.rh_pct.values
    wb, w = S.wet_bulb(tdb, rh, p)
    if o.get("db_as_wb"):
        wb = tdb.copy()
    rho = S.density(tdb, w, p)
    west = (d.wind_from_deg.values >= 225) & (d.wind_from_deg.values <= 315)
    th = {c: d[c + "_hw_in_c"].values.astype(float) for c in CELLS}
    tc = {c: d[c + "_cw_out_c"].values.astype(float) for c in CELLS}
    P = {c: d[c + "_fan_kw"].values.astype(float) for c in CELLS}
    spd = {c: d[c + "_fan_pct"].values.astype(float) for c in CELLS}
    if not o.get("c2_trusted"):
        t2 = pd.Timestamp("2026-06-20")
        if o.get("c2_ref") == "mean":
            ref = np.mean(np.vstack([th[c] for c in CELLS if c != "C2"]), axis=0)
        elif o.get("c2_ref") == "C1":
            ref = th["C1"]
        else:
            ref = np.median(np.vstack([th[c] for c in CELLS if c != "C2"]), axis=0)
        off = th["C2"] - ref
        th["C2"] = np.where(t >= t2, th["C2"] - (np.median(off[t >= t2]) - np.median(off[t < t2])), th["C2"])
    if not o.get("c4_trusted"):
        t4 = pd.Timestamp("2026-06-15")
        norm = {c: P[c] / np.maximum(spd[c] / 100.0, 1e-3) ** 3 / rho for c in CELLS}
        peer = np.median(np.vstack([norm[c] for c in CELLS if c != "C4"]), axis=0)
        with np.errstate(divide="ignore", invalid="ignore"):
            r4 = norm["C4"] / peer
        ok4 = spd["C4"] >= 60
        if o.get("c4_window"):
            k = pd.Timedelta(days=o["c4_window"])
            a, b = ok4 & (t >= t4) & (t < t4 + k), ok4 & (t < t4) & (t >= t4 - k)
        else:
            a, b = ok4 & (t >= t4), ok4 & (t < t4)
        P["C4"] = np.where(t >= t4, P["C4"] / (np.median(r4[a]) / np.median(r4[b])), P["C4"])
    if not o.get("flume_trusted"):
        tot = sum(q.values()) + B
        others = (q["C1"] + B) * tc["C1"] + sum(q[c] * tc[c] for c in CELLS if c not in ("C1", "C5"))
        with np.errstate(divide="ignore", invalid="ignore"):
            tc["C5"] = (tot * tc["C5"] - others) / q["C5"]
    if not o.get("no_unmix"):
        with np.errstate(divide="ignore", invalid="ignore"):
            tc["C1"] = ((q["C1"] + B) * tc["C1"] - B * th["C1"]) / q["C1"]
    out, end = {}, t.max()
    calm = d.wind_ms.values <= 4.5 if not o.get("no_wind_filter") else np.ones(len(d), bool)
    for c in CELLS:
        L = q[c] * S.RHO_W / 3600.0
        G = S.G_D * (np.maximum(P[c], 1e-6) / S.P_D) ** (1 / 3) * (rho / S.RHO_D) ** (2 / 3)
        until = pd.Timestamp("2099-01-01") if o.get("recirc_always") else pd.Timestamp("2026-06-24 15:00")
        wbi = wb + np.where((c == "C8") & west & (t < until) & (not o.get("no_recirc")), 2.0, 0.0)
        ok = (spd[c] >= 60) & calm & np.isfinite(tc[c]) & (q[c] > 0) & (th[c] > tc[c])
        if c == "C3" and not o.get("keep_old_fill"):
            ok &= t >= pd.Timestamp("2026-07-20 14:00")
        lg = L[ok] / G[ok]
        k = S.merkel(th[c][ok], tc[c][ok], lg, S.hsat(wbi[ok], p[ok]), p[ok], n=o.get("simpson", 40))
        C = pd.Series(k * lg ** S.N, index=t[ok])
        C = C[np.isfinite(C)]
        out[c] = 100.0 * endpoint(C, end, o.get("end", "trend")) / S.C_D
    return out


def misses(o=None):
    r = capability(o)
    return {c: round(float(r[c] - TRUE[c]), 1) for c in CELLS}


if __name__ == "__main__":
    print(misses())
