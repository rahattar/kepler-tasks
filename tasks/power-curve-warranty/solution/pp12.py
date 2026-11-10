"""PP-12 power performance verification of one farm-period package (reference program).

    python3 pp12.py PACKAGE_DIR OUT_CSV

Writes turbine, aep_ratio, warranty_claim for every turbine of the package. Each record is checked against the physics
and the farm's other records before it is used:
- each turbine's clock against M1 (whole-hour lag of best correlation of hourly wind speeds);
- M1's anemometer calibration from the mast service log; M1's barometer, replaced where it reads zero by the
  controllers' pressure feed scaled to the barometer over the periods both work;
- each turbine's yaw position against M1's vane (daily median difference; a step is located and corrected);
- the NTF's validity per turbine (a step in the daily nacelle/M1 ratio in the turbine's free sectors);
- the calibration turbine's nacelle anemometer against the other turbines (ratio constant, then linear from an onset;
  corrected), before the NTF is re-established from it and M1 in the calibration sector;
- SCADA power against the rated plateau (a step in the daily median at high wind is located and corrected).
Then PP-12 sections 4 to 6: data selection, normalised binned power curve, Rayleigh AEP ratio and claim."""
import csv, math, os, re, sys
import numpy as np
import pandas as pd

G0, R0, RW = 9.80665, 287.05, 461.5


# ---------------------------------------------------------------- package documents
def read_site(d, skip=frozenset()):
    txt = open(os.path.join(d, "site_description.md")).read()
    S = {}
    m = re.search(r"Verification period (\S+) 00:00 to (\S+ \S+) local standard time", txt)
    S["start"], S["end"] = pd.Timestamp(m.group(1)), pd.Timestamp(m.group(2))
    S["elev"] = float(re.search(r"Ground elevation at M1 ([\d.]+) m", txt).group(1))
    S["hub"] = float(re.search(r"Hub height ([\d.]+) m", txt).group(1))
    rows = re.findall(r"^\| (T\d+) \| (-?[\d.]+) \| (-?[\d.]+) \| (\S+) \| ([\d.]+) \| (-?[\d.]+) \|$", txt, re.M)
    S["turbines"] = [r[0] for r in rows]
    S["xy"] = {r[0]: (float(r[1]), float(r[2])) for r in rows}
    S["model"] = {r[0]: r[3] for r in rows}
    S["D"] = {r[0]: float(r[4]) for r in rows}
    S["north"] = {r[0]: float(r[5]) for r in rows}
    m = re.search(r"Ice detectors: ([^.]*)\.", txt)
    S["ice"] = [] if m.group(1).strip() == "none" else [x.strip() for x in m.group(1).split(",")]
    m = re.search(r"wind speed = ([\d.]+) m/s per Hz x frequency \+ ([\d.]+) m/s", txt)
    S["cert"] = [(pd.Timestamp("1900-01-01"), float(m.group(1)), float(m.group(2)))]
    m = re.search(r"Calibration turbine (T\d+), calibration sector (\d+) to (\d+) degrees", txt)
    S["cal"], S["sector"] = m.group(1), (float(m.group(2)), float(m.group(3)))
    S["ntf_old"] = np.array([(float(a), float(b)) for a, b in re.findall(r"^\| ([\d.]+) \| ([\d.]+) \|$", txt, re.M)])
    for r in csv.DictReader(open(os.path.join(d, "records", "mast_service_log.csv"))):
        m = re.search(r"wind speed = ([\d.]+) m/s per Hz x frequency \+ ([\d.]+) m/s", r["description"])
        if m and "cert" not in skip: S["cert"].append((pd.Timestamp(r["date_local"]), float(m.group(1)), float(m.group(2))))
    S["cert"].sort()
    S["sound"] = {}
    p = os.path.join(d, "noise_permit.md")
    if os.path.exists(p):
        t = open(p).read()
        m = re.search(r"Turbines (.+?) operate in sound mode \S+ from (\d+):00 to (\d+):00 local (?:standard )?time.*?limited to ([\d.]+) kW", t, re.S)
        for tb in re.findall(r"T\d+", m.group(1)): S["sound"][tb] = (int(m.group(2)), int(m.group(3)), float(m.group(4)))
    wc = pd.read_csv(os.path.join(d, "warranted_power_curves.csv"))
    S["curve"] = {c[:-3]: (wc["wind_speed_ms"].values, wc[c].values) for c in wc.columns if c.endswith("_kw")}
    S["curt"] = [(pd.Timestamp(r["start_local"]), pd.Timestamp(r["end_local"]))
                 for r in csv.DictReader(open(os.path.join(d, "records", "curtailment_log.csv")))]
    S["meter"] = pd.read_csv(os.path.join(d, "records", "monthly_meter_energy.csv"))
    # rotor upgrades: the turbine runs as the new model (warranted curve, rotor diameter) from then on
    S["rotor"] = {}
    for r in csv.DictReader(open(os.path.join(d, "records", "maintenance_log.csv"))):
        m = re.search(r"Rotor upgraded to the (\S+) blade set \(rotor diameter ([\d.]+) m\)", r["description"])
        if m and "rotor" not in skip:
            S["rotor"][r["turbine"]] = pd.Timestamp(r["date_local"])
            S["model"][r["turbine"]], S["D"][r["turbine"]] = m.group(1), float(m.group(2))
    return S


def changepoint(x, min_seg=5):
    """Best single split of a series into two constant means; returns (index, mean before, mean after, gain)."""
    x = np.asarray(x, float); n = len(x)
    if n < 2 * min_seg: return None
    c = np.cumsum(x); c2 = np.cumsum(x * x); tot = c2[-1] - c[-1] ** 2 / n
    best = None
    for k in range(min_seg, n - min_seg):
        a = c2[k - 1] - c[k - 1] ** 2 / k
        b = (c2[-1] - c2[k - 1]) - (c[-1] - c[k - 1]) ** 2 / (n - k)
        g = tot - a - b
        if best is None or g > best[3]: best = (k, c[k - 1] / k, (c[-1] - c[k - 1]) / (n - k), g)
    return best


def free_mask(S, t, direction):
    """True where the direction is outside every disturbed sector of t's neighbours (IEC 61400-12-1 Annex A)."""
    ok = np.ones(len(direction), bool)
    xt, yt = S["xy"][t]
    for o in S["turbines"]:
        if o == t: continue
        xo, yo = S["xy"][o]; L = math.hypot(xo - xt, yo - yt); Do = S["D"][o]
        if L > 20 * Do: continue
        brg = math.degrees(math.atan2(xo - xt, yo - yt)) % 360
        half = 0.5 * (1.3 * math.degrees(math.atan(2.5 * Do / L + 0.15)) + 10.0)
        ok &= np.abs((direction - brg + 180) % 360 - 180) > half
    return ok


def best_lag(a, b, lags=range(-14, 15)):
    """Hours h for which b(t + h) best matches a(t) (hourly series, correlation)."""
    best = (0, -2.0)
    for h in lags:
        j = a.align(b.shift(-h, freq="h"), join="inner")
        ok = np.isfinite(j[0].values) & np.isfinite(j[1].values)
        c = np.corrcoef(j[0].values[ok], j[1].values[ok])[0, 1] if ok.sum() > 48 else -2.0
        if c > best[1]: best = (h, c)
    return best[0]


def mast_clock(S, m, raw):
    """M1's clock against the turbines: a lag that every turbine shares, week by week, is M1's, when the turbines
    agree with the grid operator's curtailment log (local standard time). M1's records are moved back by it."""
    fleet = pd.concat([raw[t]["nacelle_ws_ms"].resample("1h").mean() for t in S["turbines"]], axis=1).median(axis=1)
    mh = m["ws_hub_hz"].resample("1h").mean()
    weeks = pd.date_range(S["start"], S["end"], freq="7D")
    lags = [best_lag(fleet[(fleet.index >= w) & (fleet.index < w + pd.Timedelta("7D"))], mh) for w in weeks]
    if not any(lags):
        return m
    # the turbines' clocks against the curtailment log: status 5 inside the logged windows
    st5 = pd.concat([(raw[t]["status"] == 5).astype(float) for t in S["turbines"]], axis=1).mean(axis=1)
    inlog = np.zeros(len(st5), bool)
    for a, b in S["curt"]: inlog |= (st5.index >= a) & (st5.index < b)
    if st5[inlog].mean() < 0.5:          # the turbines' stamps are not the log's time: leave M1 as reference
        return m
    shift = pd.Series(0.0, index=m.index)
    for i, h in enumerate(lags):
        if h == 0: continue
        w0 = weeks[i]
        # the step: the first stamp after a gap of about h hours in M1's records, in this week or the one before
        idx = m.index[(m.index >= w0 - pd.Timedelta("7D")) & (m.index < w0 + pd.Timedelta("7D"))]
        gaps = np.diff(idx.values) / np.timedelta64(1, "h")
        j = np.nonzero(np.abs(gaps - h) < 0.5)[0]
        t0 = idx[j[0] + 1] if len(j) and (i == 0 or lags[i - 1] != h) else w0
        shift[(m.index >= t0) & (shift == 0)] = h
    out = m.copy()
    out.index = m.index - pd.to_timedelta(shift.values, unit="h")
    return out[~out.index.duplicated()]


def vane_check(S, sc, mwd, day, index):
    """A step in yaw minus vane that every turbine shows at once is M1's vane's: M1's direction is corrected by it."""
    D = {}
    for t in S["turbines"]:
        yaw = sc[t]["yaw_position_deg"].values.astype(float) + S["north"][t]
        D[t] = pd.Series(((yaw - mwd + 180) % 360) - 180).groupby(day.values).median()
    cons = pd.DataFrame(D).median(axis=1).dropna()
    cp = changepoint(cons.values, 3)
    if cp is None or abs(cp[2] - cp[1]) < 5.0:
        return mwd
    t_cp = cons.index[cp[0]]
    diff = pd.DataFrame({t: ((sc[t]["yaw_position_deg"].values.astype(float) + S["north"][t] - mwd + 180) % 360) - 180
                         for t in S["turbines"]}).median(axis=1).values
    win = (index >= t_cp - pd.Timedelta("1D")) & (index < t_cp + pd.Timedelta("1D"))
    sub = diff[win]; best = None
    for i in range(6, len(sub) - 6):
        g = -(np.nanvar(sub[:i]) * i + np.nanvar(sub[i:]) * (len(sub) - i))
        if best is None or g > best[1]: best = (i, g)
    t_split = index[win][best[0]]
    step = (cp[2] - cp[1])
    return np.where(index >= t_split, mwd + step, mwd) % 360


def assess(d, skip=frozenset()):
    """Annual energy ratio and claim per turbine. `skip` names checks to leave out (for authoring/evidence/route_study.py
    only): clock, mastclock, pressure, yaw, vane, ntf, ntfcheck, drift, scale, cert, rotor."""
    S = read_site(d, skip)
    grid = pd.date_range(S["start"], S["end"], freq="10min")
    m = pd.read_csv(os.path.join(d, "mast", "m1_10min.csv"), parse_dates=["timestamp"]).set_index("timestamp")
    raw = {t: pd.read_csv(os.path.join(d, "scada", "turbine_%s.csv" % t), parse_dates=["timestamp"]).set_index("timestamp")
           for t in S["turbines"]}
    if "mastclock" not in skip:
        m = mast_clock(S, m, raw)
    m = m.reindex(grid)
    ws = np.full(len(m), np.nan)
    for i, (t0, a, b) in enumerate(S["cert"]):
        t1 = S["cert"][i + 1][0] if i + 1 < len(S["cert"]) else pd.Timestamp("2100-01-01")
        sel = (m.index >= t0) & (m.index < t1)
        ws[sel] = a * m["ws_hub_hz"].values[sel] + b
    m["ws"] = ws
    Tk = m["temp_hub_c"].values + 273.15
    # turbines: clock check first (the pressure feed and everything else is aligned after it)
    sc = {}
    mh = m["ws"].resample("1h").mean()
    for t in S["turbines"]:
        s = raw[t]
        lag = best_lag(mh, s["nacelle_ws_ms"].resample("1h").mean())   # the turbine's records are lag hours late
        if lag != 0 and "clock" not in skip:
            s.index = s.index - pd.Timedelta(hours=lag)
        sc[t] = s.reindex(m.index)
    # pressure: M1 barometer where it works; elsewhere the controllers' feed, scaled to the barometer on the overlap
    pb = m["pressure_2m_hpa"].values.astype(float)
    feed = sc[S["turbines"][0]]["ambient_pressure_hpa"].values
    good = (pb > 500) & np.isfinite(feed)
    if "pressure" in skip:
        k = 1.0
    elif good.sum() > 1000:
        k = np.median(pb[good] / feed[good])
    else:
        k = np.exp(-S["elev"] * G0 / (R0 * np.nanmean(Tk)))
    p2 = np.where(pb > 500, pb, k * feed)
    p_hub = p2 * np.exp(-(S["hub"] - 2.0) * G0 / (R0 * Tk))
    phi = m["rh_hub_pct"].values / 100.0
    Pw = 0.0000205 * np.exp(0.0631846 * Tk)
    rho = (1.0 / Tk) * (p_hub * 100.0 / R0 - phi * Pw * (1 / R0 - 1 / RW))
    icing = (m["temp_hub_c"].values < 2.0) & (m["rh_hub_pct"].values > 85.0)
    curt = np.zeros(len(m), bool)
    for a, b in S["curt"]: curt |= (m.index >= a) & (m.index < b)
    hours = m.index.hour.values
    mwd = m["wd_hub_deg"].values; mws = m["ws"].values
    day = m.index.floor("D")
    res = {}
    # per-turbine corrections: yaw offset segments, power scale segments, NTF validity
    info = {}
    if "vane" not in skip:
        mwd = vane_check(S, sc, mwd, day, m.index)
    for t in S["turbines"]:
        s = sc[t]
        st = s["status"].values
        yaw = s["yaw_position_deg"].values.astype(float) + S["north"][t]
        # yaw against M1's vane (daily circular median of the difference)
        diff = ((yaw - mwd + 180) % 360) - 180
        dd = pd.Series(diff).groupby(day.values).median()
        cp = changepoint(dd.values, 3)
        corr = np.zeros(len(m))
        if "yaw" in skip: cp = None
        if cp is not None and abs(cp[2] - cp[1]) > 5.0:
            t_cp = dd.index[cp[0]]
            win = (m.index >= t_cp - pd.Timedelta("1D")) & (m.index < t_cp + pd.Timedelta("1D"))
            sub = diff[win]; best = None
            for i in range(6, len(sub) - 6):
                g = np.nanvar(sub) * len(sub) - np.nanvar(sub[:i]) * i - np.nanvar(sub[i:]) * (len(sub) - i)
                if best is None or g > best[1]: best = (i, g)
            t_split = m.index[win][best[0]]
            corr = np.where(m.index >= t_split, -cp[2], -cp[1])
        elif cp is not None and abs(np.median(dd.values)) > 5.0:
            corr = np.full(len(m), -np.median(dd.values))
        direc = (yaw + corr) % 360
        info[t] = dict(direc=direc, free=free_mask(S, t, direc))
    # NTF: old table, then the step in each turbine's nacelle/M1 ratio in its free sectors
    a_old = np.polyfit(S["ntf_old"][:, 0], S["ntf_old"][:, 1], 1)
    ratio_d = {}
    for t in S["turbines"]:
        s = sc[t]
        sel = (s["status"].values == 0) & info[t]["free"] & (mws > 4) & (mws < 16) & ~icing
        x_all = s["nacelle_ws_ms"].values / mws
        r = pd.Series(np.where(sel, x_all, np.nan)).groupby(day.values).median()
        ratio_d[t] = r
        rv = r.dropna()
        cp = changepoint(rv.values, 3)
        info[t]["fw"] = None
        if cp is None or "ntf" in skip: continue
        k = cp[0]
        before, after = rv.values[max(0, k - 3):k], rv.values[k:k + 3]
        if abs(np.median(after) / np.median(before) - 1) < 0.04: continue
        d_a, d_b = rv.index[k - 1], rv.index[k]
        win = (m.index >= d_a) & (m.index < d_b + pd.Timedelta("1D")) & sel
        x = x_all[win]; idx = m.index[win]; best = None
        for i in range(1, len(x)):
            g = -(np.var(x[:i]) * i + np.var(x[i:]) * (len(x) - i))
            if best is None or g > best[1]: best = (i, g)
        info[t]["fw"] = idx[best[0]] if best is not None else d_b
    # the commissioning NTF verified at the calibration turbine in the calibration sector before any change: if it
    # does not give M1's wind speed there, it does not apply to the configuration in the period at all
    cal = S["cal"]
    if "ntfcheck" not in skip:
        lo, hi = S["sector"]
        pre = (m.index < info[cal]["fw"]) if info[cal]["fw"] is not None else np.ones(len(m), bool)
        k = pre & (mwd >= lo) & (mwd <= hi) & (sc[cal]["status"].values == 0) & ~icing & (mws > 5) & (mws < 12)
        v = np.interp(sc[cal]["nacelle_ws_ms"].values[k], S["ntf_old"][:, 0], S["ntf_old"][:, 1]) / mws[k]
        if k.sum() > 200 and abs(np.median(v) - 1) > 0.03:
            for t in S["turbines"]:
                info[t]["fw"] = S["start"]
    # calibration turbine drift against the other turbines, on days when every turbine is in one NTF state
    others = [t for t in S["turbines"] if t != cal]
    fws = [info[t]["fw"] for t in S["turbines"] if info[t]["fw"] is not None]
    fleet = pd.concat([ratio_d[t] for t in others], axis=1).median(axis=1)
    rel = (ratio_d[cal] / fleet)
    if fws:
        lo_fw, hi_fw = min(fws).floor("D"), max(fws).floor("D")
        rel[(rel.index >= lo_fw) & (rel.index <= hi_fw)] = np.nan
    rel = rel.dropna()
    # hinge: constant, then a linear change from an onset day to the end of the period
    dn = (rel.index - rel.index[0]).days.values.astype(float); y = rel.values
    best = (np.sum((y - np.median(y)) ** 2), None, np.median(y), 0.0)
    for j in range(5, len(y) - 5):
        t0 = dn[j]; X = np.c_[np.ones(len(y)), np.maximum(0, dn - t0)]
        cf, *_ = np.linalg.lstsq(X, y, rcond=None); e = np.sum((y - X @ cf) ** 2)
        if e < best[0]: best = (e, t0, cf[0], cf[1])
    dd = (day - rel.index[0]).days.values.astype(float)
    drift_f = np.ones(len(m))
    if "drift" not in skip and best[1] is not None and abs(best[3] * (dn[-1] - best[1])) > 0.01 * best[2]:
        drift_f = 1 + best[3] * np.maximum(0, dd - best[1]) / best[2]
    sc_cal_nac = sc[cal]["nacelle_ws_ms"].values / drift_f
    # re-established NTF from the calibration turbine (drift-corrected) and M1 in the calibration sector
    ntf_new = None
    if info[cal]["fw"] is not None:
        lo, hi = S["sector"]
        sel = (m.index >= info[cal]["fw"]) & (mwd >= lo) & (mwd <= hi) & (sc[cal]["status"].values == 0) & ~icing & (mws > 3) & (mws < 18)
        ntf_new = np.polyfit(sc_cal_nac[sel], mws[sel], 1)
    for t in S["turbines"]:
        s = sc[t]
        nac = sc_cal_nac if t == cal else s["nacelle_ws_ms"].values
        post = (m.index >= info[t]["fw"]) if info[t]["fw"] is not None else np.zeros(len(m), bool)
        free_ws = np.where(post & (ntf_new is not None), np.polyval(ntf_new, nac) if ntf_new is not None else nac,
                           np.interp(nac, S["ntf_old"][:, 0], S["ntf_old"][:, 1], left=np.nan, right=np.nan))
        lo_tab = S["ntf_old"][:, 0].min(); hi_tab = S["ntf_old"][:, 0].max()
        free_ws = np.where(~post & (nac < lo_tab), np.polyval(a_old, nac), free_ws)
        free_ws = np.where(~post & (nac > hi_tab), np.polyval(a_old, nac), free_ws)
        P = s["power_kw"].values.astype(float)
        rated = float(np.max(S["curve"][S["model"][t]][1]))
        # power scale: daily rated plateau
        st = s["status"].values
        hi_w = (st == 0) & (free_ws > 14.0) & ~curt & ~icing
        if t in S["sound"]:
            h0, h1, lim = S["sound"][t]; night = (hours >= h0) | (hours < h1)
            hi_w &= ~night
        pl = pd.Series(np.where(hi_w, P / rated, np.nan)).groupby(day.values).median().dropna()
        scale = np.ones(len(m))
        cp = changepoint(pl.values, 3) if len(pl) >= 8 and "scale" not in skip else None
        if cp is not None and abs(cp[2] - cp[1]) > 0.02:
            t_cp = pl.index[cp[0]]
            scale = np.where(m.index >= t_cp, 1.0 / cp[2] if cp[2] < 0.99 else 1.0, 1.0 / cp[1] if cp[1] < 0.99 else 1.0)
        elif len(pl) and pl.median() < 0.98 and "scale" not in skip:
            scale = np.full(len(m), 1.0 / pl.median())
        P = P * scale
        valid = (st == 0) & ~curt & ~icing & info[t]["free"] & np.isfinite(free_ws) & np.isfinite(rho)
        if t in S["ice"] and "ice_alarm" in s:
            valid &= s["ice_alarm"].values != 1
        if t in S["sound"]:
            h0, h1, lim = S["sound"][t]
            valid &= ~((hours >= h0) | (hours < h1))
        if t in S["rotor"]:
            valid &= m.index >= S["rotor"][t]
        vn = free_ws * (rho / 1.225) ** (1 / 3)
        vn, Pv = vn[valid], P[valid]
        b = np.round(vn / 0.5) * 0.5
        vb, pb_ = [], []
        for c in np.arange(3.0, 25.01, 0.5):
            kk = b == c
            if kk.sum() >= 3: vb.append(vn[kk].mean()); pb_.append(Pv[kk].mean())
        grid = np.arange(3.0, 25.01, 0.5)
        meas = np.interp(grid, vb, pb_)
        v0, p0 = S["curve"][S["model"][t]]
        Fr = lambda x: 1.0 - np.exp(-math.pi / 4.0 * (x / 7.5) ** 2)
        aep = lambda v, p: float(np.sum((Fr(v[1:]) - Fr(v[:-1])) * 0.5 * (p[1:] + p[:-1])))
        r = aep(grid, meas) / aep(np.asarray(v0, float), np.asarray(p0, float))
        res[t] = (r, "yes" if r < 0.97 else "no")
    return res


def main(pkg, out):
    res = assess(pkg)
    with open(out, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["turbine", "aep_ratio", "warranty_claim"])
        for t in sorted(res): w.writerow([t, "%.4f" % res[t][0], res[t][1]])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
