"""grade.py PROGRAM [LIMIT_S] [visible]: run the program on the hidden districts (or the three visible ones) and compare.

Each run: a scratch directory holding a copy of the program alone, one CPU, threads pinned, `pqsurvey` on the
PATH answering from the crew's sealed books. A run still going at the limit ends the grading.
"""
import csv, os, shutil, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
FILES = ("district.json", "branches.csv", "regulators.csv", "doors.csv", "fans.csv", "fan_curves.csv", "log.csv", "points.csv",
         "surveys.csv", "work_log.csv")
LAB = os.path.join(HERE, "core", "environment", "rig", "lab.py")

def cases(visible):
    if not visible:
        root = os.path.join(HERE, "hidden")
        return [(n, os.path.join(root, n), os.path.join(root, n, "truth.csv")) for n in sorted(os.listdir(root))
                if os.path.isfile(os.path.join(root, n, "truth.csv"))], os.path.join(HERE, "hidden_lab", "sealed")
    data = os.path.join(HERE, "core", "environment", "data"); out = []
    for n in sorted(os.listdir(os.path.join(data, "examples"))):
        out.append((n, os.path.join(data, "examples", n), os.path.join(data, "examples", n, "expected.csv")))
    for n in sorted(os.listdir(os.path.join(data, "pending"))):
        out.append((n, os.path.join(data, "pending", n), os.path.join(HERE, "hidden", "_pending_%s_truth.csv" % n)))
    return out, os.path.join(HERE, "core", "environment", "rig", "sealed")

def within(g, t): return abs(g - t) <= max(0.015 * abs(t), 0.03)

def grade(program, limit=30.0, visible=False, verbose=True):
    todo, books = cases(visible)
    lab = tempfile.mkdtemp(prefix="vf_lab_"); shutil.copytree(books, os.path.join(lab, "sealed")); os.makedirs(os.path.join(lab, "state"))
    tools = os.path.join(lab, "bin"); os.makedirs(tools)
    with open(os.path.join(tools, "pqsurvey"), "w") as f:
        f.write('#!/bin/bash\nexec %s -B %s pqsurvey "$@"\n' % (sys.executable, LAB))
    os.chmod(os.path.join(tools, "pqsurvey"), 0o755)
    ok_all = True; report = []
    for name, case, truthfile in todo:
        box = tempfile.mkdtemp(prefix="vf_run_")
        shutil.copy(program, os.path.join(box, "airflow.py"))
        inp = os.path.join(box, "pkg"); os.makedirs(inp)
        for f in FILES: shutil.copy(os.path.join(case, f), inp)
        out = os.path.join(box, "out.csv")
        env = dict(PATH=tools + os.pathsep + os.environ["PATH"], OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1",
                   HOME=box, LAB_DIR=lab)
        t = time.time(); status = "ran"
        try:
            p = subprocess.run(["taskset", "-c", "0", sys.executable, "airflow.py", inp, out], cwd=box, env=env,
                               capture_output=True, text=True, timeout=limit)
            if p.returncode != 0: status = "crashed: " + (p.stderr.strip().splitlines() or ["?"])[-1][:90]
        except subprocess.TimeoutExpired:
            status = "timed out"
        dt = time.time() - t
        bad = n = 0; rounds = {}; worst = 0.0
        if status == "ran":
            truth = list(csv.DictReader(open(truthfile)))
            when = {r["point"]: r["time"] for r in csv.DictReader(open(os.path.join(case, "points.csv")))}
            try: got = {r["point"]: r["flow_m3_s"] for r in csv.DictReader(open(out))}
            except Exception: got = {}; status = "no table"
            for r in truth:
                n += 1; tv = float(r["flow_m3_s"])
                try:
                    g = float(got[r["point"]]); good = g == g and within(g, tv)
                    if g == g: worst = max(worst, abs(g - tv) / max(0.015 * abs(tv), 0.03))
                except Exception: good = False
                if not good: bad += 1; rounds[when[r["point"]]] = 1
        orders = [open(os.path.join(lab, "state", f)).read() for f in os.listdir(os.path.join(lab, "state")) if f.startswith(name + ".")]
        for f in os.listdir(os.path.join(lab, "state")): os.unlink(os.path.join(lab, "state", f))
        ok_all &= status == "ran" and bad == 0
        report.append((name, status, round(dt, 1), bad, n, len(rounds), round(worst, 2), orders[0] if orders else "no order"))
        shutil.rmtree(box, ignore_errors=True)
        if status == "timed out": break
    shutil.rmtree(lab, ignore_errors=True)
    if verbose:
        for r in report:
            print("%-13s %5.1f s  %4d of %4d points out, in %2d rounds  worst %6.2f of the band  %s  [%s]" % (r[0], r[2], r[3], r[4], r[5], r[6], r[1], r[7]))
        print("ACCEPTED" if ok_all and report else "NOT ACCEPTED")
    return ok_all, report

if __name__ == "__main__":
    a = sys.argv[1:]
    grade(a[0], float(a[1]) if len(a) > 1 else 30.0, visible=len(a) > 2 and a[2] == "visible")
