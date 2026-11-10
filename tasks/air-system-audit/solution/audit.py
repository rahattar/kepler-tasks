"""Computes the results of one compressed air audit by the plant procedure CA-2 and writes them.

    python3 audit.py AUDIT_DIR OUT_JSON

Before the procedure, the logs are checked against the physics of the system:
- A power analyser connected with one current transformer records a third of the power. For each compressor, its
  running power is compared with what its performance table allows. A load/unload machine's loaded power is its
  full-load power. A variable-speed machine's running power cannot fall below its table's minimum. A log near a
  third of that is multiplied by three.
- The pressure logger's clock is checked against the power loggers. The receiver pressure must rise when supply
  steps up and fall when it steps down, so the pressure log is shifted by the lag that best lines up the rate of
  change of pressure with the steps in supply.

Supply in each 10-second interval comes from each compressor's power, as a loaded fraction for load/unload machines
and from the performance table for variable-speed ones. Demand is supply less the rate at which the storage volume
fills: V / p_atm * dp/dt in free air.
"""
import csv
import json
import sys
from datetime import datetime, timezone

import numpy as np

DT = 10.0


def read_log(path):
    t, v = [], []
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            t.append(datetime.strptime(r["time"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).timestamp())
            v.append(float(list(r.values())[1]))
    return np.array(t), np.array(v)


def audit(d):
    site = json.load(open(d + "/site.json"))
    patm = float(site["atmospheric_pressure_bar_a"])
    V = float(site["storage_volume_m3"])
    dp = float(site["pressure_drop_receiver_to_compressors_bar"])
    tp, pr = read_log(d + "/" + site["pressure_logger"])
    logs = {}
    for c in site["compressors"]:
        logs[c["tag"]] = read_log(d + "/" + c["logger"])
    grid = logs[site["compressors"][0]["tag"]][0]           # interval ends, power loggers share a clock
    n = len(grid)

    def on_grid(t, v):
        return np.interp(grid, t, v)

    def supply_power(p_now):
        supply = np.zeros(n)
        power = np.zeros(n)
        for c in site["compressors"]:
            t, kw = logs[c["tag"]]
            kw = on_grid(t, kw)
            if c["control"] == "load/unload":
                tab = c["performance"]
                ps = [r["pressure_bar_g"] for r in tab]
                fad = np.interp(p_now + dp, ps, [r["fad_m3_min"] for r in tab])
                full = np.interp(p_now + dp, ps, [r["power_kw"] for r in tab])
                ratio = kw / full
                hi = ratio[ratio > 0.2]
                level = np.percentile(hi, 90) if hi.size else 1.0
                if 0.25 < level < 0.45:                       # one CT: a third of the power
                    kw = kw * 3.0
                    ratio = kw / full
                # loaded fraction of each interval: the rest of the interval was stopped (no power) when the machine
                # starts from stopped, otherwise unloaded at the blow-down level of the neighbouring interval
                frac = np.zeros(n)
                for i in range(n):
                    r = ratio[i]
                    if r >= 0.92:
                        frac[i] = 1.0
                        continue
                    prev = ratio[i - 1] if i else 0.0
                    nxt = ratio[i + 1] if i + 1 < n else 0.0
                    if prev < 0.05 and nxt >= 0.92:          # starts from stopped in this interval
                        frac[i] = r
                    elif prev >= 0.92:                       # unloads in this interval, blow-down starts near 60 %
                        frac[i] = max(0.0, (r - 0.6) / 0.4)
                    elif nxt >= 0.92 and prev >= 0.05:       # reloads from unloaded
                        frac[i] = max(0.0, (r - prev) / (1.0 - prev))
                    else:
                        frac[i] = 0.0
                supply += frac * fad
            else:
                tab = c["performance_at_set_point"]
                q = [r["fad_m3_min"] for r in tab]
                w = [r["power_kw"] for r in tab]
                run = kw[kw > 0.02 * max(w)]
                if run.size and np.percentile(run, 5) < 0.6 * min(w):
                    kw = kw * 3.0
                running = kw >= 0.5 * min(w)
                supply += np.where(running, np.interp(kw, w, q), 0.0)
            power += kw
        return supply, power

    # first pass on the pressure log as stamped, to find its clock offset
    supply, power = supply_power(np.interp(grid, tp, pr))

    # clock check: the receiver fills when supply exceeds demand, so the pressure change over an interval follows
    # the supply in that interval; with demand varying slowly, the fast part of supply is matched to the pressure
    # change over a range of clock offsets
    kern = np.ones(31) / 31.0
    fast = supply - np.convolve(supply, kern, mode="same")
    dpr = np.diff(pr)
    best, best_lag = -1e18, 0.0
    for lag in np.arange(-3 * 3600, 3 * 3600 + 1, DT):
        r = np.interp(grid - lag, tp[1:], dpr)
        cc = float(np.dot(fast, r - r.mean()))
        if cc > best:
            best, best_lag = cc, lag
    p_end = np.interp(grid - best_lag, tp, pr)
    p_start = np.interp(grid - DT - best_lag, tp, pr)
    supply, power = supply_power(p_end)              # second pass with the pressure on the power loggers' clock
    demand = supply - V / patm * (p_end - p_start) / DT * 60.0
    k = 12
    cs = np.concatenate([[0.0], np.cumsum(demand)])
    roll = (cs[k:] - cs[:-k]) / k
    hours = ((grid - DT / 2) % 86400.0) / 3600.0                # local clock time of each interval's middle
    nonprod = np.zeros(n, bool)
    for a, b in site["non_production_hours"]:
        nonprod |= (hours >= a) & (hours < b)
    return dict(avg_demand_m3_min=round(float(demand.mean()), 4), peak_demand_m3_min=round(float(roll.max()), 4),
                leak_m3_min=round(float(demand[nonprod].mean()), 4),
                specific_power_kw_per_m3_min=round(float(power.sum() / supply.sum()), 4))


if __name__ == "__main__":
    res = audit(sys.argv[1])
    with open(sys.argv[2], "w") as f:
        json.dump(res, f, indent=1)
