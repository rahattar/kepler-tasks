"""Builds the core: two examples with results, one pending package without, six hidden pairs. python3 gen.py

Condition: on the pending pair and on four hidden pairs one gear's lead charts carry the flank names the other
way round, so the flank the register calls working is charted under the other name. With the charts as named
no mounting misalignment reproduces both edges of the contact pattern on file; with them exchanged one does.
Both examples with results are sound. Hidden shift: the gear concerned (wheel as well as pinion), loads that
close the face where the examples leave it open, end relief, an overhung pinion with the condition.
"""
import csv, json, math, os, random, shutil
import numpy as np
import gf

HERE = os.path.dirname(os.path.abspath(__file__))


def shape(b, slope, crown, relief_end=None, relief=0.0, hollow=None):
    def f(x):
        y = slope * (x / b - 0.5) - crown * (2 * x / b - 1) ** 2
        if relief_end == "far":
            y = y - relief * np.clip((x - 0.85 * b) / (0.15 * b), 0, None) ** 2
        if relief_end == "datum":
            y = y - relief * np.clip((0.15 * b - x) / (0.15 * b), 0, None) ** 2
        if hollow:
            y = y - hollow[1] * np.exp(-((x - hollow[0] * b) / (0.08 * b)) ** 2)
        return y
    return f


def build(spec, out, hidden):
    rng = random.Random(spec["seed"])
    b = spec["b"]
    pin = dict(spec["pinion"])
    pair = {"pair": spec["tag"], "face_width_mm": b, "ratio": spec["ratio"],
            "mesh_stiffness_N_mm_um": spec["cp"], "Z_MPa_sqrt": spec["Z"], "reference_C": 40.0,
            "thermal_um_per_K": spec["kT"],
            "pinion": dict(pin, working_flank=spec["work"][0], teeth=spec["z1"]),
            "wheel": {"working_flank": spec["work"][1], "teeth": round(spec["z1"] * spec["ratio"])},
            "pattern_check": {"force_N": spec["Fc"]}}
    true_f = {}
    rows = []
    xs = [round(0.02 * b + i * 0.96 * b / 24, 2) for i in range(25)]
    for gear, gi in (("pinion", 0), ("wheel", 1)):
        work = spec["work"][gi]
        other = "L" if work == "R" else "R"
        fw, fo = shape(b, *spec["shapes"][gear]["work"]), shape(b, *spec["shapes"][gear]["other"])
        true_f[gear] = fw
        named = {work: fw, other: fo}
        if spec.get("exchanged") == gear:
            named = {work: fo, other: fw}
        for tooth in spec["teeth_charted"][gi]:
            for fl in ("L", "R"):
                for x in xs:
                    rows.append({"gear": gear, "tooth": tooth, "flank": fl, "x_mm": x,
                                 "dev_um": "%.1f" % (float(named[fl](np.array([x]))[0]) + rng.gauss(0, 0.25))})
    # the pair's true flanks as charted (mean of the teeth), so the truth and a correct program read the same curves
    def charted(gear, gi):
        work = spec["work"][gi]
        lab = work if spec.get("exchanged") != gear else ("L" if work == "R" else "R")
        return lambda x: gf.curve(rows, gear, lab, x)
    f1, f2 = charted("pinion", 0), charted("wheel", 1)
    lo, hi = gf.pattern(pair, f1, f2, spec["m0"])
    pair["pattern_check"].update({"from_mm": round(lo * 2) / 2, "to_mm": round(hi * 2) / 2})
    # duty log
    pts = []
    T, oil = spec["T0"], 45.0
    for i in range(spec["points"]):
        T = min(spec["Tmax"], max(spec["Tmin"], T + rng.gauss(0, spec["Tstep"])))
        oil = min(spec["oil"][1], max(spec["oil"][0], oil + rng.gauss(0, 0.6) + 0.002 * (T / spec["Tmax"] * spec["oil"][1] - oil)))
        pts.append({"point": "P%05d" % (i + 1), "torque_Nm": round(T, 1), "oil_C": round(oil, 1)})
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out)
    json.dump(pair, open(os.path.join(out, "pair.json"), "w"), indent=1)
    with open(os.path.join(out, "lead_charts.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, ["gear", "tooth", "flank", "x_mm", "dev_um"]); w.writeheader(); w.writerows(rows)
    with open(os.path.join(out, "duty.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, ["point", "torque_Nm", "oil_C"]); w.writeheader(); w.writerows(pts)
    if spec["results"]:
        res = gf.results(pair, f1, f2, spec["m0"], pts)
        with open(os.path.join(out, "truth.csv" if hidden else "expected.csv"), "w", newline="") as f:
            w = csv.writer(f); w.writerow(["point", "k_face", "sigma_H_MPa"])
            for r in res:
                w.writerow([r["point"], "%.4f" % r["k_face"], "%.1f" % r["sigma_H_MPa"]])
        ks = [r["k_face"] for r in res]
        print(spec["tag"], "pattern", pair["pattern_check"], "k_face %.3f..%.3f" % (min(ks), max(ks)))
    else:
        print(spec["tag"], "pattern", pair["pattern_check"])


STR = lambda d, L, a: {"base_diameter_mm": 112.8, "pitch_diameter_mm": 120.0, "body_diameter_mm": d,   # noqa
                       "mounting": "straddle", "bearing_span_mm": L, "datum_to_bearing_mm": a}
OVH = lambda d, a: {"base_diameter_mm": 112.8, "pitch_diameter_mm": 120.0, "body_diameter_mm": d,      # noqa
                    "mounting": "overhung", "datum_to_bearing_mm": a}
BASE = dict(ratio=3.2, cp=14.0, Z=58.0, kT=0.22, z1=21, teeth_charted=([1, 8, 15], [1, 23, 45]), points=20000,
            results=True, oil=(38.0, 82.0))
N = 20000
EXAMPLES = [
    dict(BASE, tag="GB-A", seed=11, b=100.0, pinion=STR(95.0, 260.0, 80.0), work=("R", "L"), Fc=4000.0, m0=5.0,
         T0=3000, Tmin=800, Tmax=5200, Tstep=60),
    dict(BASE, tag="GB-B", seed=12, b=80.0, pinion=OVH(100.0, 35.0), work=("L", "L"), Fc=3000.0, m0=-4.0,
         T0=2500, Tmin=600, Tmax=4600, Tstep=50),
]
SH = {
    "GB-A": dict(pinion={"work": (6.0, 8.0), "other": (-6.5, 3.0, "far", 4.0)}, wheel={"work": (-3.0, 4.0), "other": (2.5, 5.0)}),
    "GB-B": dict(pinion={"work": (-4.0, 6.0, "far", 3.0), "other": (4.5, 2.5)}, wheel={"work": (2.0, 3.0), "other": (-2.0, 6.0)}),
    "GB-P": dict(pinion={"work": (7.0, 7.0), "other": (-7.5, 2.5, "datum", 5.0)}, wheel={"work": (-2.0, 3.5), "other": (2.5, 4.0)}),
    "TR-1": dict(pinion={"work": (5.0, 9.0), "other": (-5.5, 3.0, "far", 5.0)}, wheel={"work": (-3.0, 3.0), "other": (3.0, 3.5)}),
    "TR-2": dict(pinion={"work": (-3.0, 5.0), "other": (3.0, 5.5)}, wheel={"work": (6.0, 7.0), "other": (-6.5, 2.0, "datum", 5.0)}),
    "TR-3": dict(pinion={"work": (4.0, 6.0), "other": (-4.0, 6.5)}, wheel={"work": (-2.0, 4.0), "other": (2.0, 3.5)}),
    "TR-4": dict(pinion={"work": (-6.0, 8.0, "datum", 3.0), "other": (6.5, 2.5)}, wheel={"work": (3.0, 3.0), "other": (-3.0, 3.0)}),
    "TR-5": dict(pinion={"work": (2.0, 4.0), "other": (-2.0, 4.5)}, wheel={"work": (-7.0, 8.0), "other": (7.5, 2.5, "far", 6.0)}),
    "TR-6": dict(pinion={"work": (5.0, 5.0, "far", 2.0), "other": (-5.0, 5.5)}, wheel={"work": (-1.0, 5.0), "other": (1.0, 4.5)}),
}
PENDING = [dict(BASE, tag="GB-P", seed=13, b=100.0, pinion=STR(90.0, 280.0, 90.0), work=("R", "L"), Fc=4000.0,
                m0=6.0, exchanged="pinion", results=False, T0=3000, Tmin=800, Tmax=5000, Tstep=60)]
HIDDEN = [
    dict(BASE, tag="TR-1", seed=21, b=110.0, pinion=STR(95.0, 300.0, 95.0), work=("R", "L"), Fc=4500.0, m0=4.0,
         exchanged="pinion", T0=5000, Tmin=1500, Tmax=9000, Tstep=90,
         shift="pinion charts exchanged; torques that close the whole face (examples leave it open)"),
    dict(BASE, tag="TR-2", seed=22, b=100.0, pinion=STR(100.0, 260.0, 80.0), work=("L", "R"), Fc=4000.0, m0=-5.0,
         exchanged="wheel", T0=3000, Tmin=800, Tmax=5500, Tstep=60,
         shift="the wheel's charts exchanged (pending: the pinion's); end relief at the datum end"),
    dict(BASE, tag="TR-3", seed=23, b=90.0, pinion=STR(90.0, 240.0, 75.0), work=("R", "R"), Fc=3500.0, m0=3.0,
         T0=2800, Tmin=700, Tmax=5000, Tstep=55, shift="sound; a slender pinion body"),
    dict(BASE, tag="TR-4", seed=24, b=80.0, pinion=OVH(105.0, 30.0), work=("L", "L"), Fc=3000.0, m0=5.0,
         exchanged="pinion", T0=2500, Tmin=600, Tmax=4800, Tstep=50,
         shift="pinion charts exchanged on an overhung pinion (pending: straddle mounted)"),
    dict(BASE, tag="TR-5", seed=25, b=120.0, pinion=STR(100.0, 320.0, 100.0), work=("R", "L"), Fc=5000.0, m0=-3.0,
         exchanged="wheel", T0=5500, Tmin=1500, Tmax=9500, Tstep=95,
         shift="the wheel's charts exchanged; the widest face and the highest torques"),
    dict(BASE, tag="TR-6", seed=26, b=100.0, pinion=STR(95.0, 270.0, 85.0), work=("L", "R"), Fc=4000.0, m0=-6.0,
         T0=3200, Tmin=900, Tmax=5400, Tstep=60, shift="sound; oil temperatures to 82 C"),
]

if __name__ == "__main__":
    man = {}
    for group, sub, hid in ((EXAMPLES, "core/data/examples", False), (PENDING, "core/data/pending", False),
                            (HIDDEN, "core/hidden", True)):
        for spec in group:
            spec = dict(spec, shapes=SH[spec["tag"]])
            build(spec, os.path.join(HERE, sub, spec["tag"]), hid)
            if hid:
                man[spec["tag"]] = {"shift": spec["shift"], "exchanged": spec.get("exchanged")}
    json.dump(man, open(os.path.join(HERE, "core", "manifest.json"), "w"), indent=1)
