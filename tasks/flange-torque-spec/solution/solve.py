"""Reference solution: plans a trial campaign, runs it on the rig, fits a nut-factor model and writes the torques.

    python3 solve.py [DATA_DIR] [OUT_JSON]

It uses only the agent's documents (/app/data) and the `trial` command. Nothing sealed is read.

Method
1. The example records give each one's single-bolt nut factor (its trial) and its ratio of assembled per-bolt preload
   to the single-bolt preload at the assembly torque. That ratio belongs to the records' own sequence (incremental
   cross-pattern passes and two circular passes); the crew makes one cross-pattern pass (procedure.md), which leaves
   more of the elastic-interaction loss, so the records' ratios are used only to scale between the flange classes.
2. Trials are run at 60% of the rig's default torque so that no trial bolt approaches its proof load: a bolt taken
   past proof yields, and the preload it reports no longer follows the torque (the rig's default, computed from the
   handbook K, does this on the low-friction joints J01 and J16).
3. Six single-bolt trials: J01 (low roughness), J03 and J06 (mid and high roughness), J09 (coating over the 6g
   allowance), and J13 and J08 (reused threads with one and three earlier assemblies). Each gives K = T / (F d).
4. One pattern trial (two slots) on J06 at the same torque as its single-bolt trial: the ratio of the two readings
   is the crew's class-A ratio. Class B's crew loss is its recorded loss scaled by the same factor.
5. New threads: K = a + b (Ra - 2) + c max(0, tp - |es|/4), with |es|/4 the coating allowance of the 6g thread
   (9.5 um M16, 10.5 um M20, 12.0 um M24), fitted on the new-thread trials and the two record trials. Reused
   threads: the measured excess over that model at one and three earlier assemblies, interpolated through zero and
   held flat beyond three, since friction from reuse rises steeply at first and then levels off.
6. For every joint the assembly torque is K d target / crew ratio; the single-bolt preload it implies is checked
   against the proof load.
"""
import csv
import json
import os
import re
import subprocess
import sys

import numpy as np

DATA = sys.argv[1] if len(sys.argv) > 1 else "/app/data"
OUT = sys.argv[2] if len(sys.argv) > 2 else "/app/output/torques.json"
TRIAL_CMD = os.environ.get("TRIAL_CMD", "trial")
CAMPAIGN = ["J01", "J03", "J06", "J08", "J09", "J13"]   # single-bolt trials, one slot each
PATTERN_JOINT = "J06"      # pattern trial (two slots) on the same class-A joint: K and K / ratio together
SAFE_FRACTION = 0.6
# coating allowance of a 6g external thread, |es| / 4, with es the fundamental deviation (ISO 965-1, ISO 4042):
# zinc thicker than this fills the clearance and galls under the nut
ES_6G_UM = {"M12": -34.0, "M16": -38.0, "M20": -42.0, "M24": -48.0}
ALLOW_UM = {t: abs(es) / 4.0 for t, es in ES_6G_UM.items()}
LINE = re.compile(r"torque applied ([0-9.]+) N\.m(?: to every bolt)?, preload (?:developed in the bolt|in the monitored bolt) ([0-9.]+) kN")


def read_rows(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def read_items(path):
    return {r["item"]: r["value"] for r in read_rows(path)}


def main():
    sched = {r["joint_id"]: r for r in read_rows(os.path.join(DATA, "joint_schedule.csv"))}
    hb = read_items(os.path.join(DATA, "fastener_handbook.csv"))
    K_hb = float(hb["nut_factor_K_zinc_plated"])
    # earlier assemblies, counted from the dates in the note: friction grows with each one
    reused = {r["joint_id"]: float(len(re.findall(r"\d{4}-\d{2}", r["note"])))
              for r in read_rows(os.path.join(DATA, "maintenance_log.csv"))}

    def d_m(r):
        return float(r["thread"][1:]) * 1e-3

    def proof_kN(r):
        return float(hb["proof_load_kN_%s_grade_%s" % (r["thread"], r["grade"])])

    # 1. pattern ratio for the recorded designs, from the example records
    ratio_rec = {}
    rec_k = []          # the records' trials are single-bolt trials: their K joins the fit
    exdir = os.path.join(DATA, "examples")
    for name in sorted(os.listdir(exdir)):
        e = read_items(os.path.join(exdir, name))
        single_at_assembly = float(e["trial_bolt_preload_kN"]) * float(e["assembly_torque_Nm"]) / float(e["trial_torque_Nm"])
        ratio_rec[e["flange_class"]] = float(e["assembled_preload_per_bolt_kN_measured"]) / single_at_assembly
        rec_k.append((float(e["trial_torque_Nm"]) / (float(e["trial_bolt_preload_kN"]) * 1e3 * d_m(e)),
                      float(e["flank_roughness_Ra_um"]), float(e["plating_thickness_um"]) - ALLOW_UM[e["thread"]], 0.0))

    # 2-3. trials at a safe torque
    def run_trial(jid, pattern=False):
        r = sched[jid]
        T = SAFE_FRACTION * K_hb * d_m(r) * float(r["target_preload_per_bolt_kN"]) * 1e3
        cmd = [TRIAL_CMD, jid, "%.1f" % T] + (["pattern"] if pattern else [])
        out = subprocess.run(cmd, capture_output=True, text=True, check=False).stdout
        m = LINE.search(out)
        if not m:
            raise SystemExit("trial failed for %s: %s" % (jid, out.strip()))
        Ta, F_kN = float(m.group(1)), float(m.group(2))
        if F_kN > 0.95 * proof_kN(r):
            raise SystemExit("trial on %s came too close to proof; lower the torque" % jid)
        return Ta / (F_kN * 1e3 * d_m(r))

    meas = {jid: run_trial(jid) for jid in CAMPAIGN}
    k_eff = run_trial(PATTERN_JOINT, pattern=True)          # K / ratio for the measured design

    # 4. fit. New threads first: K = a + b (Ra - 2) + c max(0, tp - |es|/4) on the new-thread trials and the records.
    # Then the reuse effect: each reused trial's excess over that model, against its number of earlier assemblies,
    # interpolated piecewise-linearly through (0, 0) and held flat beyond the largest count measured (friction from
    # reuse levels off; a straight line through two counts would overshoot at the ends).
    def feats(r):
        return [1.0, float(r["flank_roughness_Ra_um"]) - 2.0,
                max(0.0, float(r["plating_thickness_um"]) - ALLOW_UM[r["thread"]])]

    new = [(feats(sched[j]), meas[j]) for j in meas if reused[j] == 0]
    new += [([1.0, p[1] - 2.0, max(0.0, p[2])], p[0]) for p in rec_k]
    X = np.array([f for f, _ in new])
    y = np.array([v for _, v in new])
    b, *_ = np.linalg.lstsq(X, y, rcond=None)

    def k_new(r):
        return float(np.array(feats(r)) @ b)

    excess_by_n = {}
    for j in meas:
        if reused[j] > 0:
            excess_by_n.setdefault(reused[j], []).append(meas[j] - k_new(sched[j]))
    ns = [0.0] + sorted(excess_by_n)
    dk = [0.0] + [float(np.mean(excess_by_n[n])) for n in sorted(excess_by_n)]

    def reuse_dk(n):
        return float(np.interp(n, ns, dk)) if n <= ns[-1] else dk[-1]

    def k_model(r, jid):
        return k_new(r) + reuse_dk(reused[jid])

    # the crew's ratio for class A, from the pattern trial: the fitted (or measured) single-bolt K over the pattern
    # trial's K / ratio. The records' sequence (check passes) left a fraction of the crew's loss; that fraction is the
    # same for both flanges, so class B's crew loss is its recorded loss scaled by the class-A factor.
    kp = meas[PATTERN_JOINT] if PATTERN_JOINT in meas else k_model(sched[PATTERN_JOINT], PATTERN_JOINT)
    ca = sched[PATTERN_JOINT]["flange_class"]
    crew = {ca: float(kp / k_eff)}
    m = (1.0 - crew[ca]) / (1.0 - ratio_rec[ca])
    for c in ratio_rec:
        crew.setdefault(c, 1.0 - m * (1.0 - ratio_rec[c]))

    def ratio_for(r):
        return crew[r["flange_class"]]

    # 5. torques
    torques = {}
    for jid, r in sched.items():
        k = meas[jid] if jid in meas else k_model(r, jid)
        target_N = float(r["target_preload_per_bolt_kN"]) * 1e3
        single = target_N / ratio_for(r)
        if single > 0.97 * proof_kN(r) * 1e3:
            single = 0.97 * proof_kN(r) * 1e3          # never plan a bolt past proof
        torques[jid] = round(k * d_m(r) * single, 2)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump({"torques": torques}, f, indent=1)
    print("K = %.4f + %.4f (Ra - 2) + %.4f excess, reuse dK %s; recorded ratios %s; crew ratios %s (loss factor %.2f); wrote %s" % (
        b[0], b[1], b[2], {int(n): round(v, 4) for n, v in zip(ns, dk)}, {k: round(v, 3) for k, v in ratio_rec.items()}, {k: round(v, 3) for k, v in crew.items()}, m, OUT))


if __name__ == "__main__":
    main()
