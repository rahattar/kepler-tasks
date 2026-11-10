"""Sealed definition of the hydraulic power unit audit: writes the agent's documents and example package (data/)
and the hidden packages with their true results (hidden/).

    python3 gen.py OUT_DIR

Each press's power unit is simulated (hpusim.py) through its cycles. The true results are the oil the press took,
the highest demand flow, the hydraulic energy delivered and the electrical energy, per cycle, from the simulated
flows and pressures. The recorded logs carry the faults of the sealed definition: on some presses the logger's
pressure channels are scaled wrong (both transducers of the unit, same factor), and on some the accumulator has lost
precharge since the figure in the unit's record was taken.
"""
import csv
import json
import os
import shutil
import sys

import numpy as np

import hpusim

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "solution"))
import hpu  # noqa: E402  the HP-2 implementation, applied to the true log for the true results

HERE = os.path.dirname(os.path.abspath(__file__))
FS = 20.0
P_ATM = 1.013e5           # the logger's transducers read gauge pressure
N_CYCLES = 10
NOISE_P_BAR, NOISE_P_REL, NOISE_W_REL = 0.08, 0.0005, 0.004
# pump tables: pressure (bar), volumetric efficiency, hydromechanical efficiency at rated speed
TABLES = {
    "A": [[20, 0.975, 0.90], [50, 0.965, 0.915], [100, 0.95, 0.925], [150, 0.935, 0.925], [200, 0.92, 0.92],
          [250, 0.905, 0.91], [300, 0.89, 0.90]],
    "B": [[20, 0.98, 0.89], [50, 0.972, 0.905], [100, 0.96, 0.92], [150, 0.948, 0.925], [200, 0.935, 0.922],
          [250, 0.92, 0.915], [300, 0.905, 0.905]],
}
MOTORS = {"18.5": dict(n_sync=1500.0, n_rated=1465.0, P_rated=18.5e3, eta=0.915, idle_kw=0.9),
          "22": dict(n_sync=1500.0, n_rated=1468.0, P_rated=22e3, eta=0.92, idle_kw=1.0),
          "30": dict(n_sync=1500.0, n_rated=1472.0, P_rated=30e3, eta=0.93, idle_kw=1.2),
          "15": dict(n_sync=1500.0, n_rated=1460.0, P_rated=15e3, eta=0.905, idle_kw=0.8)}
# per press: pump Vg (cc/rev), table, motor, accumulator V0 (L), documented precharge (bar), actual precharge if it
# differs, unloading valve on/off (bar), demand profile [(s, L/min)], dwell (s), pressure scale factor of the logger
PRESSES = {
    "p-01": dict(Vg=28, table="A", motor="18.5", V0=20, p0=90, on=160, off=210, cyc=[(1.8, 55), (3.0, 6), (1.4, 40)], dwell=5.0, example=True),
    "p-11": dict(Vg=32, table="B", motor="22", V0=25, p0=100, on=170, off=230, cyc=[(2.0, 70), (2.5, 8), (1.5, 50)], dwell=6.0),
    "p-12": dict(Vg=28, table="A", motor="18.5", V0=20, p0=85, on=150, off=200, cyc=[(1.5, 50), (3.5, 5), (1.2, 38)], dwell=4.5, scale=0.8),
    "p-13": dict(Vg=45, table="B", motor="30", V0=32, p0=110, on=180, off=250, cyc=[(2.2, 95), (3.0, 10), (1.6, 70)], dwell=6.5),
    "p-14": dict(Vg=14, table="A", motor="15", V0=16, p0=80, on=140, off=190, cyc=[(1.6, 42), (2.8, 5), (1.3, 30)], dwell=5.0, p0_act=52),
    "p-15": dict(Vg=32, table="A", motor="22", V0=25, p0=95, on=165, off=220, cyc=[(1.9, 65), (3.2, 7), (1.4, 48)], dwell=5.5, scale=1.25),
    "p-16": dict(Vg=28, table="B", motor="18.5", V0=20, p0=90, on=155, off=205, cyc=[(1.7, 52), (3.0, 6), (1.3, 40)], dwell=5.0),
    "p-17": dict(Vg=32, table="A", motor="30", V0=32, p0=105, on=175, off=240, cyc=[(2.4, 90), (2.8, 9), (1.8, 68)], dwell=7.0, p0_act=66, scale=1.25),
    "p-18": dict(Vg=14, table="B", motor="15", V0=16, p0=75, on=135, off=185, cyc=[(1.5, 40), (3.0, 5), (1.2, 32)], dwell=4.5, p0_act=48),
}


def unit_of(r):
    m = MOTORS[r["motor"]]
    tab = np.array(TABLES[r["table"]], float)
    Vg = r["Vg"] * 1e-6
    return dict(Vg=Vg, n_sync=m["n_sync"], s_rated=(m["n_sync"] - m["n_rated"]) / m["n_sync"], P_rated=m["P_rated"],
                idle_kw=m["idle_kw"], V0=r["V0"] * 1e-3, p0_act=r.get("p0_act", r["p0"]) * 1e5 + P_ATM, T_amb=308.0,
                tau_th=60.0, p_on=r["on"] * 1e5 + P_ATM, p_off=r["off"] * 1e5 + P_ATM, table=tab, eta_motor=m["eta"], dp_line=3e5,
                q_ref=Vg * m["n_rated"] / 60, p_unloaded=4e5 + P_ATM, dwell=r["dwell"])


def make(name, r, rng, d):
    os.makedirs(d, exist_ok=True)
    U = unit_of(r)
    cyc = [(s, q / 6e4) for s, q in r["cyc"]]
    t, ps, pp, pe, truth = hpusim.simulate(U, cyc, N_CYCLES, rng, fs=FS)
    k = r.get("scale", 1.0)
    with open(os.path.join(d, "log.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["time_s", "system_pressure_bar", "pump_pressure_bar", "motor_power_kw"])
        for i in range(t.size):
            a = (ps[i] - P_ATM) / 1e5 * k * (1 + rng.normal(0, NOISE_P_REL)) + rng.normal(0, NOISE_P_BAR)
            b = (pp[i] - P_ATM) / 1e5 * k * (1 + rng.normal(0, NOISE_P_REL)) + rng.normal(0, NOISE_P_BAR)
            c = pe[i] / 1e3 * (1 + rng.normal(0, NOISE_W_REL))
            w.writerow(["%.2f" % t[i], "%.2f" % a, "%.2f" % b, "%.3f" % c])
    m = MOTORS[r["motor"]]
    unit = dict(press=name.upper(),
                pump=dict(type="fixed-displacement axial piston", displacement_cm3_per_rev=r["Vg"],
                          efficiency_table=[dict(pressure_bar=a, volumetric=b, hydromechanical=c) for a, b, c in TABLES[r["table"]]],
                          table_note="at rated motor speed; efficiencies vary little with speed in the motor's slip range"),
                motor=dict(type="induction, 4-pole, 50 Hz", rated_power_kw=m["P_rated"] / 1e3, synchronous_speed_rpm=m["n_sync"],
                           rated_speed_rpm=m["n_rated"], efficiency=m["eta"], unloaded_input_power_kw=m["idle_kw"]),
                accumulator=dict(type="bladder, nitrogen", volume_l=r["V0"], precharge_bar=r["p0"],
                                 precharge_note="precharge pressure at the last check, gas at ambient temperature"),
                unloading_valve="pump unloads to tank when the system pressure reaches its upper setting and reloads at its lower setting",
                logger=dict(sample_rate_hz=FS, channels=["system pressure (accumulator line)", "pump outlet pressure", "motor input power"]))
    with open(os.path.join(d, "unit.json"), "w") as f:
        json.dump(unit, f, indent=1)
    # true results: HP-2 on the true log (no noise, true pressures) with the actual precharge
    tr = hpu.results(unit, t, (ps - P_ATM) / 1e5, (pp - P_ATM) / 1e5, pe / 1e3, r.get("p0_act", r["p0"]))
    sim = {kk: round(float(np.mean([c[kk] for c in truth])), 3) for kk in truth[0]}
    tr["_simulated"] = sim
    return tr


def main(out):
    data, hidden = os.path.join(out, "data"), os.path.join(out, "hidden")
    shutil.copytree(os.path.join(HERE, "docs"), os.path.join(data, "docs"))
    tr = {}
    for name, r in PRESSES.items():
        rng = np.random.default_rng([3201, int(name[2:])])
        if r.get("example"):
            t = make(name, r, rng, os.path.join(data, "examples", name))
            t.pop("_simulated")
            with open(os.path.join(data, "examples", name, "results.json"), "w") as f:
                json.dump(t, f, indent=1)
        else:
            tr[name] = make(name, r, rng, os.path.join(hidden, name))
    os.makedirs(hidden, exist_ok=True)
    sim = {k: v.pop("_simulated") for k, v in tr.items()}
    with open(os.path.join(hidden, "truth.json"), "w") as f:
        json.dump(tr, f, indent=1)
    with open(os.path.join(out, "simulated.json"), "w") as f:      # simulated per-cycle means, for the evidence
        json.dump(sim, f, indent=1)


if __name__ == "__main__":
    main(sys.argv[1])
