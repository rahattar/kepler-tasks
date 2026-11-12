"""The seed screen: is the shipped draw of the records' noise an ordinary one?

build.py draws every instrument's noise from SEED. A fleet tuned on one draw could pass only on that draw, so this
script rebuilds the records with SEED replaced by each of the playbook's laboratory seeds (5301-5320), runs the
reference and the independent audit on each against the reference order, and scores each sheet through the task's
grader. The truth does not depend on SEED, so every rebuilt fleet is graded against the same answers.

It fails unless both audits are accepted on the shipped seed and on every screened seed, and it reports the worst
deviation each reaches on each seed, so a draw near an edge would be visible.

    python3 -I seed_screen.py  > ../evidence/seed_screen.txt
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TASK = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(TASK, "authoring", "evidence"))
import common as C                                                      # noqa: E402
import independent as I                                                 # noqa: E402


def build_with(seed, dest):
    """The records as build.py writes them, with only its SEED line changed."""
    work = tempfile.mkdtemp(prefix="bpd-seed-")
    try:
        for name in os.listdir(HERE):
            if name.endswith(".py"):
                shutil.copy(os.path.join(HERE, name), work)
        src = open(os.path.join(work, "build.py")).read()
        line = [l for l in src.splitlines() if l.startswith("SEED = ")]
        assert len(line) == 1, "build.py must hold exactly one SEED line"
        open(os.path.join(work, "build.py"), "w").write(src.replace(line[0], "SEED = %d" % seed, 1))
        subprocess.run([sys.executable, "-I", os.path.join(work, "build.py"), dest], check=True,
                       capture_output=True)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def reference_on(data, vac, out):
    p = subprocess.run([sys.executable, "-I", os.path.join(TASK, "solution", "diagnose.py"), data, out, vac],
                       capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError("the reference failed: %s%s" % (p.stdout, p.stderr))
    answers = {}
    with open(out) as f:
        next(f)
        for line in f:
            cid, cause, q, s = line.strip().split(",")
            answers[cid] = (cause, float(q), float(s))
    return answers


def main():
    C.header(__file__)
    shipped = int([l for l in open(os.path.join(HERE, "build.py")).read().splitlines()
                   if l.startswith("SEED = ")][0].split("=")[1])
    vac = C.place_order(C.REFERENCE_PLAN)
    rows = []
    plans = []
    fails = []
    for seed in [shipped] + C.LAB_SEEDS:
        data = os.path.join(C._work, "data-%d" % seed)
        build_with(seed, data)
        # the order is derived from the records, so a redrawn noise must not move it
        pl = subprocess.run([sys.executable, "-I", os.path.join(TASK, "solution", "diagnose.py"), "--plan", data],
                            capture_output=True, text=True)
        planned = [dict(t, pumping_time_h=float(t["pumping_time_h"])) for t in json.loads(pl.stdout)["tests"]]
        spreads = [l.split()[1] + " " + l.rsplit("(", 1)[1].split(" ")[0] for l in pl.stderr.splitlines()[:2]]
        if planned != C.REFERENCE_PLAN:
            fails.append("seed %d: the planned order is %s, not the reference order" % (seed, planned))
        plans.append(["%d" % seed, spreads[0], spreads[1]])
        for who in ("reference", "independent"):
            if who == "reference":
                answers = reference_on(data, vac, os.path.join(C._work, "ref-%d.csv" % seed))
            else:
                answers = I.audit_all(data, vac)
            r = C.score(answers)
            if "error" in r:
                fails.append("seed %d: the %s's sheet was rejected outright: %s" % (seed, who, r["error"]))
                continue
            wrong = [cid for cid in C.IDS if not r["chambers"][cid]["ok"]]
            wq = max(C.IDS, key=lambda cid: abs(r["chambers"][cid]["q_dev"]))
            ws = max(C.IDS, key=lambda cid: abs(r["chambers"][cid]["s_dev"]))
            if not r["accepted"]:
                fails.append("seed %d: the %s gets %s wrong" % (seed, who, " ".join(wrong)))
            rows.append(["%d%s" % (seed, " (shipped)" if seed == shipped else ""), who,
                         "%d/%d" % (r["npass"], len(C.IDS)),
                         "%.2f%% (%s)" % (100 * abs(r["chambers"][wq]["q_dev"]), wq),
                         "%.2f%% (%s)" % (100 * abs(r["chambers"][ws]["s_dev"]), ws)])

    print(C.report("Both audits on records rebuilt from each screened seed, reference order", rows,
                   ["build seed", "audit", "right", "worst q deviation", "worst s deviation"]))
    print("tolerances: gas load %.1f%%, speed %.1f%%" % (100 * C.G.Q_TOL, 100 * C.G.S_TOL))
    print("")
    print(C.report("The order diagnose.py --plan derives on each seed's records: the widest and next spread", plans,
                   ["build seed", "widest", "next"]))
    print("")
    if fails:
        print("%d PROBLEM(S)" % len(fails))
        for f in fails:
            print("  " + f)
    else:
        print("both audits accepted on the shipped seed and on all %d screened seeds" % len(C.LAB_SEEDS))
    C.cleanup()
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
