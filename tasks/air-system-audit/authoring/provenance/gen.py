"""Sealed definition of the compressed-air audits: writes the agent's documents and example audit package (data/)
and the hidden audit packages with their true results (hidden/).

    python3 gen.py OUT_DIR

Each site is simulated second by second over its logging period:
- The plant draws air at the true demand.
- The compressors run on their pressure bands (load/unload machines) or hold a set point (variable speed).
- The receiver and piping store the difference between supply and demand.

The loggers record 10-second averages of each compressor's electrical power and the receiver pressure at each
10-second mark. The true results come from the true demand and supply, not from anything logged.
"""
import csv
import json
import math
import os
import shutil
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PATM = 1.013          # bar(a), every site (site_package.md)
DT = 10               # logging interval, s
PRESS = [6.0, 7.0, 8.0, 9.0]          # bar(g), compressor table pressures (at the compressor discharge)


def fixed_table(fad7, kw7):
    return [dict(pressure_bar_g=p, fad_m3_min=round(fad7 * (1 - 0.025 * (p - 7.0)), 3),
                 power_kw=round(kw7 * (1 + 0.065 * (p - 7.0)), 2)) for p in PRESS]


def vsd_table(fadmax, kwmax):
    rows = []
    for f in (0.25, 0.4, 0.55, 0.7, 0.85, 1.0):
        rows.append(dict(fad_m3_min=round(f * fadmax, 3), power_kw=round(kwmax * (0.14 + 0.86 * f ** 1.08), 2)))
    return rows


# comps: (tag, kind, fad at 7 bar g or max, kW, load at, unload at) for load/unload; for vsd the set point instead
# demand: production base (m3/min), surge events per production day (size as a fraction of total capacity), leak.
# one_phase: compressors whose power logger was connected with one CT (records a third of the power)
# clock_s: the pressure logger's clock is this many seconds behind the power loggers' (it records each reading with
#          an earlier time)
SITES = {
    "s-201": dict(V=9.0, dp=0.3, days=4, start="2026-09-14", comps=[
        ("C-1", "fixed", 18.0, 110.0, 6.6, 7.3), ("C-2", "fixed", 18.0, 110.0, 6.4, 7.1),
        ("C-3", "fixed", 12.0, 75.0, 6.2, 6.9)], base=27.0, surge=0.50, leak=7.5, example=True),
    "s-301": dict(V=12.0, dp=0.35, days=4, start="2026-08-03", comps=[
        ("K-1", "fixed", 22.0, 132.0, 6.7, 7.4), ("K-2", "fixed", 22.0, 132.0, 6.5, 7.2),
        ("K-3", "fixed", 15.0, 90.0, 6.3, 7.0)], base=36.0, surge=0.47, leak=11.0, one_phase=["K-2"]),
    "s-302": dict(V=7.5, dp=0.25, days=4, start="2026-08-10", comps=[
        ("A-1", "fixed", 15.0, 90.0, 6.5, 7.2), ("A-2", "fixed", 15.0, 90.0, 6.3, 7.0)], base=18.0,
        surge=0.52, leak=6.0, clock_s=3600),
    "s-303": dict(V=14.0, dp=0.3, days=4, start="2026-08-17", comps=[
        ("V-1", "vsd", 30.0, 165.0, 6.8, None), ("F-2", "fixed", 22.0, 132.0, 6.4, 7.1)], base=34.0,
        surge=0.45, leak=9.0),
    "s-304": dict(V=10.0, dp=0.3, days=4, start="2026-08-24", comps=[
        ("B-1", "fixed", 18.0, 110.0, 6.6, 7.3), ("B-2", "fixed", 18.0, 110.0, 6.4, 7.1),
        ("B-3", "fixed", 18.0, 110.0, 6.2, 6.9)], base=34.0, surge=0.47, leak=10.0, one_phase=["B-1", "B-3"]),
    "s-305": dict(V=8.0, dp=0.3, days=4, start="2026-08-31", comps=[
        ("D-1", "vsd", 22.0, 130.0, 6.9, None), ("D-2", "fixed", 15.0, 90.0, 6.5, 7.2)], base=24.0,
        surge=0.50, leak=7.0, clock_s=-1800),
    "s-306": dict(V=11.0, dp=0.4, days=4, start="2026-09-07", comps=[
        ("E-1", "fixed", 22.0, 132.0, 6.8, 7.5), ("E-2", "fixed", 12.0, 75.0, 6.6, 7.3),
        ("E-3", "fixed", 12.0, 75.0, 6.4, 7.1)], base=29.0, surge=0.50, leak=8.5),
    "s-307": dict(V=9.5, dp=0.3, days=4, start="2026-09-21", comps=[
        ("G-1", "fixed", 18.0, 110.0, 6.6, 7.3), ("G-2", "vsd", 18.0, 105.0, 6.9, None)], base=23.0,
        surge=0.50, leak=6.5, one_phase=["G-2"], clock_s=2700),
    "s-308": dict(V=13.0, dp=0.3, days=4, start="2026-09-28", comps=[
        ("H-1", "fixed", 22.0, 132.0, 6.7, 7.4), ("H-2", "fixed", 22.0, 132.0, 6.5, 7.2),
        ("H-3", "fixed", 15.0, 90.0, 6.3, 7.0)], base=37.0, surge=0.47, leak=12.0),
}
NONPROD = [(0, 6), (22, 24)]          # hours of day with production stopped (every day)


def interp_fixed(tab, p):
    ps = [r["pressure_bar_g"] for r in tab]
    return (float(np.interp(p, ps, [r["fad_m3_min"] for r in tab])),
            float(np.interp(p, ps, [r["power_kw"] for r in tab])))


def simulate(c, rng):
    n = int(c["days"] * 86400)
    tsec = np.arange(n)
    hod = (tsec % 86400) / 3600.0
    prod = ~(((hod >= 0) & (hod < 6)) | (hod >= 22))
    cap = sum(x[2] for x in c["comps"])
    # demand: production base with slow wander and fast noise, surge events, leak always
    wander = np.zeros(n)
    x = 0.0
    for i in range(n):
        x += -x / 1800.0 + rng.normal(0, 0.06)
        wander[i] = x
    D = np.where(prod, c["base"] + 2.0 * wander, c["leak"] + 0.15 * wander)
    D = D + rng.normal(0, 0.4, n) * prod
    days = c["days"]
    for d in range(days):
        for _ in range(int(rng.integers(3, 6))):
            t0 = int(d * 86400 + rng.uniform(7, 21) * 3600)
            dur = int(rng.uniform(60, 180))
            level = (1.06 + 0.08 * rng.random()) * cap               # a surge takes demand above the plant's capacity
            D[t0:t0 + dur] = level + rng.normal(0, 0.5, dur)
    D = np.maximum(D, 0.5)
    # compressors
    tabs = {}
    for tag, kind, fad, kw, a, b in c["comps"]:
        tabs[tag] = fixed_table(fad, kw) if kind == "fixed" else vsd_table(fad, kw)
    P = 7.0
    state = {x[0]: "off" for x in c["comps"]}
    since = {x[0]: 0 for x in c["comps"]}
    vsd_f = {x[0]: 0.5 for x in c["comps"]}
    integ = {x[0]: 0.0 for x in c["comps"]}
    S = np.zeros(n)
    Pw = {x[0]: np.zeros(n) for x in c["comps"]}
    Ptr = np.zeros(n)
    for i in range(n):
        s_tot = 0.0
        pdis = P + c["dp"]
        for tag, kind, fad, kw, a, b in c["comps"]:
            if kind == "fixed":
                st = state[tag]
                if P < a and st != "loaded":
                    state[tag], since[tag] = "loaded", i
                elif P > b and st == "loaded":
                    state[tag], since[tag] = "unloaded", i
                elif st == "unloaded" and i - since[tag] > 600:
                    state[tag], since[tag] = "off", i
                st = state[tag]
                f7, k7 = interp_fixed(tabs[tag], pdis)
                if st == "loaded":
                    q, pw = f7, k7
                elif st == "unloaded":
                    q, pw = 0.0, k7 * (0.25 + 0.35 * math.exp(-(i - since[tag]) / 25.0))
                else:
                    q, pw = 0.0, 0.0
            else:
                err = a - P
                integ[tag] = min(max(integ[tag] + err * 0.004, -0.2), 1.2)
                f = min(max(0.5 + 2.0 * err + integ[tag], 0.0), 1.0)
                vsd_f[tag] = f
                if f < 0.25:                                   # below minimum speed the drive stops
                    q, pw = 0.0, 0.0
                else:
                    tb = tabs[tag]
                    q = f * fad
                    pw = float(np.interp(q, [r["fad_m3_min"] for r in tb], [r["power_kw"] for r in tb]))
            s_tot += q
            Pw[tag][i] = pw
        S[i] = s_tot
        Ptr[i] = P
        P += PATM / c["V"] * (s_tot - D[i]) / 60.0
    return D, S, Pw, Ptr, prod, tabs


def truth(D, S, Pw, prod):
    k = 120
    cs = np.concatenate([[0.0], np.cumsum(D)])
    roll = (cs[k:] - cs[:-k]) / k
    energy = sum(v.sum() for v in Pw.values())
    return dict(avg_demand_m3_min=round(float(D.mean()), 4), peak_demand_m3_min=round(float(roll.max()), 4),
                leak_m3_min=round(float(D[~prod].mean()), 4),
                specific_power_kw_per_m3_min=round(float(energy / S.sum()), 4))


def stamp(start, secs):
    t0 = np.datetime64(start + "T00:00:00")
    return [str(t0 + np.timedelta64(int(s), "s")).replace("T", " ") for s in secs]


def make(name, c, rng, d):
    os.makedirs(d)
    D, S, Pw, Ptr, prod, tabs = simulate(c, rng)
    n = len(D)
    m = n // DT
    marks = np.arange(m) * DT
    os.makedirs(os.path.join(d, "loggers"))
    for tag, kind, *_ in c["comps"]:
        avg = Pw[tag][:m * DT].reshape(m, DT).mean(axis=1)
        if tag in c.get("one_phase", []):
            avg = avg / 3.0
        avg = avg * (1 + rng.normal(0, 0.006, m))
        with open(os.path.join(d, "loggers", "power_%s.csv" % tag.lower()), "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["time", "kw"])
            for t, v in zip(stamp(c["start"], marks + DT), avg):          # stamped at the end of the interval
                w.writerow([t, "%.2f" % max(v, 0.0)])
    pr = Ptr[marks] + rng.normal(0, 0.004, m)
    shift = c.get("clock_s", 0)
    with open(os.path.join(d, "loggers", "pressure.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["time", "bar_g"])
        for t, v in zip(stamp(c["start"], marks - shift), pr):
            w.writerow([t, "%.3f" % v])
    comps = []
    for tag, kind, fad, kw, a, b in c["comps"]:
        e = dict(tag=tag, control="load/unload" if kind == "fixed" else "variable speed",
                 logger="loggers/power_%s.csv" % tag.lower())
        if kind == "fixed":
            e["performance"] = tabs[tag]
        else:
            e["performance_at_set_point"] = tabs[tag]
        comps.append(e)
    site = dict(site=name.upper(), atmospheric_pressure_bar_a=PATM, storage_volume_m3=c["V"],
                pressure_drop_receiver_to_compressors_bar=c["dp"], pressure_logger="loggers/pressure.csv",
                non_production_hours=[list(x) for x in NONPROD], compressors=comps)
    with open(os.path.join(d, "site.json"), "w") as f:
        json.dump(site, f, indent=1)
    return truth(D, S, Pw, prod)


def main(out, only=None):
    rng = np.random.default_rng(2611)
    data, hidden = os.path.join(out, "data"), os.path.join(out, "hidden")
    shutil.copytree(os.path.join(HERE, "docs"), os.path.join(data, "docs"))
    tr = {}
    for name, c in SITES.items():
        sub = np.random.default_rng([2611, int(name[2:])])
        if only and name not in only:
            continue
        if c.get("example"):
            t = make(name, c, sub, os.path.join(data, "examples", name))
            with open(os.path.join(data, "examples", name, "audit_result.json"), "w") as f:
                json.dump(t, f, indent=1)
        else:
            tr[name] = make(name, c, sub, os.path.join(hidden, name))
    os.makedirs(hidden, exist_ok=True)
    with open(os.path.join(hidden, "truth.json"), "w") as f:
        json.dump(tr, f, indent=1)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:] or None)
