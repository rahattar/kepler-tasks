"""Writes the agent-visible records of diffusion bay 2 from the sealed definition (tc.py, seed 7): the furnace
register, the maintenance log, the 2025 TC-wafer calibration, the corrections loaded now and four weeks of 15-minute
controller trends per furnace. The documents in environment/data/docs are written by hand and copied as they are.

    python3 gen.py OUT_DIR
"""
import os, sys
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tc

SEED = 7
NOISE = 0.08
SLOTS = 150                # product slots in a boat
LOAD_K = 0.8              # heater-to-load difference with a partial boat: x (1 - LOAD_K (1 - wafers / SLOTS))
PARTIAL = {"F2": 0.8, "F7": 0.8}   # share of loads run as partial boats without fill dummies (low-volume lots)


def schedule(f, b, rng):
    """28 days of controller states at 15 min: (state, setpoint). Ramps are linear between holds."""
    n = 28 * 96
    out = []
    cur = 600.0 if b["standby"] else 750.0
    while len(out) < n:
        if b["standby"]:
            proc = {"dry oxidation": 1050.0, "wet oxidation": 1000.0, "anneal": 1050.0}[b["process"]]
            blocks = [("process", proc, int(rng.integers(12, 28))), ("standby", 600.0, int(rng.integers(8, 30)))]
            nramp = 6
        else:
            blocks = [("process", 850.0, int(rng.integers(16, 24))), ("boat_out", 750.0, int(rng.integers(3, 6)))]
            nramp = 2
        for state, sp, hold in blocks:
            for k in range(1, nramp + 1):
                out.append(("ramp", round(cur + (sp - cur) * k / (nramp + 1), 1)))
            out += [(state, sp)] * hold
            cur = sp
    return out[:n]


def with_hold(f, sched):
    """F6: held at 600 C (boat in, door closed, nitrogen) during the scrubber interlock repair, 2026-09-15 02:00-12:00."""
    if f != "F6":
        return sched
    i0 = 1 * 96 + 8                       # 2026-09-15 02:00
    prev = sched[i0 - 1][1]
    ramp_in = [("ramp", round(prev + (600.0 - prev) * k / 3, 1)) for k in (1, 2)]
    hold = [("hold", 600.0)] * 40
    nxt = sched[i0 + 42][1] if sched[i0 + 42][1] is not None else 850.0
    ramp_out = [("ramp", round(600.0 + (nxt - 600.0) * k / 3, 1)) for k in (1, 2)]
    seg = ramp_in + hold + ramp_out
    return sched[:i0 - 2] + seg + sched[i0 - 2 + len(seg):]


def loads(f, sched, rl):
    """Product wafers in the boat for each row: one draw per process block (full boats unless the furnace runs the
    low-volume lots); 0 with the boat out or in an empty soak."""
    out, cur, prev_state = [], SLOTS, None
    for state, sp in sched:
        if state == "process" and prev_state != "process":
            cur = SLOTS
            if rl.random() < PARTIAL.get(f, 0.0):
                cur = int(rl.choice([50, 75, 100]))
        if state in ("process", "ramp"):
            out.append(cur)
        else:
            out.append(0)
        prev_state = state
    return out


def trend(f, b, rng, c_lo, c_hi, rl):
    t = pd.date_range("2026-09-14 00:00", periods=28 * 96, freq="15min")
    rows = []
    b_out = rng.uniform(1.0, 6.0, 5)        # door open, boat out: heater-to-junction difference, its own per zone
    prev = None
    sched = with_hold(f, schedule(f, b, rng))
    wafers = loads(f, sched, rl)
    for i, (ts, (state, sp)) in enumerate(zip(t, sched)):
        day = i / 96.0
        lf = 1.0 - LOAD_K * (1.0 - wafers[i] / SLOTS)
        c = tc.correction_at(c_lo, c_hi, sp)
        raw_true = sp - c
        tj = tc.junction(b, raw_true, day)
        raw = raw_true + rng.normal(0, NOISE, 5)
        if state in ("standby", "hold") and sp == 600.0:
            spike = tj + b["spike_err"]
        elif state == "boat_out":
            spike = tj + b_out + rng.normal(0, 0.8, 5) + b["spike_err"]
        elif state == "ramp":                # the heater leads the tube while ramping
            lag = rng.uniform(5.0, 12.0, 5) if (prev is None or sp >= prev) else -rng.uniform(3.0, 8.0, 5)
            spike = tj + b["gradient"] * lf * tc.r(tj) + lag + b["spike_err"]
        else:
            spike = tj + b["gradient"] * lf * tc.r(tj) + b["spike_err"]
        prev = sp
        spike = spike + rng.normal(0, NOISE, 5)
        rows.append([ts.strftime("%Y-%m-%d %H:%M"), state, round(sp, 1), wafers[i]] + [round(float(x), 2) for x in raw]
                    + [round(float(x), 2) for x in spike])
    cols = ["timestamp", "state", "setpoint_c", "boat_wafers"] + ["profile_raw_%s" % z.lower() for z in tc.ZONES] + \
           ["spike_%s" % z.lower() for z in tc.ZONES]
    return pd.DataFrame(rows, columns=cols)


def main(out):
    rng = np.random.default_rng(SEED + 1000)
    bay = tc.make_bay(SEED)
    os.makedirs(os.path.join(out, "trends"), exist_ok=True)
    reg = pd.DataFrame([dict(furnace=f, model=bay[f]["model"], process=bay[f]["process"],
                             liner="SiC (2026 retrofit)" if bay[f]["liner"] == "SiC" else "quartz",
                             profile_tc="type S, 5-junction assembly", spike_tc="type S, one per zone")
                        for f in tc.FURN])
    reg.to_csv(os.path.join(out, "furnace_register.csv"), index=False)
    cal_rows, cur_rows = [], []
    for f in tc.FURN:
        b = bay[f]
        for i, z in enumerate(tc.ZONES):
            if f == "F8":
                fat = (tc.G_VX + tc.G_FAT_ERR)
                lo, hi = float(fat[i] * tc.r(850)), float(fat[i])
                cur_rows.append(dict(furnace=f, zone=z, correction_850_c=round(lo, 2), correction_1050_c=round(hi, 2),
                                     source="vendor factory acceptance (2026-05)"))
                continue
            lo = float(b["G_old"][i] * tc.r(850) + b["cal2025_err"][i])
            hi = float(b["G_old"][i] + b["cal2025_err"][i] * 1.2)
            cal_rows.append(dict(furnace=f, zone=z, wafer_minus_profile_850_c=round(lo, 2),
                                 wafer_minus_profile_1050_c=round(hi, 2)))
            cur_rows.append(dict(furnace=f, zone=z, correction_850_c=round(lo, 2), correction_1050_c=round(hi, 2),
                                 source="TC-wafer calibration 2025-03"))
    pd.DataFrame(cal_rows).to_csv(os.path.join(out, "tc_wafer_calibration_2025.csv"), index=False)
    log = [("2025-03-10", "all", "Annual PM: new profile assemblies installed in F1-F7; TC-wafer calibration of F1-F7, corrections loaded"),
           ("2025-06-16", "all", "Quarterly PM: spike thermocouples replaced"),
           ("2025-08-04", "F3", "POCl3 bubbler replaced"),
           ("2025-09-15", "all", "Quarterly PM: spike thermocouples replaced"),
           ("2025-11-18", "F1", "Boat elevator repair. Profile sheath found cracked near Z3; sheath replaced, thermocouple assembly kept"),
           ("2025-12-15", "all", "Quarterly PM: spike thermocouples replaced"),
           ("2026-01-20", "F4", "Profile assembly replaced (Z2 junction open circuit); position unchanged"),
           ("2026-02-09", "F6", "POCl3 bubbler replaced"),
           ("2026-03-16", "all", "Quarterly PM: spike thermocouples replaced"),
           ("2026-04-21", "F2", "SiC liner fitted (engineering change EC-2026-014)"),
           ("2026-05-12", "F8", "New furnace (VX-300) released to production; vendor factory-acceptance corrections loaded"),
           ("2026-05-19", "F3", "SiC liner fitted (EC-2026-014)"),
           ("2026-06-15", "all", "Quarterly PM: spike thermocouples replaced"),
           ("2026-06-23", "F7", "SiC liner fitted (EC-2026-014)"),
           ("2026-07-01", "F2", "Low-volume lots moved here; boats run without fill dummies (particle reduction)"),
           ("2026-07-01", "F7", "Low-volume lots moved here; boats run without fill dummies (particle reduction)"),
           ("2026-07-07", "F5", "Door seal O-ring replaced"),
           ("2026-08-11", "F5", "Process tube replaced (devitrification); profile assembly refitted in the new tube's thermocouple well"),
           ("2026-09-08", "F6", "Boat inspection: profile thermocouple sheath devitrified, hairline crack near Z3. Replacement profile assembly ordered (delivery after the bay calibration); furnace kept in production"),
           ("2026-09-14", "all", "Quarterly PM: spike thermocouples replaced"),
           ("2026-09-15", "F6", "Exhaust scrubber interlock fault: furnace held at 600 C, boat in, door closed, nitrogen purge, until repaired")]
    pd.DataFrame(log, columns=["date", "furnace", "work_done"]).to_csv(os.path.join(out, "maintenance_log.csv"), index=False)
    cur = pd.DataFrame(cur_rows)
    cur.to_csv(os.path.join(out, "loaded_corrections.csv"), index=False)
    rl = np.random.default_rng(SEED + 3000)
    for f in tc.FURN:
        c = cur[cur.furnace == f]
        trend(f, bay[f], rng, c.correction_850_c.values, c.correction_1050_c.values, rl).to_csv(
            os.path.join(out, "trends", "%s.csv" % f.lower()), index=False)
    return bay


if __name__ == "__main__":
    main(sys.argv[1])
