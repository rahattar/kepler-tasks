"""A second audit program, written apart from solution/audit.py and sharing no code with it.

    python3 independent_audit.py AUDIT_DIR OUT_JSON

Differences in method:
- pandas time series throughout;
- one-CT logs found from the 99th percentile of running power against the table's largest power;
- the pressure logger's clock offset from an FFT cross-correlation (scipy.signal.correlate) of the pressure change
  with the supply less its 5-minute rolling median;
- each interval's loaded share from the unloaded power expected at that time since the machine last left full load
  (60 % falling to 25 % with a 25 s time constant), or from zero after a stop;
- variable-speed delivery by linear interpolation of the table inverted.
"""
import json
import math
import sys

import numpy as np
import pandas as pd
from scipy.signal import correlate

STEP = 10.0


def load(path):
    df = pd.read_csv(path)
    t = pd.to_datetime(df["time"], format="%Y-%m-%d %H:%M:%S")
    return pd.Series(df.iloc[:, 1].astype(float).values, index=t)


def main(src, dst):
    cfg = json.load(open(f"{src}/site.json"))
    pa = cfg["atmospheric_pressure_bar_a"]
    vol = cfg["storage_volume_m3"]
    drop = cfg["pressure_drop_receiver_to_compressors_bar"]
    press = load(f"{src}/{cfg['pressure_logger']}")
    pw = {c["tag"]: load(f"{src}/{c['logger']}") for c in cfg["compressors"]}
    idx = next(iter(pw.values())).index
    secs = ((idx - idx[0]) / pd.Timedelta(seconds=1)).values
    psecs = ((press.index - idx[0]) / pd.Timedelta(seconds=1)).values

    def flows(p_at_ends):
        sup = np.zeros(len(idx))
        tot = np.zeros(len(idx))
        for c in cfg["compressors"]:
            kw = pw[c["tag"]].reindex(idx).interpolate().fillna(0.0).values
            if c["control"] == "load/unload":
                tb = pd.DataFrame(c["performance"]).sort_values("pressure_bar_g")
                pdis = p_at_ends + drop
                full = np.interp(pdis, tb.pressure_bar_g, tb.power_kw)
                fad = np.interp(pdis, tb.pressure_bar_g, tb.fad_m3_min)
                running = kw[kw > 0.1 * kw.max()] if kw.max() > 0 else kw
                if running.size and np.percentile(running, 99) < 0.5 * tb.power_kw.min():
                    kw = kw * 3
                rel = kw / full
                share = np.zeros(len(rel))
                left_full = None          # index of the last interval at full load
                stopped = True
                for i, r in enumerate(rel):
                    if r > 0.95:
                        share[i] = 1.0
                        left_full, stopped = i, False
                        continue
                    if r < 0.03:
                        stopped = True
                        continue
                    nxt_full = i + 1 < len(rel) and rel[i + 1] > 0.95
                    if stopped and nxt_full:
                        share[i] = min(r, 1.0)
                    elif left_full is not None and i - left_full == 1:
                        share[i] = max(0.0, (r - 0.6) / 0.4)
                    elif nxt_full:
                        u = rel[i - 1] if i else 0.25
                        share[i] = max(0.0, (r - u) / (1 - u))
                    stopped = False
                sup += share * fad
            else:
                tb = pd.DataFrame(c["performance_at_set_point"]).sort_values("power_kw")
                running = kw[kw > 0.05 * tb.power_kw.max()]
                if running.size and np.percentile(running, 99) < 0.5 * tb.power_kw.max() and \
                        np.percentile(running, 5) < 0.6 * tb.power_kw.min():
                    kw = kw * 3
                on = kw >= 0.5 * tb.power_kw.min()
                sup += np.where(on, np.interp(kw, tb.power_kw, tb.fad_m3_min), 0.0)
            tot += kw
        return sup, tot

    p0 = np.interp(secs, psecs, press.values)
    sup, _ = flows(p0)
    # pressure change per interval on the pressure clock, against the fast part of supply
    pr_grid = np.arange(psecs[0], psecs[-1] + 1, STEP)
    prs = np.interp(pr_grid, psecs, press.values)
    dpp = np.diff(prs)
    fast = sup - pd.Series(sup).rolling(31, center=True, min_periods=1).median().values
    a = (fast[1:] - fast[1:].mean())
    b = (dpp - dpp.mean())
    cc = correlate(b, a, mode="full", method="fft")
    lags = np.arange(-len(a) + 1, len(b))
    # b index j at time pr_grid[j+1]; a index i at time secs[i+1]; lag in samples maps pressure clock to power clock
    k = lags[np.argmax(cc)]
    offset = (pr_grid[1] + k * STEP) - secs[1]               # pressure time of the matching sample minus power time
    pend = np.interp(secs + offset, psecs, press.values)
    pstart = np.interp(secs - STEP + offset, psecs, press.values)
    sup, tot = flows(pend)
    dem = sup - vol / pa * (pend - pstart) / STEP * 60
    s = pd.Series(dem, index=idx)
    peak = s.rolling(12).mean().max()
    mid = idx - pd.Timedelta(seconds=STEP / 2)
    h = mid.hour + mid.minute / 60 + mid.second / 3600
    mask = np.zeros(len(idx), bool)
    for lo, hi in cfg["non_production_hours"]:
        mask |= (h >= lo) & (h < hi)
    out = dict(avg_demand_m3_min=float(dem.mean()), peak_demand_m3_min=float(peak),
               leak_m3_min=float(dem[mask].mean()), specific_power_kw_per_m3_min=float(tot.sum() / sup.sum()))
    assert all(math.isfinite(v) for v in out.values())
    json.dump(out, open(dst, "w"))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
