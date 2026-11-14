"""Builds the core: two example furnaces with results, one pending furnace without, six hidden furnaces.

Condition: a furnace's oxygen probe starts to read high on a date nothing records (sooting), its error growing
day by day, so the atmosphere is leaner than the carbon potential the record gives. The controller holds the
probe's reading at setpoint, so from then on it needs less enrichment gas for the same loads: the carbon the
gas brings is the carbon the loads take up plus what the exhaust carries away. CD-2 never uses the enrichment
flow. The examples are clean; the pending furnace and four hidden ones drift.
Hidden shift: onset dates and drift rates beyond the pending furnace's, other grades, hotter cycles, thin
sections carburized from both sides. python3 gen.py
"""
import json, os, shutil
import numpy as np
import cd

HERE = os.path.dirname(os.path.abspath(__file__))
GRADES = {"16MnCr5": {"core_C_pct": 0.16, "alloy_factor": 1.03},
          "20MnCr5": {"core_C_pct": 0.20, "alloy_factor": 1.05},
          "18CrNiMo7-6": {"core_C_pct": 0.18, "alloy_factor": 1.12},
          "SAE 8620": {"core_C_pct": 0.20, "alloy_factor": 1.00},
          "17NiCrMo6-4": {"core_C_pct": 0.17, "alloy_factor": 1.09}}


def cycle(rng, spec):
    Tset = rng.uniform(*spec["T_range"])
    tb = int(rng.uniform(*spec["boost_h"]) * 60); td = int(rng.uniform(1.0, 3.0) * 60); th = int(rng.uniform(30, 45))
    cb = rng.uniform(1.00, 1.20); cdif = rng.uniform(0.75, 0.90)
    K = th + tb + td
    t = np.arange(K)
    T = np.where(t < th, 860 + (Tset - 860) * (1 - np.exp(-t / (th / 3.0))), Tset)
    sp = np.where(t < th + tb, cb, cdif)
    return T, sp


def build(spec, out, kind):
    rng = np.random.default_rng(spec["seed"])
    n = spec["loads"]
    grades = rng.choice(spec["grades"], n)
    area = rng.uniform(*spec["area_m2"], n)
    section = np.where(rng.random(n) < spec["thin_share"], rng.uniform(4.0, 6.0, n), rng.uniform(12, 60, n))
    Ts, sps = zip(*[cycle(rng, spec) for _ in range(n)])
    K = max(len(t) for t in Ts)
    T = np.full((n, K), 900.0); SP = np.full((n, K), 0.8); act = np.zeros((n, K), bool)
    for i in range(n):
        k = len(Ts[i]); T[i, :k] = Ts[i]; SP[i, :k] = sps[i]; act[i, :k] = True
    # loads run one after another, four or so a day; day of each load
    day = np.cumsum(rng.uniform(0.15, 0.40, n))
    drift = np.zeros(n)
    if spec.get("onset"):
        d0 = day[int(spec["onset"] * n)]
        drift = np.clip((day - d0) * spec["rate_per_day"], 0, spec["max_drift"])
    probe = SP + rng.normal(0, 0.004, SP.shape)                       # the controller holds the probe at setpoint
    Cp_true = probe - drift[:, None]
    alloy = np.array([GRADES[g]["alloy_factor"] for g in grades])
    C0 = np.array([GRADES[g]["core_C_pct"] for g in grades])
    L = np.minimum(4.0, section / 2.0)
    beta = spec["beta"]
    C, dx, up = cd.run(T, Cp_true * alloy[:, None], act, L, C0, beta)
    cs, depth = C[:, 0], cd.case_depth(C, dx)
    # enrichment gas: carbon supplied = carbon taken up + exhaust losses, at efficiency eta
    up_gh = up * (area[:, None] * 1e6) * 60.0                          # g/h, per record minute
    loss = spec["L0"] + spec["L1"] * (Cp_true - 0.8)
    q = (up_gh + loss) / (536.0 * spec["eta"])
    q = q * (1 + rng.normal(0, 0.02, q.shape)) + rng.normal(0, 0.03, q.shape)
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out)
    fur = {"furnace": spec["tag"], "mass_transfer_mm_s": beta, "probe_calibrated_day": 0.0,
           "grades": {g: GRADES[g] for g in spec["grades"]}}
    json.dump(fur, open(os.path.join(out, "furnace.json"), "w"), indent=1)
    with open(os.path.join(out, "loads.csv"), "w") as f:
        f.write("load,day,grade,area_m2,section_mm\n")
        for i in range(n):
            f.write("L%04d,%.3f,%s,%.2f,%.1f\n" % (i + 1, day[i], grades[i], area[i], section[i]))
    with open(os.path.join(out, "record.csv"), "w") as f:
        f.write("load,t_min,furnace_C,cp_probe_pct,cp_setpoint_pct,enrichment_m3h\n")
        rows = []
        for i in range(n):
            for k in range(len(Ts[i])):
                rows.append("L%04d,%d,%.1f,%.3f,%.2f,%.3f\n" % (i + 1, k, T[i, k], probe[i, k], SP[i, k], max(q[i, k], 0.0)))
        f.write("".join(rows))
    if kind != "pending":
        with open(os.path.join(out, "truth.csv" if kind == "hidden" else "expected.csv"), "w") as f:
            f.write("load,surface_C_pct,case_depth_mm\n")
            for i in range(n):
                f.write("L%04d,%.3f,%.3f\n" % (i + 1, cs[i], depth[i]))
    # what a program that takes the probe as the atmosphere gets
    Cn, dxn, _ = cd.run(T, probe * alloy[:, None], act, L, C0, beta, n=60, sub=2, picard=1)
    dn = cd.case_depth(Cn, dxn)
    e = np.abs(dn / depth - 1)
    print(spec["tag"], "loads", n, "rows", int(act.sum()), "drift max %.3f" % drift.max(),
          "probe-as-atmosphere: case out of 2%% on %d loads, worst %.1f%%" % ((e > 0.02).sum(), 100 * e.max()), flush=True)


BASE = dict(loads=250, grades=["16MnCr5", "20MnCr5", "SAE 8620"], area_m2=(6.0, 28.0), thin_share=0.15,
            T_range=(915.0, 940.0), boost_h=(2.0, 6.0), beta=2.0e-4, L0=120.0, L1=400.0, eta=0.55)
SPECS = {
    "examples": [dict(BASE, tag="CF-A", seed=1), dict(BASE, tag="CF-B", seed=2, beta=1.6e-4, eta=0.60,
                                                         grades=["18CrNiMo7-6", "16MnCr5"])],
    "pending": [dict(BASE, tag="CF-P", seed=3, onset=0.55, rate_per_day=0.006, max_drift=0.15, L0=140.0, eta=0.52)],
    "hidden": [
        dict(BASE, tag="CX-1", seed=11, onset=0.30, rate_per_day=0.010, max_drift=0.22,
             shift="drift from 30 per cent of the record, to 0.22 %C (pending: from 55 per cent, to 0.15)"),
        dict(BASE, tag="CX-2", seed=12, beta=2.4e-4, eta=0.58, T_range=(945.0, 970.0),
             shift="clean; cycles at 945 to 970 C (examples to 940)"),
        dict(BASE, tag="CX-3", seed=13, onset=0.70, rate_per_day=0.004, max_drift=0.12, grades=["17NiCrMo6-4", "20MnCr5"],
             shift="late, slow drift; a grade the examples do not have"),
        dict(BASE, tag="CX-4", seed=14, onset=0.45, rate_per_day=0.008, max_drift=0.18, thin_share=0.45,
             shift="drift; nearly half the loads thin sections carburized from both sides"),
        dict(BASE, tag="CX-5", seed=15, grades=["18CrNiMo7-6", "17NiCrMo6-4"], boost_h=(5.0, 9.0),
             shift="clean; long boosts of 5 to 9 h (examples 2 to 6)"),
        dict(BASE, tag="CX-6", seed=16, onset=0.15, rate_per_day=0.012, max_drift=0.20, L0=100.0, eta=0.50,
             shift="early, fast drift"),
    ],
}

if __name__ == "__main__":
    man = {}
    for kind, sub in (("examples", "core/data/examples"), ("pending", "core/data/pending"), ("hidden", "core/hidden")):
        for spec in SPECS[kind]:
            build(spec, os.path.join(HERE, sub, spec["tag"]), {"examples": "example"}.get(kind, kind))
            if kind == "hidden":
                man[spec["tag"]] = {"shift": spec["shift"], "onset": spec.get("onset"), "max_drift": spec.get("max_drift", 0)}
    json.dump(man, open(os.path.join(HERE, "core", "manifest.json"), "w"), indent=1)
