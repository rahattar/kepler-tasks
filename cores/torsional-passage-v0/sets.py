"""The ten sets: each generating set's shaft line, its sequence of runs, and their files.

    python3 sets.py OUT [SET ...]        writes the packages and the sealed results under OUT

A set is one row of SETS. Its shaft line comes from the engine, coupling and generator named in the row, with
small seeded variations; its sequence of runs is written out in the row. The truth comes from
shaftline.simulate.

This table is where the shift between the visible and the hidden sets is built:

  role      what the agent has                                  the sequences
  example   the set and its results (expected.csv)              3 to 4 runs, ramps of 3 to 8 s, short holds:
                                                                the rubber warms by a few kelvin
  pending   the set, no results                                 set_11: a long sequence with idle holds near
                                                                the coupling's resonance; set_13: a V12
  hidden    nothing; the verifier runs the program on these     6 to 9 runs, idle holds, ramps of 4 to 40 s,
                                                                the rubber 15 to 40 K warmer by the end

and the hidden engines include V8 and V12 engines and speeds to 1800 rpm.
"""
import csv
import json
import os
import sys

sys.dont_write_bytecode = True
import numpy as np

import shaftline

PLACE = {"example": "environment/data/examples", "pending": "environment/data/pending", "hidden": "tests/sets"}
SEALED = {"pending": "authoring/provenance/pending_results", "hidden": "tests/sealed/results"}
QUANTITIES = ["crankshaft_kNm", "coupling_kNm", "generator_shaft_kNm", "rubber_C"]

ENGINES = {
    "I6": dict(orders=[1.5, 3, 4.5, 6, 7.5, 9], amps=[1500, 2500, 900, 1200, 500, 600], J=(6.0, 8.0)),
    "V8": dict(orders=[1, 2, 3, 4, 6, 8], amps=[900, 1400, 700, 2600, 500, 900], J=(5.0, 7.0)),
    "V12": dict(orders=[1.5, 3, 4.5, 6, 9, 12], amps=[1300, 2200, 700, 2800, 900, 700], J=(9.0, 11.0)),
}

# each run: (n_start_rpm, n_end_rpm, ramp_s, hold_s)
SETS = [
    dict(role="example", name="set_03", seed=3, engine="I6", start_C=38.0,
         runs=[(700, 1500, 5.0, 10.0), (1500, 900, 4.0, 5.0), (900, 1500, 8.0, 8.0)]),
    dict(role="example", name="set_08", seed=8, engine="I6", start_C=42.0,
         runs=[(750, 1500, 3.0, 8.0), (1500, 1000, 6.0, 4.0), (1000, 1500, 4.0, 6.0), (1500, 750, 7.0, 4.0)]),
    dict(role="pending", name="set_11", seed=11, engine="I6", start_C=36.0,
         runs=[(700, 850, 3.0, 60.0), (850, 1500, 20.0, 30.0), (1500, 820, 10.0, 45.0), (820, 1500, 6.0, 20.0)]),
    dict(role="pending", name="set_13", seed=13, engine="V12", start_C=40.0,
         runs=[(700, 1500, 6.0, 10.0), (1500, 1000, 5.0, 6.0), (1000, 1500, 9.0, 10.0)]),
    dict(role="hidden", name="set_02", seed=2, engine="I6", start_C=37.0,
         runs=[(700, 830, 3.0, 50.0), (830, 1500, 12.0, 20.0), (1500, 860, 8.0, 40.0), (860, 1500, 5.0, 15.0),
               (1500, 1000, 30.0, 10.0), (1000, 1500, 4.0, 20.0)]),
    dict(role="hidden", name="set_05", seed=5, engine="V8", start_C=41.0,
         runs=[(650, 900, 4.0, 40.0), (900, 1500, 15.0, 15.0), (1500, 700, 10.0, 50.0), (700, 1500, 6.0, 15.0),
               (1500, 1100, 20.0, 10.0), (1100, 1500, 8.0, 10.0)]),
    dict(role="hidden", name="set_06", seed=6, engine="V12", start_C=35.0,
         runs=[(700, 880, 3.0, 45.0), (880, 1800, 25.0, 20.0), (1800, 900, 12.0, 40.0), (900, 1800, 8.0, 15.0),
               (1800, 1200, 6.0, 10.0), (1200, 1800, 40.0, 10.0), (1800, 850, 5.0, 30.0)]),
    dict(role="hidden", name="set_09", seed=9, engine="I6", start_C=44.0,
         runs=[(750, 1500, 4.0, 15.0), (1500, 840, 6.0, 60.0), (840, 1500, 10.0, 20.0), (1500, 880, 15.0, 45.0),
               (880, 1500, 4.0, 15.0), (1500, 1200, 3.0, 10.0), (1200, 1500, 20.0, 10.0)]),
    dict(role="hidden", name="set_12", seed=12, engine="V8", start_C=39.0,
         runs=[(700, 1800, 10.0, 20.0), (1800, 760, 8.0, 50.0), (760, 1800, 30.0, 15.0), (1800, 1300, 5.0, 10.0),
               (1300, 1800, 6.0, 10.0), (1800, 780, 20.0, 40.0)]),
    dict(role="hidden", name="set_14", seed=14, engine="V12", start_C=43.0,
         runs=[(700, 860, 4.0, 55.0), (860, 1500, 6.0, 15.0), (1500, 870, 25.0, 50.0), (870, 1500, 12.0, 15.0),
               (1500, 1000, 4.0, 10.0), (1000, 1500, 35.0, 10.0), (1500, 880, 6.0, 20.0)]),
]


def line_of(s, rng):
    """The set's shaft line: its engine's data, a coupling and a generator, all varied a little by seed."""
    eng = ENGINES[s["engine"]]
    v = lambda x, spread=0.08: float(round(x * (1 + spread * (2 * rng.random() - 1)), 4))
    J1, J2 = eng["J"]
    line = dict(
        inertia_kgm2=dict(engine=v(J1), flywheel=v(J2), hub=v(1.5), generator=v(25.0)),
        crankshaft=dict(stiffness_Nm_per_rad=v(2.5e6), damping_Nms_per_rad=v(25.0, 0.3)),
        coupling=dict(stiffness_Nm_per_rad=v(1.5e5), damping_Nms_per_rad=v(230.0, 0.15), softening_per_K=v(0.008, 0.2),
                      reference_C=40.0, heat_capacity_J_per_K=v(5000.0, 0.2), cooling_W_per_K=v(12.0, 0.2)),
        generator_shaft=dict(stiffness_Nm_per_rad=v(4.0e6), damping_Nms_per_rad=v(40.0, 0.3)),
        engine_damping_Nms_per_rad=v(5.0, 0.3),
        ambient_C=v(35.0, 0.1), start_C=s["start_C"],
        orders=[dict(order=o, amplitude_Nm=v(a, 0.15), phase_deg=float(round(360 * rng.random(), 1)))
                for o, a in zip(eng["orders"], eng["amps"])])
    line["coupling"] = {k: (round(x, 6) if isinstance(x, float) else x) for k, x in line["coupling"].items()}
    return line


def build(s, out, place=None, sealed=None):
    rng = np.random.default_rng(5000 + s["seed"])
    line = line_of(s, rng)
    runs = [dict(run="R%02d" % (i + 1), n_start_rpm=a, n_end_rpm=b, ramp_s=c, hold_s=d) for i, (a, b, c, d) in enumerate(s["runs"])]
    d = os.path.join(out, place or PLACE[s["role"]], s["name"])
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "shaftline.json"), "w") as f:
        json.dump(dict(set=s["name"], engine=s["engine"], **line), f, indent=1)
    with open(os.path.join(d, "runs.csv"), "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["run", "n_start_rpm", "n_end_rpm", "ramp_s", "hold_s"])
        for r in runs:
            w.writerow([r["run"], "%g" % r["n_start_rpm"], "%g" % r["n_end_rpm"], "%g" % r["ramp_s"], "%g" % r["hold_s"]])
    peaks, temps = shaftline.simulate(line, runs)
    if s["role"] == "example" and sealed is None:
        tp = os.path.join(d, "expected.csv")
    else:
        sd = os.path.join(out, sealed or SEALED[s["role"]])
        os.makedirs(sd, exist_ok=True)
        tp = os.path.join(sd, s["name"] + ".csv")
    with open(tp, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["run"] + QUANTITIES)
        for r, p, T in zip(runs, peaks, temps):
            w.writerow([r["run"]] + ["%.4f" % (x / 1e3) for x in p] + ["%.3f" % T])
    return d


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for s in SETS:
        if len(sys.argv) > 2 and s["name"] not in sys.argv[2:]:
            continue
        build(s, sys.argv[1])
        print(s["name"], s["role"], flush=True)
