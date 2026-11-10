"""Second, independent PP-12 program (method-spread evidence); shares no code with solution/pp12.py.

    python3 authoring/evidence/independent.py PACKAGE_DIR OUT_CSV

Differs from pp12.py wherever PP-12 leaves the method open: clock offset from 10-minute correlation; barometer
outage replaced by the controllers' sea-level pressure reduced to M1's elevation with the barometric formula;
NTF validity from each turbine's nacelle/M1 ratio against its own first weeks; re-established NTF as a binned table
(0.5 m/s nacelle bins) rather than a straight line; calibration-turbine drift fitted against M1 (not the fleet);
wrong-yaw periods left out rather than corrected; SCADA power scale corrected with the revenue meters; M1's clock
by majority vote of the turbines per 14-day block; M1's vane by the fleet's daily offsets against its first week;
the commissioning NTF checked against M1 over each turbine's first ten days."""
import csv, math, os, re, sys
import numpy as np
import pandas as pd

G, R0, RW = 9.80665, 287.05, 461.5


def doc(d, f):
    return open(os.path.join(d, f)).read()


def site(d):
    t = doc(d, "site_description.md")
    s = dict(
        start=pd.Timestamp(re.search(r"period (\S+) 00:00", t).group(1)),
        elev=float(re.search(r"elevation at M1 ([\d.]+)", t).group(1)),
        hub=float(re.search(r"Hub height ([\d.]+)", t).group(1)))
    tb = re.findall(r"^\| (T\d+) \| (-?[\d.]+) \| (-?[\d.]+) \| (\S+) \| ([\d.]+) \| (-?[\d.]+) \|$", t, re.M)
    s["T"] = {r[0]: dict(x=float(r[1]), y=float(r[2]), model=r[3], D=float(r[4]), north=float(r[5])) for r in tb}
    ice = re.search(r"Ice detectors: ([^.]*)\.", t).group(1)
    s["ice"] = set(re.findall(r"T\d+", ice))
    c = re.search(r"Calibration turbine (T\d+), calibration sector (\d+) to (\d+)", t)
    s["cal"], s["sec"] = c.group(1), (float(c.group(2)), float(c.group(3)))
    s["ntf"] = np.array(re.findall(r"^\| ([\d.]+) \| ([\d.]+) \|$", t, re.M), float)
    certs = [(pd.Timestamp("1900-01-01"),) + tuple(map(float, re.search(r"= ([\d.]+) m/s per Hz x frequency \+ ([\d.]+)", t).groups()))]
    for r in csv.DictReader(open(os.path.join(d, "records", "mast_service_log.csv"))):
        g = re.search(r"= ([\d.]+) m/s per Hz x frequency \+ ([\d.]+)", r["description"])
        if g: certs.append((pd.Timestamp(r["date_local"]),) + tuple(map(float, g.groups())))
    s["certs"] = sorted(certs)
    s["sound"] = {}
    if os.path.exists(os.path.join(d, "noise_permit.md")):
        n = doc(d, "noise_permit.md")
        g = re.search(r"Turbines (.*?) operate in sound mode \S+ from (\d+):00 to (\d+):00", n, re.S)
        for x in re.findall(r"T\d+", g.group(1)): s["sound"][x] = (int(g.group(2)), int(g.group(3)))
    w = pd.read_csv(os.path.join(d, "warranted_power_curves.csv"))
    s["wc"] = {c[:-3]: w[c].values for c in w.columns if c != "wind_speed_ms"}
    s["wv"] = w["wind_speed_ms"].values
    s["curt"] = pd.read_csv(os.path.join(d, "records", "curtailment_log.csv"), parse_dates=["start_local", "end_local"])
    s["meter"] = pd.read_csv(os.path.join(d, "records", "monthly_meter_energy.csv")).set_index("month")
    s["since"] = {}
    for r in csv.DictReader(open(os.path.join(d, "records", "maintenance_log.csv"))):
        g = re.search(r"Rotor upgraded to the (\S+) blade set \(rotor diameter ([\d.]+) m\)", r["description"])
        if g:   # the turbine is the new model from then on; its earlier periods are another configuration
            s["T"][r["turbine"]].update(model=g.group(1), D=float(g.group(2)))
            s["since"][r["turbine"]] = pd.Timestamp(r["date_local"])
    return s


def disturbed(s, t, wd):
    """Annex A: True where t's direction lies in a neighbour's disturbed sector."""
    out = np.zeros(len(wd), bool); a = s["T"][t]
    for o, b in s["T"].items():
        if o == t: continue
        L = math.hypot(b["x"] - a["x"], b["y"] - a["y"])
        if L > 20 * b["D"]: continue
        c = math.degrees(math.atan2(b["x"] - a["x"], b["y"] - a["y"])) % 360
        w = 1.3 * math.degrees(math.atan(2.5 * b["D"] / L + 0.15)) + 10
        out |= np.abs((wd - c + 540) % 360 - 180) <= w / 2
    return out


def step_time(x, idx, lo, hi):
    """Split time (10-minute resolution) of a level step in x between days lo and hi."""
    k = (idx >= lo) & (idx < hi + pd.Timedelta("1D")) & np.isfinite(x)
    v, ti = x[k], idx[k]
    if len(v) < 2: return hi
    e = [np.var(v[:i]) * i + np.var(v[i:]) * (len(v) - i) for i in range(1, len(v))]
    return ti[int(np.argmin(e)) + 1]


def m_clock(s, m, raw):
    """M1's clock: per 14-day block, the whole-hour lag of best 10-minute correlation of M1's wind with each turbine's
    nacelle wind. A lag shared by most turbines in a block, while the turbines' status agrees with the curtailment log,
    is M1's; M1's records from the gap in its stamps where it starts are moved back by it."""
    hz = m["ws_hub_hz"]
    start = m.index[0].normalize()
    blocks = pd.date_range(start, m.index[-1], freq="14D")
    st5 = pd.concat([(raw[t]["status"] == 5) for t in raw], axis=1).mean(axis=1)
    inlog = np.zeros(len(st5), bool)
    for _, r in s["curt"].iterrows(): inlog |= (st5.index >= r["start_local"]) & (st5.index < r["end_local"])
    if len(st5[inlog]) and st5[inlog].mean() < 0.5:
        return m
    lag_b = []
    for b0 in blocks:
        k = (hz.index >= b0) & (hz.index < b0 + pd.Timedelta("14D")); hb = hz[k]
        votes = []
        for t in raw:
            y = raw[t]["nacelle_ws_ms"]; best, lag = -9, 0
            for h in range(-14, 15):
                v = y.reindex(hb.index - pd.Timedelta(hours=h)).values; ok = np.isfinite(v)
                if ok.sum() < 200: continue
                c = np.corrcoef(v[ok], hb.values[ok])[0, 1]
                if c > best: best, lag = c, h
            votes.append(lag)
        v, cnt = np.unique(votes, return_counts=True)
        lag_b.append(int(v[np.argmax(cnt)]) if cnt.max() >= 2 * len(votes) / 3 else 0)
    if not any(lag_b):
        return m
    shift = np.zeros(len(m))
    for i, h in enumerate(lag_b):
        if h == 0 or (i and lag_b[i - 1] == h): continue
        w = m.index[(m.index >= blocks[i] - pd.Timedelta("14D")) & (m.index < blocks[i] + pd.Timedelta("14D"))]
        gap = np.nonzero(np.abs(np.diff(w.values) / np.timedelta64(1, "h") - h) < 0.5)[0]
        at = w[gap[0] + 1] if len(gap) else blocks[i]
        shift[m.index >= at] = h
    out = m.copy(); out.index = m.index - pd.to_timedelta(shift, unit="h")
    return out[~out.index.duplicated()].sort_index()


def assess(d):
    s = site(d)
    m = pd.read_csv(os.path.join(d, "mast", "m1_10min.csv"), parse_dates=["timestamp"]).set_index("timestamp")
    raw = {t: pd.read_csv(os.path.join(d, "scada", "turbine_%s.csv" % t), parse_dates=["timestamp"]).set_index("timestamp")
           for t in s["T"]}
    m = m_clock(s, m, raw)
    idx = m.index; n = len(m)
    v1 = np.zeros(n)
    for i, (t0, a, b) in enumerate(s["certs"]):
        k = idx >= t0
        v1[k] = a * m["ws_hub_hz"].values[k] + b
    wd1 = m["wd_hub_deg"].values; Tc = m["temp_hub_c"].values; Tk = Tc + 273.15; rh = m["rh_hub_pct"].values
    ice = (Tc < 2) & (rh > 85)
    curt = np.zeros(n, bool)
    for _, r in s["curt"].iterrows(): curt |= (idx >= r["start_local"]) & (idx < r["end_local"])
    days = idx.normalize()
    # turbine records, clock-aligned to M1 by the whole-hour lag of best 10-minute correlation
    sc = {}
    for t in s["T"]:
        x = raw[t]
        best, lag = -9, 0
        for h in range(-14, 15):
            y = x["nacelle_ws_ms"].reindex(idx + pd.Timedelta(hours=h)).values
            ok = np.isfinite(y)
            c = np.corrcoef(y[ok], v1[ok])[0, 1]
            if c > best: best, lag = c, h
        sc[t] = x.reindex(idx + pd.Timedelta(hours=lag)).set_axis(idx)
    # density: barometer, or where it is out the controllers' sea-level pressure reduced to M1's elevation
    pb = m["pressure_2m_hpa"].values.astype(float)
    q = np.nanmedian(np.c_[[sc[t]["ambient_pressure_hpa"].values for t in s["T"]]], axis=0)
    p2 = np.where(pb > 500, pb, q * np.exp(-(s["elev"] + 2.0) * G / (R0 * Tk)))
    B = p2 * 100 * np.exp(-(s["hub"] - 2) * G / (R0 * Tk))
    Pw = 0.0000205 * np.exp(0.0631846 * Tk)
    rho = (B / R0 - rh / 100 * Pw * (1 / R0 - 1 / RW)) / Tk
    ntf_v, ntf_u = s["ntf"][:, 0], s["ntf"][:, 1]
    def old(v):
        a, b = np.polyfit(ntf_v, ntf_u, 1)
        return np.where((v >= ntf_v[0]) & (v <= ntf_v[-1]), np.interp(v, ntf_v, ntf_u), a * v + b)
    # M1's vane: when most turbines' daily yaw-minus-vane offsets move together by more than 10 degrees, the vane moved
    offs = pd.DataFrame({t: pd.Series((((sc[t]["yaw_position_deg"].values + a["north"]) % 360) - wd1 + 540) % 360 - 180)
                         .groupby(days).median() for t, a in s["T"].items()})
    fl = offs.median(axis=1).dropna()
    base = fl.iloc[:7].median()
    for i in range(len(fl) - 5):
        if np.all(np.abs(fl.iloc[i:i + 5].values - base) > 10):
            jump = fl.iloc[i:i + 15].median() - base
            ten = pd.DataFrame({t: (((sc[t]["yaw_position_deg"].values + a["north"]) % 360) - wd1 + 540) % 360 - 180
                                for t, a in s["T"].items()}).median(axis=1).values
            at = step_time(ten, idx, fl.index[i - 1] if i else fl.index[0], fl.index[i])
            wd1 = np.where(idx >= at, wd1 + jump, wd1) % 360
            break
    # per turbine: direction (wrong-yaw days left out), NTF state change
    T = {}
    for t, a in s["T"].items():
        x = sc[t]
        wd = (x["yaw_position_deg"].values + a["north"]) % 360
        off = pd.Series((wd - wd1 + 540) % 360 - 180).groupby(days).median()
        bad_yaw = np.abs(off.reindex(days).values) > 10
        free = ~disturbed(s, t, wd) & ~bad_yaw
        run = (x["status"].values == 0) & ~ice & np.isfinite(v1)
        r = np.where(run & free & (v1 > 4) & (v1 < 16), old(x["nacelle_ws_ms"].values) / v1, np.nan)
        dr = pd.Series(r).groupby(days).median().dropna()
        lvl = dr.iloc[:10].median(); change = None
        if abs(lvl - 1) > 0.03:     # the commissioning NTF does not give M1's wind from the start of the period
            change = idx[0]
        for i in range(len(dr) - 5 if change is None else 0):
            if np.all(np.abs(dr.iloc[i:i + 5].values / lvl - 1) > 0.03):
                change = step_time(r, idx, dr.index[i - 1] if i else dr.index[0], dr.index[i]); break
        T[t] = dict(x=x, wd=wd, free=free, run=run, r=r, change=change)
    # calibration turbine: its nacelle wind against M1 in its free sectors, in log, is a level per NTF state plus a
    # drift that is zero up to an onset and linear after it (joint fit over both states); the nacelle record is
    # corrected for the fitted drift (M1 fixes the right value)
    cal = s["cal"]; c = T[cal]
    nac_c = c["x"]["nacelle_ws_ms"].values.astype(float)
    post_c = (idx >= c["change"]) if c["change"] is not None else np.zeros(n, bool)
    q = np.where(post_c, nac_c, old(nac_c)) / v1
    keep = c["run"] & c["free"] & (v1 > 4) & (v1 < 16)
    if c["change"] is not None:
        keep &= np.abs((idx - c["change"]) / pd.Timedelta("1D")) > 1
    g = pd.DataFrame(dict(q=np.where(keep, q, np.nan), post=post_c.astype(float))).groupby(days).median().dropna()
    y = np.log(g.q.values); pst = g.post.values; td = (g.index - g.index[0]).days.values.astype(float)
    X0 = np.c_[np.ones(len(y)), pst]
    sse0 = np.sum((y - X0 @ np.linalg.lstsq(X0, y, rcond=None)[0]) ** 2)
    best = (sse0, None, 0.0)
    for j in range(3, len(y) - 10):
        X = np.c_[X0, np.maximum(0, td - td[j])]
        cf = np.linalg.lstsq(X, y, rcond=None)[0]; e = np.sum((y - X @ cf) ** 2)
        if e < best[0]: best = (e, td[j], cf[2])
    tdi = (days - g.index[0]).days.values.astype(float)
    fac = np.ones(n)
    if best[1] is not None and best[0] < 0.6 * sse0 and abs(best[2]) * (td[-1] - best[1]) > 0.01:
        fac = np.exp(best[2] * np.maximum(0, tdi - best[1]))
    T[cal]["x"] = c["x"].assign(nacelle_ws_ms=nac_c / fac); c = T[cal]
    # re-established NTF: binned table from the calibration turbine and M1 in the calibration sector
    new = None
    if c["change"] is not None:
        lo, hi = s["sec"]
        k = (idx >= c["change"]) & c["run"] & (wd1 >= lo) & (wd1 <= hi)
        vn_, u_ = c["x"]["nacelle_ws_ms"].values[k], v1[k]
        b = np.round(vn_ / 0.5) * 0.5
        tab = pd.DataFrame(dict(b=b, v=vn_, u=u_)).groupby("b").agg(v=("v", "mean"), u=("u", "mean"), n=("u", "size"))
        tab = tab[tab.n >= 3]
        new = (tab.v.values, tab.u.values)
    def newf(v):
        a, b = np.polyfit(new[0], new[1], 1)
        return np.where((v >= new[0][0]) & (v <= new[0][-1]), np.interp(v, *new), a * v + b)
    res = {}
    for t, a in s["T"].items():
        e = T[t]; x = e["x"]
        nv = x["nacelle_ws_ms"].values
        post = (idx >= e["change"]) if e["change"] is not None else np.zeros(n, bool)
        u = np.where(post, newf(nv) if new is not None else np.nan, old(nv))
        P = x["power_kw"].values.astype(float)
        # power scale: SCADA energy against the revenue meter per month; a month off the farm's typical ratio
        # marks a scale error, located to the day from the rated plateau and corrected by the meters
        mon = idx.strftime("%Y-%m")
        se = pd.Series(np.where(np.isfinite(P), P, 0) / 6.0).groupby(mon).sum()
        fleet = pd.concat([pd.Series(np.where(np.isfinite(T[o]["x"]["power_kw"].values), T[o]["x"]["power_kw"].values, 0) / 6.0).groupby(mon).sum()
                           / s["meter"][o] for o in s["T"]], axis=1).median(axis=1)
        rat = (se / s["meter"][t]) / fleet
        corr = np.ones(n)
        if (np.abs(rat - 1) > 0.02).any():
            rated = s["wc"][a["model"]].max()
            hiw = e["run"] & (u > 14) & ~curt
            if t in s["sound"]:
                h0, h1 = s["sound"][t]; hiw &= ~((idx.hour >= h0) | (idx.hour < h1))
            # the step lies in the first month off the farm's ratio; locate it to the day from the rated plateau
            m0 = pd.Timestamp(rat.index[int(np.argmax(np.abs(rat.values - 1) > 0.02))] + "-01")
            pl = pd.Series(np.where(hiw, P / rated, np.nan)).groupby(days).median().dropna()
            pl = pl[(pl.index >= m0 - pd.Timedelta("3D")) & (pl.index < m0 + pd.offsets.MonthBegin(1) + pd.Timedelta("3D"))]
            sse = [np.var(pl.values[:i]) * i + np.var(pl.values[i:]) * (len(pl) - i) for i in range(1, len(pl))]
            j = int(np.argmin(sse)) + 1
            st = step_time(np.where(hiw, P, np.nan), idx, pl.index[j - 1], pl.index[j])
            after = [mm for mm in rat.index if pd.Timestamp(mm + "-01") >= st.normalize() + pd.offsets.MonthBegin(0)]
            before = [mm for mm in rat.index if pd.Timestamp(mm + "-01") + pd.offsets.MonthEnd(0) < st]
            fa = rat[after].median() if after else np.nan; fb = rat[before].median() if before else 1.0
            corr = np.where(idx >= st, 1 / fa if np.isfinite(fa) else 1.0, 1 / fb)
        P = P * corr
        ok = e["run"] & e["free"] & ~curt & np.isfinite(u) & np.isfinite(P)
        if t in s["ice"] and "ice_alarm" in x: ok &= x["ice_alarm"].values != 1
        if t in s["sound"]:
            h0, h1 = s["sound"][t]; ok &= ~((idx.hour >= h0) | (idx.hour < h1))
        if t in s["since"]:
            ok &= idx >= s["since"][t]
        vn = u[ok] * (rho[ok] / 1.225) ** (1 / 3); pk = P[ok]
        b = np.round(vn / 0.5) * 0.5
        df = pd.DataFrame(dict(b=b, v=vn, p=pk)).groupby("b").agg(v=("v", "mean"), p=("p", "mean"), k=("p", "size"))
        df = df[(df.k >= 3) & (df.index >= 3.0) & (df.index <= 25.0)]
        g = np.arange(3.0, 25.001, 0.5)
        pm = np.interp(g, df.v.values, df.p.values)
        F = 1 - np.exp(-math.pi / 4 * (g / 7.5) ** 2); dF = np.diff(F)
        aep = lambda p: np.sum(dF * (p[1:] + p[:-1]) / 2)
        ratio = aep(pm) / aep(np.interp(g, s["wv"], s["wc"][a["model"]]))
        res[t] = (float(ratio), "yes" if ratio < 0.97 else "no")
    return res


if __name__ == "__main__":
    r = assess(sys.argv[1])
    with open(sys.argv[2], "w", newline="") as f:
        w = csv.writer(f); w.writerow(["turbine", "aep_ratio", "warranty_claim"])
        for t in sorted(r): w.writerow([t, "%.4f" % r[t][0], r[t][1]])
