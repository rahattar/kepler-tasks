"""Builds the v1 core: two examples with results, one pending package without, six hidden pairs. python3 gen.py

v1 condition: on the pending pair and four hidden pairs one gear's lead charts carry the flank names the other
way round (the inspection shop names flanks from the other end). The misalignment is measured at assembly, so
no calculation shows a misfit. The evidence is in the charts: pitting forms only on a flank that carries load,
and every exchanged gear's working flank is pitted, under the name of the other flank. Sound gears are pitted
on their working flank or not at all. Hidden shift: the gear concerned (the wheel as well as the pinion), an
overhung pinion, torques and faces beyond the examples', hotter oil.
"""
import csv, json, math, os, random, shutil
import numpy as np
import gf

HERE = os.path.dirname(os.path.abspath(__file__))
N_POINTS = 100000


def design(b, slope, crown):
    return lambda x: slope * (x / b - 0.5) - crown * (2.0 * x / b - 1.0) ** 2


def correction(pair, F):
    """Slope over the face (um) of the pinion body's deflection under a uniform load F."""
    b = pair["face_width_mm"]
    n = 200
    x = (np.arange(n) + 0.5) * b / n
    u = gf.kernel(pair["pinion"], x) @ np.full(n, F / b) * (b / n)
    return float(np.polyfit(x / b, u, 1)[0])


def build(spec, out, kind):
    rng = random.Random(spec["seed"])
    nrng = np.random.default_rng(spec["seed"])
    b = spec["b"]
    z1 = spec["z1"]
    pin = dict(spec["pinion"], working_flank=spec["work"][0], teeth=z1)
    pair = {"pair": spec["tag"], "face_width_mm": b, "ratio": round(round(z1 * spec["ratio"]) / z1, 4),
            "mesh_stiffness_N_mm_um": spec["cp"], "Z_MPa_sqrt": spec["Z"], "reference_C": 40.0,
            "thermal_um_per_K": spec["kT"], "mesh_misalignment_um": spec["m0"],
            "pinion": pin, "wheel": {"working_flank": spec["work"][1], "teeth": round(z1 * spec["ratio"])}}
    Frated = 2000.0 * 0.6 * spec["Tmax"] / pin["base_diameter_mm"]
    corr = correction(pair, Frated)
    xs = np.arange(round(0.02 * b), round(0.98 * b) + 0.5, 1.0)
    # designs: the working flanks carry the lead correction (shared between the gears) and the heavier crown
    sh = spec["share"]
    des = {"pinion": {"work": design(b, corr * sh + spec["p_extra"], spec["crown"][0]),
                      "coast": design(b, spec["coast"][0][0], spec["coast"][0][1])},
           "wheel": {"work": design(b, corr * (1 - sh) + spec["w_extra"], spec["crown"][1]),
                     "coast": design(b, spec["coast"][1][0], spec["coast"][1][1])}}
    lead0 = lambda x: des["pinion"]["work"](x) + des["wheel"]["work"](x)          # noqa: E731
    # duty record
    pts = []
    T, oil = spec["T0"], 50.0
    for i in range(N_POINTS):
        T = min(spec["Tmax"], max(spec["Tmin"], T + rng.gauss(0, spec["Tstep"])))
        target = spec["oil"][0] + (spec["oil"][1] - spec["oil"][0]) * (T - spec["Tmin"]) / (spec["Tmax"] - spec["Tmin"])
        oil = min(spec["oil"][1], max(spec["oil"][0], oil + 0.01 * (target - oil) + rng.gauss(0, 0.25)))
        pts.append((round(T, 1), round(oil, 1)))
    Tq = np.array([p[0] for p in pts])
    oilv = np.array([p[1] for p in pts])
    F_all = 2000.0 * Tq / pin["base_diameter_mm"]
    m_all = spec["m0"] + spec["kT"] * (oilv - 40.0)
    # where the service load is heaviest: pits form there
    samp = nrng.choice(N_POINTS, 600, replace=False)
    xw, W, _ = gf.loads(pair, lead0, F_all[samp], m_all[samp])
    wm = (W ** 3).mean(axis=0)
    p_x = np.interp(xs, xw, wm)
    p_x = p_x / p_x.sum()
    rows = []
    for gear, gi in (("pinion", 0), ("wheel", 1)):
        work = spec["work"][gi]
        other = "L" if work == "R" else "R"
        true = {work: des[gear]["work"], other: des[gear]["coast"]}
        named = dict(true) if spec.get("exchanged") != gear else {work: true[other], other: true[work]}
        pitted_true = gear in spec.get("pitted", ())
        for tooth in spec["teeth_charted"][gi]:
            wob = nrng.normal(0, 0.8)
            for fl in ("L", "R"):
                dev = named[fl](xs) + (wob if fl == "L" else -wob) * (xs / b - 0.5) + nrng.normal(0, 0.2, len(xs))
                # pits on the flank that truly carries the load, whatever the record calls it
                is_true_work = (named[fl] is true[work])
                if pitted_true and is_true_work:
                    for _ in range(rng.randint(2, 5)):
                        x0 = float(nrng.choice(xs, p=p_x))
                        hw = rng.uniform(0.6, 1.5)
                        dev = dev - rng.uniform(3.0, 9.0) * np.exp(-((xs - x0) / hw) ** 4)
                for x, d in zip(xs, dev):
                    rows.append({"gear": gear, "tooth": tooth, "flank": fl, "x_mm": "%.1f" % x, "dev_um": "%.1f" % d})
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out)
    json.dump(pair, open(os.path.join(out, "pair.json"), "w"), indent=1)
    with open(os.path.join(out, "lead_charts.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, ["gear", "tooth", "flank", "x_mm", "dev_um"]); w.writeheader(); w.writerows(rows)
    with open(os.path.join(out, "duty.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["point", "torque_Nm", "oil_C"])
        for i, (t, o) in enumerate(pts):
            w.writerow(["P%06d" % (i + 1), "%.1f" % t, "%.1f" % o])
    # results from the charts of the flanks in mesh (the true working flanks, by their record names)
    def charted(gear, gi):
        work = spec["work"][gi]
        lab = work if spec.get("exchanged") != gear else ("L" if work == "R" else "R")
        return gf.curve(rows, gear, lab)
    c1, c2 = charted("pinion", 0), charted("wheel", 1)
    lead = lambda x: c1(x) + c2(x)                 # noqa: E731
    named_lead = lambda x: gf.curve(rows, "pinion", spec["work"][0])(x) + gf.curve(rows, "wheel", spec["work"][1])(x)  # noqa
    info = {}
    if kind != "pending":
        x, W, nb = gf.loads(pair, lead, F_all, m_all)
        wmax = W.max(axis=1)
        k = wmax / (F_all / b)
        d1, u = pin["pitch_diameter_mm"], pair["ratio"]
        sig = spec["Z"] * np.sqrt(wmax * (u + 1) / (d1 * u))
        with open(os.path.join(out, "truth.csv" if kind == "hidden" else "expected.csv"), "w", newline="") as f:
            wr = csv.writer(f); wr.writerow(["point", "k_face", "sigma_H_MPa"])
            for i in range(N_POINTS):
                wr.writerow(["P%06d" % (i + 1), "%.4f" % k[i], "%.1f" % sig[i]])
        _, Wn, _ = gf.loads(pair, named_lead, F_all[samp], m_all[samp])
        kn = Wn.max(axis=1) / (F_all[samp] / b)
        e = np.abs(kn / k[samp] - 1)
        info = {"k_face": [round(float(k.min()), 3), round(float(k.max()), 3)], "partial": nb,
                "named_err_pct_median": round(100 * float(np.median(e)), 1), "named_out_share": round(float((e > 0.015).mean()), 2)}
    print(spec["tag"], "corr %.1f" % corr, info, flush=True)
    return info


STR = lambda d, L, a: {"base_diameter_mm": 112.8, "pitch_diameter_mm": 120.0, "body_diameter_mm": d,   # noqa
                       "mounting": "straddle", "bearing_span_mm": L, "datum_to_bearing_mm": a}
OVH = lambda d, a: {"base_diameter_mm": 112.8, "pitch_diameter_mm": 120.0, "body_diameter_mm": d,      # noqa
                    "mounting": "overhung", "datum_to_bearing_mm": a}
BASE = dict(ratio=3.2, cp=14.0, Z=58.0, kT=0.22, z1=21, oil=(42.0, 74.0), share=1.0, p_extra=0.0, w_extra=0.0)
SPECS = {
    "examples": [
        dict(BASE, tag="GB-A", seed=31, b=100.0, pinion=STR(95.0, 260.0, 80.0), work=("R", "L"), m0=4.2,
             crown=(7.5, 3.0), coast=((0.8, 4.1), (-1.2, 2.6)), teeth_charted=([1, 8, 15], [1, 23, 45]),
             T0=3000, Tmin=700, Tmax=5200, Tstep=40),
        dict(BASE, tag="GB-B", seed=32, b=80.0, pinion=OVH(100.0, 35.0), work=("L", "L"), m0=-3.1, z1=23,
             crown=(5.5, 4.4), coast=((-0.6, 3.2), (1.5, 5.0)), share=0.7, w_extra=-1.0,
             teeth_charted=([2, 10, 18], [3, 27, 51]), pitted=("wheel",), T0=2500, Tmin=600, Tmax=4600, Tstep=35),
    ],
    "pending": [
        dict(BASE, tag="GB-P", seed=33, b=100.0, pinion=STR(90.0, 280.0, 90.0), work=("R", "L"), m0=5.6, z1=19,
             crown=(8.4, 3.6), coast=((1.1, 2.4), (0.4, 4.3)), exchanged="pinion", pitted=("pinion", "wheel"),
             teeth_charted=([1, 7, 13], [1, 21, 41]), T0=3000, Tmin=800, Tmax=5000, Tstep=40),
    ],
    "hidden": [
        dict(BASE, tag="TR-1", seed=41, b=110.0, pinion=STR(95.0, 300.0, 95.0), work=("R", "L"), m0=3.0,
             crown=(6.8, 4.0), coast=((-1.4, 3.3), (0.9, 2.2)), exchanged="pinion", pitted=("pinion",),
             teeth_charted=([1, 8, 15], [1, 23, 45]), T0=5000, Tmin=1500, Tmax=9000, Tstep=70,
             shift="pinion charts exchanged; torques to 9000 N m (examples to 5200)"),
        dict(BASE, tag="TR-2", seed=42, b=100.0, pinion=STR(100.0, 260.0, 80.0), work=("L", "R"), m0=-4.4,
             crown=(5.2, 6.9), coast=((0.5, 2.9), (-0.8, 3.1)), share=0.4, p_extra=0.5, w_extra=1.0,
             exchanged="wheel", pitted=("wheel",), teeth_charted=([2, 9, 16], [4, 26, 48]),
             T0=3000, Tmin=800, Tmax=5500, Tstep=45, shift="the wheel's charts exchanged (pending: the pinion's)"),
        dict(BASE, tag="TR-3", seed=43, b=90.0, pinion=STR(90.0, 240.0, 75.0), work=("R", "R"), m0=2.4,
             crown=(6.1, 3.8), coast=((1.6, 3.0), (-0.4, 4.6)), pitted=("pinion",),
             teeth_charted=([1, 8, 15], [1, 23, 45]), T0=2800, Tmin=700, Tmax=5000, Tstep=40,
             shift="sound; the pinion pitted on its working flank"),
        dict(BASE, tag="TR-4", seed=44, b=80.0, pinion=OVH(105.0, 30.0), work=("L", "L"), m0=4.8, z1=23,
             crown=(7.0, 3.3), coast=((-0.9, 2.1), (1.3, 3.9)), exchanged="pinion", pitted=("pinion", "wheel"),
             teeth_charted=([2, 10, 18], [3, 27, 51]), T0=2500, Tmin=600, Tmax=4800, Tstep=35,
             shift="pinion charts exchanged on an overhung pinion (pending: straddle mounted)"),
        dict(BASE, tag="TR-5", seed=45, b=120.0, pinion=STR(100.0, 320.0, 100.0), work=("R", "L"), m0=-2.6,
             crown=(4.6, 7.8), coast=((0.2, 3.4), (-1.1, 2.7)), share=0.35, w_extra=-0.8,
             exchanged="wheel", pitted=("wheel",), teeth_charted=([1, 8, 15], [1, 23, 45]),
             T0=5500, Tmin=1500, Tmax=9500, Tstep=75, shift="the wheel's charts exchanged; a 120 mm face"),
        dict(BASE, tag="TR-6", seed=46, b=100.0, pinion=STR(95.0, 270.0, 85.0), work=("L", "R"), m0=-5.2,
             crown=(8.9, 2.9), coast=((-0.3, 4.4), (0.7, 3.5)), oil=(50.0, 84.0),
             teeth_charted=([2, 9, 16], [4, 26, 48]), T0=3200, Tmin=900, Tmax=5400, Tstep=40,
             shift="sound and unpitted; oil to 84 C (examples to 74)"),
    ],
}

if __name__ == "__main__":
    man = {}
    for kind, sub in (("examples", "core/data/examples"), ("pending", "core/data/pending"), ("hidden", "core/hidden")):
        for spec in SPECS[kind]:
            info = build(spec, os.path.join(HERE, sub, spec["tag"]), {"examples": "example"}.get(kind, kind))
            if kind == "hidden":
                man[spec["tag"]] = {"shift": spec["shift"], "exchanged": spec.get("exchanged"), **info}
    json.dump(man, open(os.path.join(HERE, "core", "manifest.json"), "w"), indent=1)
