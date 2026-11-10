"""Writes the agent-visible records of the glycol cooler bank from the sealed definition (hx.py, seed 11): the unit
register, the maintenance log, the 2025 post-cleaning acceptance tests, and seven weeks of hourly DCS trends per
unit. The documents in data/docs are written by hand and copied as they are.

    python3 gen.py OUT_DIR
"""
import os, sys
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hx

SEED = 11
SHEET_FAULT = {"E9": [("cw_out_c", -1.2), ("glycol_out_c", 2.0)]}   # E9's 2025 sheet: two readings misrecorded


def standby_blocks(u, rng):
    """(start hour, length) of standby periods: cooling water isolated, glycol circulating."""
    if u == "E8":
        return []
    if u == "E6":
        return [(30, 10)]
    n = int(rng.integers(1, 3))
    return [(int(rng.integers(24, 1140)), int(rng.integers(6, 12))) for _ in range(n)]


def trend(b, rng):
    m = hx.MODEL[b["model"]]
    hours = 49 * 24
    t0 = pd.Timestamp("2026-08-24 00:00")
    sb = standby_blocks(b["unit"], rng)
    day_ft = m["ft"] * rng.uniform(0.975, 1.005, 50)     # fixed-speed CW pumps, balancing valves set at commissioning
    day_fs = m["fs"] * rng.uniform(0.98, 1.02, 50)       # glycol on flow control
    rows = []
    for k in range(hours):
        t = k / 24.0
        d = int(t)
        standby = any(s <= k < s + n for s, n in sb)
        tci = 26.5 + 2.5 * np.sin(2 * np.pi * (t - 0.375)) + rng.normal(0, 0.1)
        thi = 70.0 + 3.0 * np.sin(2 * np.pi * t / 3.1) + rng.normal(0, 0.2)
        fs = day_fs[d] * (1 + rng.normal(0, 0.003))
        if standby:
            ft = 0.0
            tco, tho = tci, thi
        else:
            ft = day_ft[d] * (1 + rng.normal(0, 0.003))
            UA = hx.u_value(b, ft, fs, t) * hx.area(b)
            tco, tho, _ = hx.outlets(UA, ft, fs, tci, thi)
        dp = hx.dp_tube(b, ft) if ft > 0 else 0.0
        row = [(t0 + pd.Timedelta(hours=k)).strftime("%Y-%m-%d %H:%M"), "standby" if standby else "run",
               round(ft * (1 + rng.normal(0, 0.005)), 1) if ft > 0 else 0.0,
               round(fs * (1 + rng.normal(0, 0.005)), 1),
               round(tci + rng.normal(0, 0.05), 2)]
        rng.normal(0, 0.05)        # the water outlet has no per-unit transmitter (common return header)
        row += [round(thi + rng.normal(0, 0.05), 2), round(tho + b["bias"] + rng.normal(0, 0.05), 2),
                round(dp * (1 + rng.normal(0, 0.01)), 2)]
        rows.append(row)
    return pd.DataFrame(rows, columns=["timestamp", "state", "cw_flow_m3h", "glycol_flow_m3h", "cw_in_c",
                                       "glycol_in_c", "glycol_out_c", "dp_tube_kpa"])


def acceptance_2025(fleet, rng):
    rows = []
    for u in hx.UNITS:
        b = fleet[u]
        if u in hx.NEW:
            continue
        m = hx.MODEL[b["model"]]
        ft, fs = m["ft"] * rng.uniform(0.95, 1.05), m["fs"] * rng.uniform(0.95, 1.05)
        tci, thi = 25.0 + rng.uniform(-1, 1), 70.0 + rng.uniform(-1, 1)
        UA = hx.u_value(b, ft, fs, clean=True, now=False) * hx.area(b, now=False)
        tco, tho, _ = hx.outlets(UA, ft, fs, tci, thi)
        rows.append(dict(unit=u, date="2025-03-%02d" % (10 + hx.UNITS.index(u)), condition="after hydroblasting",
                         cw_flow_m3h=round(ft * (1 + rng.normal(0, 0.003)), 2), glycol_flow_m3h=round(fs * (1 + rng.normal(0, 0.003)), 2),
                         cw_in_c=round(tci + rng.normal(0, 0.02), 2), cw_out_c=round(tco + rng.normal(0, 0.02), 2),
                         glycol_in_c=round(thi + rng.normal(0, 0.02), 2), glycol_out_c=round(tho + rng.normal(0, 0.02), 2),
                         dp_tube_kpa=round(hx.dp_tube(b, ft, now=False) * (1 + rng.normal(0, 0.01)), 2)))
    df = pd.DataFrame(rows)
    for u, faults in SHEET_FAULT.items():      # misrecorded readings on the test sheet (show as a heat-balance gap)
        for col, off in faults:
            df.loc[df.unit == u, col] = (df.loc[df.unit == u, col] + off).round(2)
    return df


def main(out):
    rng = np.random.default_rng(SEED + 1000)
    fleet = hx.make_fleet(SEED)
    os.makedirs(os.path.join(out, "trends"), exist_ok=True)
    reg = pd.DataFrame([dict(unit=u, model=fleet[u]["model"],
                             service="reactor jacket glycol" if u == "E8" else "process glycol header",
                             tubes="ribbed (2026 retube)" if u in hx.ENH else "plain", in_service_since="2026-06" if u in hx.NEW else "2014")
                        for u in hx.UNITS])
    reg.to_csv(os.path.join(out, "unit_register.csv"), index=False)
    acceptance_2025(fleet, rng).to_csv(os.path.join(out, "acceptance_tests_2025.csv"), index=False)
    log = [("2025-03-10", "E1-E9", "Annual outage: bundles hydroblasted, acceptance test with calibrated instruments after cleaning. The sheet for the original E1 was withdrawn when that cooler was replaced in 2026"),
           ("2025-11-04", "E4", "Glycol outlet RTD replaced (open circuit)"),
           ("2026-01-19", "E6", "Shell gasket replaced"),
           ("2026-04-14", "E3", "Retubed with ribbed tubes (EC-2026-031, lot A)"),
           ("2026-04-28", "E7", "Retubed with ribbed tubes (EC-2026-031, lot C)"),
           ("2026-05-12", "E8", "Retubed with ribbed tubes (EC-2026-031, lot B)"),
           ("2026-06-08", "E1 and E10", "Both original coolers replaced under the capacity upgrade: two new C-310 coolers from one build batch commissioned; the C-310 datasheet clean coefficient entered in the monitoring sheet for both"),
           ("2026-07-21", "E2", "Tube leak: leaking tubes plugged both ends; number plugged not recorded on the work order"),
           ("2026-08-17", "E5", "Bundle replaced (corroded baffles); new bundle from the bundle shop to the revised baffle drawing (see bundle_e5_2026.md)"),
           ("2026-09-02", "CW", "Chlorine dosing pump failed; repaired 2026-09-12. Slime found at the E6 inlet box"),
           ("2026-09-28", "CW", "Shock chlorination of the cooling-water system, hypochlorite slug 08:00-12:00, after slime was found again at the E6 inlet box"),
           ("2026-10-26", "E1-E10", "Assessment day: three clean-and-test slots booked with the maintenance contractor")]
    pd.DataFrame(log, columns=["date", "units", "work_done"]).to_csv(os.path.join(out, "maintenance_log.csv"), index=False)
    for u in hx.UNITS:
        trend(fleet[u], rng).to_csv(os.path.join(out, "trends", "%s.csv" % u.lower()), index=False)
    return fleet


if __name__ == "__main__":
    main(sys.argv[1])
