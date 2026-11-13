"""The ten cells: what each engine is, what its indicating system does to the pressure, and their files.

    python3 cells.py OUT [CELL ...]        writes the packages and the sealed results under OUT

A cell is one row of CELLS. `index_deg` is the true crank angle of the encoder's index mark, in degrees: 0 when
the mark sits on top dead centre. `gain` is what the transducer really gives for a unit of pressure as a
multiple of what the indicating system's scale (`bar_per_count`) assumes: 1 when the scale is right. Neither
is written in any file a program reads; they are in the records only.

This table is where the shift between the visible and the hidden cells is built:

  role      what the agent has                                   index and gain
  example   the package and its results to IS-2 (expected.csv)   both exact
  pending   the package, no results                              cell_11: index off; cell_13: gain off
  hidden    nothing; the verifier runs the program on these      one exact, one index, two gain, two both

and the hidden engines are other engines: compression ratios of 15.5 to 17.5 and bores to 130 mm against
10.0 to 11.0 and 76 to 86 mm in the visible cells, manifold pressures to 2.5 bar against 1.6, speeds from
800 to 5000 rpm against 1200 to 4000.

For every point the true pressure of every cycle comes from cylinder.simulate; its results from
cylinder.results, on the true pressure; and its record from the same pressure sampled at the angles the
encoder's pulses really fall on, scaled by the transducer's gain, given the charge amplifier's arbitrary
level for the cycle and the converter's noise, and rounded to counts.
"""
import sys

sys.dont_write_bytecode = True
import csv
import json
import os
import sys

import numpy as np

import cylinder

FINE = np.arange(-185.0, 185.0 + 1e-9, 0.1)       # degrees; the grid the truth is worked out on
ENC = -180.0 + 0.5 * np.arange(720)               # the indicating system's angle for the 720 samples of a cycle
QUANTITIES = ["imep_bar", "pmax_bar", "apmax_deg", "ca10_deg", "ca50_deg", "q_gross_J"]
CYCLES = {"example": 150, "pending": 300, "hidden": 300}     # cycles recorded at each point, for each cylinder
PLACE = {"example": "environment/data/examples", "pending": "environment/data/pending", "hidden": "tests/cells"}
SEALED = {"pending": "authoring/provenance/pending_results", "hidden": "tests/sealed/results"}

CELLS = [
    dict(role="example", cell="cell_03", seed=3, index_deg=0.0, gain=1.0, f_ht=1.03, cyl=4,
         eng=dict(bore_mm=82.0, stroke_mm=90.0, conrod_mm=145.0, compression_ratio=10.5, ivc_deg=-140.0, evo_deg=130.0),
         ignition="spark", speeds=(1500, 2000, 2500, 3000, 3500), mans=(0.45, 0.70, 0.98), points=10, scale=0.02),
    dict(role="example", cell="cell_08", seed=8, index_deg=0.0, gain=1.0, f_ht=0.96, cyl=4,
         eng=dict(bore_mm=76.0, stroke_mm=84.0, conrod_mm=138.0, compression_ratio=10.0, ivc_deg=-136.0, evo_deg=128.0),
         ignition="spark", speeds=(1500, 2500, 3500, 4000), mans=(0.55, 1.00, 1.60), points=10, scale=0.02),
    dict(role="pending", cell="cell_11", seed=11, index_deg=-1.57, gain=1.0, f_ht=1.05, cyl=6,
         eng=dict(bore_mm=86.0, stroke_mm=86.0, conrod_mm=143.0, compression_ratio=11.0, ivc_deg=-138.0, evo_deg=130.0),
         ignition="spark", speeds=(1200, 2000, 2800, 3600), mans=(0.50, 0.80, 1.00), points=10, scale=0.02),
    dict(role="pending", cell="cell_13", seed=13, index_deg=0.0, gain=1.063, f_ht=0.97, cyl=4,
         eng=dict(bore_mm=80.0, stroke_mm=84.0, conrod_mm=136.0, compression_ratio=10.8, ivc_deg=-137.0, evo_deg=129.0),
         ignition="spark", speeds=(1400, 2200, 3000, 3800), mans=(0.48, 0.75, 1.02), points=10, scale=0.02),
    dict(role="hidden", cell="cell_02", seed=2, index_deg=+2.23, gain=1.0, f_ht=0.94, cyl=4,
         eng=dict(bore_mm=84.0, stroke_mm=90.0, conrod_mm=145.0, compression_ratio=16.5, ivc_deg=-145.0, evo_deg=125.0),
         ignition="compression", speeds=(1000, 1500, 2000, 3000), mans=(1.10, 1.60, 2.30), points=10, scale=0.05),
    dict(role="hidden", cell="cell_05", seed=5, index_deg=0.0, gain=0.947, f_ht=1.07, cyl=4,
         eng=dict(bore_mm=130.0, stroke_mm=150.0, conrod_mm=250.0, compression_ratio=17.5, ivc_deg=-150.0, evo_deg=120.0),
         ignition="compression", speeds=(800, 1100, 1500, 1900), mans=(1.20, 1.80, 2.50), points=10, scale=0.05),
    dict(role="hidden", cell="cell_06", seed=6, index_deg=+1.34, gain=1.052, f_ht=1.02, cyl=6,
         eng=dict(bore_mm=105.0, stroke_mm=125.0, conrod_mm=210.0, compression_ratio=12.5, ivc_deg=-145.0, evo_deg=125.0),
         ignition="spark", speeds=(1000, 1200, 1500, 1800), mans=(0.80, 1.30, 1.90), points=10, scale=0.05),
    dict(role="hidden", cell="cell_09", seed=9, index_deg=-2.41, gain=0.958, f_ht=0.93, cyl=3,
         eng=dict(bore_mm=74.0, stroke_mm=80.0, conrod_mm=132.0, compression_ratio=11.5, ivc_deg=-135.0, evo_deg=128.0),
         ignition="spark", speeds=(1500, 2500, 4000, 5000), mans=(0.40, 0.90, 1.70), points=10, scale=0.02),
    dict(role="hidden", cell="cell_12", seed=12, index_deg=0.0, gain=1.0, f_ht=0.99, cyl=4,
         eng=dict(bore_mm=79.0, stroke_mm=88.0, conrod_mm=140.0, compression_ratio=9.6, ivc_deg=-139.0, evo_deg=131.0),
         ignition="spark", speeds=(1500, 2200, 3000, 4200), mans=(0.50, 0.85, 1.40), points=10, scale=0.02),
    dict(role="hidden", cell="cell_14", seed=14, index_deg=0.0, gain=1.071, f_ht=1.06, cyl=4,
         eng=dict(bore_mm=96.0, stroke_mm=104.0, conrod_mm=165.0, compression_ratio=15.5, ivc_deg=-146.0, evo_deg=124.0),
         ignition="compression", speeds=(900, 1400, 2000, 2600), mans=(1.00, 1.50, 2.20), points=10, scale=0.05),
]


def points_of(c, rng):
    """The session's operating points: speed, manifold pressure, charge and wall temperatures."""
    pts = []
    combos = [(s, m) for s in c["speeds"] for m in c["mans"]]
    pick = rng.choice(len(combos), size=c["points"], replace=False)
    for i, k in enumerate(sorted(pick)):
        s, m = combos[k]
        pts.append(dict(point="P%02d" % (i + 1), speed_rpm=s, p_man_bar=round(m + 0.01 * rng.integers(-3, 4), 2),
                        t_ivc_K=int(338 + 30 * rng.random()), t_wall_K=int(405 + 12 * m + 20 * rng.random())))
    return pts


def build(c, out, cycles=None, seed_shift=0, place=None, sealed=None):
    """Writes one cell: engine.json, points.csv, records/, and its results (expected.csv for an example)."""
    rng = np.random.default_rng(1000 + c["seed"] + seed_shift)
    eng = c["eng"]
    d = os.path.join(out, place or PLACE[c["role"]], c["cell"])
    os.makedirs(os.path.join(d, "records"), exist_ok=True)
    pts = points_of(c, rng)
    ejson = dict(cell=c["cell"], cylinders=c["cyl"], **eng, bar_per_count=c["scale"])
    with open(os.path.join(d, "engine.json"), "w") as f:
        json.dump(ejson, f, indent=1)
    with open(os.path.join(d, "points.csv"), "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["point", "speed_rpm", "p_man_bar", "t_ivc_K", "t_wall_K", "record"])
        for p in pts:
            w.writerow([p["point"], p["speed_rpm"], "%.2f" % p["p_man_bar"], p["t_ivc_K"], p["t_wall_K"],
                        "records/%s.npy" % p["point"].lower()])
    ncyl = c["cyl"]
    cyl_dth = rng.normal(0, 0.8, ncyl)             # each cylinder burns a little earlier or later than the others
    cyl_dq = rng.normal(0, 0.02, ncyl)             # and takes a little more or less fuel
    rows = []
    for p in pts:
        nc = cycles or CYCLES[c["role"]]
        speed, pman, tivc, tw = p["speed_rpm"], p["p_man_bar"] * 1e5, float(p["t_ivc_K"]), float(p["t_wall_K"])
        m_ch = pman * cylinder.volume(eng["ivc_deg"], eng) / (cylinder.R_GAS * tivc)
        if c["ignition"] == "spark":
            qspec = 2.25e6 * (0.92 + 0.1 * rng.random())
            th0_0, dur_0, mw_0 = -20 - 4 * rng.random() - 0.002 * (speed - 2000), 46 + 10 * rng.random(), 2.0 + 0.4 * rng.random()
            s_th, s_dur, s_q = 1.4, 0.06, 0.02
        else:
            qspec = 1.0e6 * (0.7 + 0.8 * rng.random())
            th0_0, dur_0, mw_0 = -6 - 3 * rng.random(), 42 + 14 * rng.random(), 1.0 + 0.5 * rng.random()
            s_th, s_dur, s_q = 0.3, 0.03, 0.01
        pexh = (1.05 + 0.25 * max(p["p_man_bar"] - 1.0, 0)) * 1e5
        n = ncyl * nc
        cy_of = np.repeat(np.arange(ncyl), nc)
        q = m_ch * qspec * (1 + cyl_dq[cy_of]) * (1 + s_q * rng.standard_normal(n))
        th0 = th0_0 + cyl_dth[cy_of] + s_th * rng.standard_normal(n)
        dur = dur_0 * (1 + s_dur * rng.standard_normal(n))
        mw = mw_0 * (1 + 0.04 * rng.standard_normal(n))
        ptrue = cylinder.simulate(eng, speed, pman, tivc, tw, q, th0, dur, mw, pexh, c["f_ht"], FINE)
        res = cylinder.results(FINE, ptrue, eng, speed, pman, tivc, tw)
        for cy in range(ncyl):
            rows.append([p["point"], cy + 1] + ["%.4f" % res[k].reshape(ncyl, nc)[cy].mean() for k in QUANTITIES])
        # the record: the encoder's pulses fall index_deg away from the angles the indicating system gives them
        xs = ENC + c["index_deg"]
        j = (xs - FINE[0]) / 0.1
        j0 = np.floor(j).astype(int)
        fr = j - j0
        samp = ptrue[:, j0] * (1 - fr) + ptrue[:, j0 + 1] * fr
        # the transducer gives `gain` times what the scale assumes; the level is the charge amplifier's, new each cycle
        meas = c["gain"] * samp * 1e-5 + rng.uniform(-3, 3, (n, 1)) + 0.6 * c["scale"] * rng.standard_normal(samp.shape)
        rec = np.round(meas / c["scale"]).astype(np.int16).reshape(ncyl, nc, 720)
        np.save(os.path.join(d, "records", p["point"].lower() + ".npy"), rec)
    if c["role"] == "example" and sealed is None:
        tp = os.path.join(d, "expected.csv")
    else:
        sd = os.path.join(out, sealed or SEALED[c["role"]])
        os.makedirs(sd, exist_ok=True)
        tp = os.path.join(sd, c["cell"] + ".csv")
    with open(tp, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["point", "cylinder"] + QUANTITIES)
        w.writerows(rows)
    return d


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for c in CELLS:
        if len(sys.argv) > 2 and c["cell"] not in sys.argv[2:]:
            continue
        build(c, sys.argv[1])
        print(c["cell"], c["role"], flush=True)
