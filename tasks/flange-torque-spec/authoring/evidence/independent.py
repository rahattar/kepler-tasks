"""Independent second solution: a different campaign, its own CSV handling and a different fit (scipy least_squares on a
smooth coating-excess term over the 6g allowance and a saturating reuse curve, roughness not centred), with the crew ratio taken from a pattern
trial on a joint that has no single-bolt trial. It shares no code with solution/solve.py and must reach an accepted
bolt-up on the shipped scenario.

    python3 authoring/evidence/independent.py > authoring/evidence/independent.txt
"""
import csv
import os
import re

import numpy as np
from scipy.optimize import least_squares

import common as C

DATA = C.DATA
SINGLES = ["J16", "J06", "J12", "J05", "J04", "J14"]     # roughness ends, two over-coated, reused once and four times
PATTERN = "J07"                                            # class A, new threads, its K from the fit
FRACTION = 0.55
ES_6G = {"M16": 38.0, "M20": 42.0, "M24": 48.0}            # |es| of the 6g external thread, micrometres


def load():
    def table(name):
        with open(os.path.join(DATA, name), newline="") as f:
            return list(csv.DictReader(f))
    sched = {r["joint_id"]: r for r in table("joint_schedule.csv")}
    reused = {r["joint_id"]: float(len(re.findall(r"[0-9]{4}-[0-9]{2}", r["note"]))) for r in table("maintenance_log.csv")}
    hb = {r["item"]: r["value"] for r in table("fastener_handbook.csv")}
    recs = []
    for name in sorted(os.listdir(os.path.join(DATA, "examples"))):
        with open(os.path.join(DATA, "examples", name), newline="") as f:
            recs.append({r["item"]: r["value"] for r in csv.DictReader(f)})
    return sched, reused, hb, recs


def soft(x, s=6.0):
    return np.logaddexp(0.0, s * x) / s


def main():
    sched, reused, hb, recs = load()
    rig = C.Rig()
    pts = []          # (Ra, excess, reused, K)
    k_meas = {}
    for j in SINGLES:
        r = sched[j]
        d = float(r["thread"][1:]) * 1e-3
        T0 = float(hb["nut_factor_K_zinc_plated"]) * d * float(r["target_preload_per_bolt_kN"]) * 1e3
        T, F = rig.trial(j, FRACTION * T0)
        assert F < 0.9 * float(hb["proof_load_kN_%s_grade_%s" % (r["thread"], r["grade"])]) * 1e3
        k_meas[j] = T / (F * d)
        pts.append((float(r["flank_roughness_Ra_um"]), float(r["plating_thickness_um"]) - ES_6G[r["thread"]] / 4,
                    reused[j], k_meas[j]))
    rec_loss = {}
    for e in recs:
        d = float(e["thread"][1:]) * 1e-3
        k = float(e["trial_torque_Nm"]) / (float(e["trial_bolt_preload_kN"]) * 1e3 * d)
        pts.append((float(e["flank_roughness_Ra_um"]), float(e["plating_thickness_um"]) - ES_6G[e["thread"]] / 4, 0.0, k))
        single_at_asm = float(e["assembly_torque_Nm"]) / (k * d)
        rec_loss[e["flange_class"]] = 1.0 - float(e["assembled_preload_per_bolt_kN_measured"]) * 1e3 / single_at_asm
    P = np.array(pts)

    def model(p, Ra, ex, re):
        a, b, c, rs, n0 = p
        return a + b * Ra + c * soft(ex) + rs * (1.0 - np.exp(-re / n0))     # reuse: a saturating curve

    p = least_squares(lambda p: model(p, P[:, 0], P[:, 1], P[:, 2]) - P[:, 3], x0=[0.09, 0.03, 0.02, 0.04, 1.5],
                      bounds=([-1, -1, -1, 0, 0.3], [1, 1, 1, 0.2, 10])).x

    def k_of(j):
        if j in k_meas:
            return k_meas[j]
        r = sched[j]
        return float(model(p, float(r["flank_roughness_Ra_um"]),
                           float(r["plating_thickness_um"]) - ES_6G[r["thread"]] / 4, reused[j]))

    r = sched[PATTERN]
    d = float(r["thread"][1:]) * 1e-3
    T0 = float(hb["nut_factor_K_zinc_plated"]) * d * float(r["target_preload_per_bolt_kN"]) * 1e3
    T, F = rig.trial(PATTERN, FRACTION * T0, pattern=True)
    loss_a = 1.0 - k_of(PATTERN) / (T / (F * d))
    factor = loss_a / rec_loss[r["flange_class"]]
    crew = {c: 1.0 - factor * v for c, v in rec_loss.items()}
    torques = {j: k_of(j) * float(s["thread"][1:]) * 1e-3 * float(s["target_preload_per_bolt_kN"]) * 1e3
               / crew[s["flange_class"]] for j, s in sched.items()}
    n, bad, errs, _ = C.grade(torques)
    e = np.array(list(errs.values()))
    print("Independent solution on the shipped scenario (seed %d)." % C.SEED)
    print("singles %s at %.0f percent of the default torque, pattern trial on %s (%d of 8 slots)" % (
        SINGLES, 100 * FRACTION, PATTERN, rig.used))
    print("fit K = %.4f + %.4f Ra + %.4f softplus(coating - |es|/4) + %.4f (1 - exp(-n / %.2f)), n earlier assemblies"
          % tuple(p))
    print("crew loss factor %.2f x recorded; crew ratios %s" % (factor, {k: round(v, 3) for k, v in crew.items()}))
    print("result: %d of 16 right (gate 15): %s; worst error %+.2f percent of target, rms %.2f percent; wrong: %s"
          % (n, "accepted" if n >= 15 else "rejected", e[np.argmax(np.abs(e))], np.sqrt(np.mean(e ** 2)), bad or "-"))


if __name__ == "__main__":
    main()
