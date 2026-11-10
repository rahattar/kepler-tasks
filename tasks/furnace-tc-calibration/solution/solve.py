"""Reference recalibration of diffusion bay 2: corrections at 850 C and 1050 C for all 40 zones from the records and
three TC-wafer temperature steps.

    python3 solve.py DATA_DIR TCWAFER_URL RUNS_DIR OUT_CSV

Uses only the shipped records (/app/data), the run service and the run reports it writes. Never reads the
service's code, the sealed definition or the verifier.

The correction a zone needs is its drift (the profile junction reads low, in proportion to temperature in C) plus
its wafer-to-profile offset (radiative: zero in an isothermal soak, growing with temperature). The spike
thermocouple at the heater reads the junction temperature plus a heater-to-load difference that is radiative too,
so spike - raw = drift in an isothermal soak and drift + that difference at a process temperature.
1. Drift at 600 C from the trends: in any 600 C soak with the boat in and the door closed (state standby or hold)
   spike - raw is the drift. Carried to 850 C and 1050 C by T / 600.
2. Drift growth: at a fixed process setpoint and a full boat the heater-to-load difference does not change (a
   boat run without fill dummies absorbs less heat and shows a smaller difference), so a trend in
   spike - raw over the four weeks is the drift growing. Its slope, scaled from the process temperature to 600 C,
   carries each soak reading forward to the calibration (the runs' date, morning). Only F6, whose sheath is
   cracked, grows by more than a few tenths of a kelvin.
3. Offset ratio: the 2025 calibration (new assemblies, no drift) gives offsets at both temperatures in 35 zones;
   their 850/1050 ratio (least squares through the origin) carries an offset measured at one temperature to the
   other.
4. What the records cannot settle: the offset where a furnace was never calibrated on site or where its process
   tube (and with it the thermocouple well) was replaced since 2025 (one step at 1050 C each), and a retrofitted
   furnace that never soaks, whose drift and offset are both unknown. That one is run at 1050 C only: its trend
   gives spike - raw at its 850 C process setpoint (carried to the calibration), the run gives spike - raw at
   1050 C, and the two separate drift (proportional to temperature) from the heater-to-load difference
   (radiative, the T^4 law zero at 600 C), each evaluated at the junction's own temperature. With the drift known,
   the run's wafer - raw gives its new offset, and the new offset minus its 2025 offset is its liner change.
5. Liner change of the retrofitted furnaces not run: the SiC liner is an extra shield between heater and load, and
   the slip-cast liners differ in wall thickness, so one furnace's change cannot be carried to another as it is.
   The shield also raises the heater-to-load difference, which every furnace's trend shows: spike - raw at its
   process setpoint less the drift there, over the radiative shape. Against the bare-quartz furnaces of the same
   model it gives each retrofitted furnace's rise, zone by zone; the measured furnace gives, zone by zone, the ratio
   of offset change to that rise, and the other retrofitted furnaces take their own rise times that ratio.
6. Corrections: measured furnaces take the measured wafer - raw at 1050 C and, at 850 C, the drift plus the
   ratio-scaled offset; retrofitted furnaces not run take the 2025 offset plus their liner change plus their drift;
   the rest take the 2025 offset plus their drift.
"""
import csv, glob, json, os, sys, urllib.request
import numpy as np
import pandas as pd

DATA, URL, RUNS, OUT = sys.argv[1:5]
BUDGET = 3
ZONES = ["Z1", "Z2", "Z3", "Z4", "Z5"]
T0 = pd.Timestamp("2026-09-14 00:00")

REG = pd.read_csv(os.path.join(DATA, "furnace_register.csv")).set_index("furnace")
LOG = pd.read_csv(os.path.join(DATA, "maintenance_log.csv"))
CAL = pd.read_csv(os.path.join(DATA, "tc_wafer_calibration_2025.csv"))
FURN = list(REG.index)


def r(T):
    """Radiative temperature shape, zero at the 600 C soak, one at 1050 C."""
    return ((T + 273.15) ** 4 - 873.15 ** 4) / (1323.15 ** 4 - 873.15 ** 4)


def trend(f):
    t = pd.read_csv(os.path.join(DATA, "trends", "%s.csv" % f.lower()))
    t["day"] = (pd.to_datetime(t.timestamp) - T0).dt.total_seconds() / 86400.0
    return t


def gap(rows):
    return np.array([(rows["spike_%s" % z.lower()] - rows["profile_raw_%s" % z.lower()]).values for z in ZONES])


def process_creep(t):
    """Least-squares line through spike - raw over the full-boat process rows: (intercept, slope per day, setpoint,
    raw)."""
    p = t[t.state == "process"]
    sp = p.setpoint_c.mode().iloc[0]
    p = p[p.setpoint_c == sp]
    p = p[p.boat_wafers == p.boat_wafers.max()]          # full boats: a partial boat absorbs less heat
    A = np.vstack([np.ones(len(p)), p.day.values]).T
    coef = np.linalg.lstsq(A, gap(p).T, rcond=None)[0]
    raw = p[["profile_raw_%s" % z.lower() for z in ZONES]].mean().values
    return coef[0], coef[1], float(sp), raw


def drift600(t, t_cal):
    """Drift at 600 C at the calibration, or None when the furnace never soaks."""
    iso = t[t.state.isin(["standby", "hold"]) & (t.setpoint_c == 600.0)]
    if len(iso) < 20:
        return None
    d = np.median(gap(iso), axis=1)
    _, slope, sp, _ = process_creep(t)
    return d + slope * 600.0 / sp * (t_cal - float(iso.day.median()))


def offsets2025(f):
    c = CAL[CAL.furnace == f]
    if not len(c):
        return None                                   # never calibrated on site
    c = c.set_index("zone").loc[ZONES]
    return c.wafer_minus_profile_850_c.values, c.wafer_minus_profile_1050_c.values


def run(f, steps):
    done = sorted(glob.glob(os.path.join(RUNS, "run*_%s.json" % f.lower())))
    if done:
        rep = json.load(open(done[0]))
    else:
        req = urllib.request.Request("%s/run?furnace=%s&steps=%s" % (URL.rstrip("/"), f, ",".join(map(str, steps))),
                                     data=b"", method="POST")
        with urllib.request.urlopen(req, timeout=60) as resp:
            rep = json.loads(resp.read())
    out = {"date": rep["date"]}
    for s in rep["steps"]:
        zz = {z["zone"]: z for z in s["zones"]}
        out[int(s["setpoint_c"])] = {key: np.array([zz[z][key] for z in ZONES])
                                     for key in ("profile_raw_c", "spike_c", "wafer_tc_c")}
    return out


def split(g_proc, raw_proc, g_run, raw_run):
    """Drift coefficient k and heater-to-load difference h (at 1050 C) per zone from spike - raw at two
    temperatures: spike - raw = raw k / (1 - k) + h r(Tj), Tj = raw / (1 - k)."""
    k, h = np.zeros(5), np.zeros(5)
    for _ in range(50):
        tp, tr = raw_proc / (1 - k), raw_run / (1 - k)
        for i in range(5):
            A = np.array([[raw_proc[i], r(tp[i])], [raw_run[i], r(tr[i])]])
            x = np.linalg.solve(A, [g_proc[i], g_run[i]])       # x[0] = k / (1 - k)
            k[i], h[i] = x[0] / (1 + x[0]), x[1]
    return k, h


def main():
    x = CAL.wafer_minus_profile_1050_c.values; y = CAL.wafer_minus_profile_850_c.values
    rho = float(x @ y / (x @ x))
    trends = {f: trend(f) for f in FURN}
    sic = [f for f in FURN if str(REG.loc[f, "liner"]).startswith("SiC")]
    tube = {f for f in FURN if LOG[(LOG.furnace == f) & LOG.work_done.str.contains("Process tube replaced")
                                  & (LOG.date > "2025-03-10")].shape[0]}
    uncalibrated = {f for f in FURN if offsets2025(f) is None}
    t_cal0 = (pd.Timestamp("2026-10-12 08:00") - T0).total_seconds() / 86400.0      # the procedure's run day
    no_soak = {f for f in FURN if drift600(trends[f], t_cal0) is None}
    plan = {f: (1050,) for f in FURN if f in tube or f in uncalibrated or f in no_soak}
    assert sum(len(s) for s in plan.values()) <= BUDGET, plan
    assert all(f in sic for f in no_soak), "a furnace that never soaks needs its own liner reference"

    meas = {f: run(f, s) for f, s in plan.items()}
    date = next(iter(meas.values()))["date"]
    t_cal = (pd.Timestamp(date + " 08:00") - T0).total_seconds() / 86400.0
    drift = {f: drift600(trends[f], t_cal) for f in FURN}
    corr, offset_new = {}, {}
    for f in sorted(no_soak):
        m = meas[f][1050]
        a, slope, sp, raw_p = process_creep(trends[f])
        k, _ = split(a + slope * t_cal, raw_p, m["spike_c"] - m["profile_raw_c"], m["profile_raw_c"])
        drift[f] = k * 600.0
    for f, m in meas.items():
        w = m[1050]["wafer_tc_c"] - m[1050]["profile_raw_c"]
        g1050 = w - drift[f] * 1050 / 600
        offset_new[f] = (rho * g1050, g1050)
        corr[f] = (drift[f] * 850 / 600 + rho * g1050, w)
    # heater-to-load difference at 1050 C per furnace and zone: spike - raw at the process setpoint (carried to
    # the calibration) less the drift there, over the radiative shape; F3's comes from its split
    heat = {}
    for f in FURN:
        if f in no_soak:
            m = meas[f][1050]
            a, slope, sp, raw_p = process_creep(trends[f])
            heat[f] = split(a + slope * t_cal, raw_p, m["spike_c"] - m["profile_raw_c"], m["profile_raw_c"])[1]
            continue
        a, slope, sp, raw_p = process_creep(trends[f])
        heat[f] = (a + slope * t_cal - drift[f] * raw_p / 600.0) / r(raw_p)
    model = REG.model
    quartz = [f for f in FURN if f not in sic and model[f] == model[sic[0]]]
    base = np.median([heat[f] for f in quartz], axis=0)
    # the liner is an extra shield: in each zone its offset change and its heater-to-load change keep one ratio;
    # the ratio comes from the retrofitted furnace that was measured, the shielding of the others from their trends
    ref = [f for f in sic if f in meas]
    ratio = np.mean([(offset_new[f][1] - offsets2025(f)[1]) / (heat[f] - base) for f in ref], axis=0)
    liner = {f: ratio * (heat[f] - base) for f in sic}
    for f in FURN:
        if f in corr:
            continue
        lo, hi = offsets2025(f)
        if f in sic:
            lo, hi = lo + rho * liner[f], hi + liner[f]
        corr[f] = (lo + drift[f] * 850 / 600, hi + drift[f] * 1050 / 600)

    os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
    with open(OUT, "w", newline="") as fh:
        wr = csv.writer(fh)
        wr.writerow(["furnace", "zone", "correction_850_c", "correction_1050_c"])
        for f in FURN:
            for i, z in enumerate(ZONES):
                wr.writerow([f, z, round(float(corr[f][0][i]), 2), round(float(corr[f][1][i]), 2)])
    print("plan:", {f: list(s) for f, s in plan.items()}, "| offset ratio 850/1050: %.4f" % rho)
    print("liner offset change at 1050 C:", {f: np.round(liner[f], 2).tolist() for f in sic})
    print("drift at 600 C at the calibration:", {f: np.round(drift[f], 2).tolist() for f in ("F3", "F6")})


if __name__ == "__main__":
    main()
