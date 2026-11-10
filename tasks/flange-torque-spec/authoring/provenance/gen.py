"""Writes everything generated in the bundle from the sealed definition (jointsim.py, seed SEED).

    python3 gen.py OUT_DIR

OUT_DIR/data      the agent's documents: docs/procedure.md, joint_schedule.csv, fastener_handbook.csv,
                  maintenance_log.csv, examples/E01_record.csv, examples/E02_record.csv
OUT_DIR/sealed    jointsim.py and seed.json, installed for the rig user (agent container) and for the verifier

The truth (each joint's nut factor, proof load, target and interaction fraction) is whatever jointsim.seal(SEED)
returns. It never comes from running the reference solution.
"""
import csv
import json
import os
import shutil
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import jointsim as J  # noqa: E402

SEED = 4315
EARLIER = ["2019-04", "2021-02", "2022-10", "2024-05"]   # dates of earlier assemblies, oldest first

PROC = """# Bolt-up procedure JT-5

The flanged joints listed in joint_schedule.csv are to be assembled with their full bolt patterns. For each joint,
specify the assembly torque to be applied to every bolt, in newton-metres.

## Preload

Tightening a bolt to a torque T develops a preload F in it. For the fasteners used here the handbook relation is
T = K * d * F, with d the bolt nominal diameter and K the nut factor given in fastener_handbook.csv, which also
tabulates the bolt proof loads by size and grade.

## Assembly

The crew tightens each joint in one cross-pattern pass, every bolt brought to the full assembly torque in turn, with
calibrated hydraulic torque wrenches. There is no further pass.

## Trial tightenings

The rig can perform a trial tightening on any joint of the schedule. A single-bolt trial tightens one bolt of the
joint to a torque and reports the torque applied and the preload developed in that bolt: run `trial <joint_id>` to
use the rig's default torque (the handbook torque for the joint's target preload), or `trial <joint_id> <torque_Nm>`
to apply a torque of your choosing. A pattern trial, `trial <joint_id> pattern` (default torque) or
`trial <joint_id> <torque_Nm> pattern`, tightens every bolt of the joint's pattern to the torque in the crew's
sequence and reports the torque applied and the preload then measured in one monitored bolt of the pattern. A
single-bolt trial uses one trial of the allowance and a pattern trial uses two; the allowance is 8 trials in total,
and the rig refuses any trial that would exceed it.

## Records

examples/ holds the records of two earlier assemblies on this flange type, in the same format as the schedule, with
the trial and final measurements taken at the time and the sequence the assembly was tightened in.

## Requirement

Deliver `/app/output/torques.json`: {"torques": {"J01": <N.m>, ...}} with one assembly torque for every joint of
the schedule. A joint is assembled correctly when, after its pattern is tightened, the preload in each of its bolts
is within 6% of the target_preload_per_bolt_kN given for it in joint_schedule.csv and no bolt has been taken past
its proof load. The bolt-up is acceptable when at least 15 of the 16 joints are assembled correctly.
"""


def write_docs(out, truth):
    os.makedirs(os.path.join(out, "docs"), exist_ok=True)
    os.makedirs(os.path.join(out, "examples"), exist_ok=True)
    with open(os.path.join(out, "joint_schedule.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["joint_id", "thread", "grade", "bolt_count", "bolt_circle_diameter_mm", "flange_class",
                    "flange_thickness_mm", "flank_roughness_Ra_um", "plating_thickness_um", "target_preload_per_bolt_kN"])
        for (jid, d, grade, n, fc, Ra, tp, reused, frac) in J.JOINTS:
            w.writerow([jid, "M%d" % d, grade, n, "%.0f" % J.pcd_of(jid, fc, n, d), fc, "%.0f" % J.FLANGE_T_MM[fc],
                        "%.1f" % Ra, "%.1f" % tp, "%.1f" % (truth[jid]["Ftarget"] / 1e3)])
    with open(os.path.join(out, "fastener_handbook.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["item", "value"])
        w.writerow(["nut_factor_K_zinc_plated", "%.2f" % J.K_HB])
        w.writerow(["thread_tolerance_class", "6g/6H"])
        for d in sorted(J.STRESS_AREA):
            for g in ("8.8", "10.9"):
                w.writerow(["proof_load_kN_M%d_grade_%s" % (d, g), "%.1f" % (J.proof_load_N(d, g) / 1e3)])
    with open(os.path.join(out, "maintenance_log.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["joint_id", "note"])
        for (jid, d, grade, n, fc, Ra, tp, reused, frac) in J.JOINTS:
            w.writerow([jid, ("Threads reused (not re-cut). Earlier assemblies: %s." % ", ".join(EARLIER[len(EARLIER) - reused:])) if reused
                        else "New fasteners."])
    # example records: a default-torque trial, then the assembly torque that met the target, with the assembled
    # per-bolt preload measured after the pattern was tightened (lab-grade measurements, 0.3%)
    rng = np.random.default_rng(SEED + 77)
    for (eid, d, grade, n, fc, Ra, tp, reused, frac) in J.EXAMPLES:
        t = truth[eid]
        Ttr = J.K_HB * t["d"] * t["Ftarget"]
        Fs0, _ = J.single_bolt(t, Ttr)
        Ftr = Fs0 * (1 + rng.normal(0, 0.003))
        Tasm = t["k_true"] * t["d"] * t["Ftarget"] / (1 - J.M_REC * t["r"])
        Fs, _ = J.single_bolt(t, Tasm)
        Fasm = Fs * (1 - J.M_REC * t["r"]) * (1 + rng.normal(0, 0.003))
        with open(os.path.join(out, "examples", "%s_record.csv" % eid), "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["item", "value"])
            for k, v in [("joint_id", eid), ("thread", "M%d" % d), ("grade", grade), ("bolt_count", n),
                         ("bolt_circle_diameter_mm", "%.0f" % J.pcd_of(eid, fc, n, d)), ("flange_class", fc), ("flange_thickness_mm", "%.0f" % J.FLANGE_T_MM[fc]),
                         ("flank_roughness_Ra_um", "%.1f" % Ra), ("plating_thickness_um", "%.1f" % tp),
                         ("threads", "new"), ("target_preload_per_bolt_kN", "%.1f" % (t["Ftarget"] / 1e3)),
                         ("trial_torque_Nm", "%.1f" % Ttr), ("trial_bolt_preload_kN", "%.2f" % (Ftr / 1e3)),
                         ("assembly_torque_Nm", "%.1f" % Tasm),
                         ("tightening_sequence", "cross pattern in passes at 30, 70 and 100 percent of the assembly "
                          "torque, then two circular passes at 100 percent"),
                         ("assembled_preload_per_bolt_kN_measured", "%.2f" % (Fasm / 1e3))]:
                w.writerow([k, v])
    open(os.path.join(out, "docs", "procedure.md"), "w").write(PROC)


def main(out):
    truth = J.seal(SEED)
    data = os.path.join(out, "data")
    sealed = os.path.join(out, "sealed")
    for d in (data, sealed):
        shutil.rmtree(d, ignore_errors=True)
        os.makedirs(d)
    write_docs(data, truth)
    shutil.copy(os.path.join(HERE, "jointsim.py"), os.path.join(sealed, "jointsim.py"))
    with open(os.path.join(sealed, "seed.json"), "w") as f:
        json.dump({"seed": SEED}, f)


if __name__ == "__main__":
    main(sys.argv[1])
