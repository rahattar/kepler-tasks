"""grade.py PROGRAM [LIMIT_S] [SITE ...]: run the program on the hidden districts under the limit and compare.

Each run: a scratch directory holding a copy of the program alone, one CPU, threads pinned. A run still going
at the limit ends the grading: nothing it wrote is read and no later district is run.
"""
import csv, os, shutil, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
HIDDEN = os.path.join(HERE, "hidden")
FILES = ("district.json", "branches.csv", "regulators.csv", "doors.csv", "fans.csv", "fan_curves.csv", "log.csv", "points.csv")

def within(g, t):
    return abs(g - t) <= max(0.01 * abs(t), 0.02)

def grade(program, limit=30.0, sites=None, verbose=True, root=HIDDEN, truth_name="truth.csv"):
    ok_all = True; report = []
    for name in sorted(os.listdir(root)):
        case = os.path.join(root, name)
        if not os.path.isfile(os.path.join(case, truth_name)) or (sites and name not in sites): continue
        box = tempfile.mkdtemp(prefix="vf_run_")
        shutil.copy(program, os.path.join(box, "airflow.py"))
        inp = os.path.join(box, "pkg"); os.makedirs(inp)
        for f in FILES: shutil.copy(os.path.join(case, f), inp)
        out = os.path.join(box, "out.csv")
        env = dict(PATH=os.environ["PATH"], OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1", HOME=box)
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
            truth = list(csv.DictReader(open(os.path.join(case, truth_name))))
            when = {r["point"]: r["time"] for r in csv.DictReader(open(os.path.join(case, "points.csv")))}
            try:
                got = {r["point"]: r["flow_m3_s"] for r in csv.DictReader(open(out))}
            except Exception:
                got = {}; status = "no table"
            for r in truth:
                n += 1; tv = float(r["flow_m3_s"])
                try:
                    g = float(got[r["point"]]); good = g == g and within(g, tv)
                    if g == g: worst = max(worst, abs(g - tv) / max(0.01 * abs(tv), 0.02))
                except Exception:
                    good = False
                if not good: bad += 1; rounds[when[r["point"]]] = 1
        good = status == "ran" and bad == 0
        ok_all &= good
        report.append((name, status, round(dt, 1), bad, n, len(rounds), round(worst, 2)))
        shutil.rmtree(box, ignore_errors=True)
        if status == "timed out": break
    if verbose:
        for r in report:
            print("%-13s %5.1f s  %4d of %4d points out, in %2d rounds  worst %.2f of the band  %s" % (r[0], r[2], r[3], r[4], r[5], r[6], r[1]))
        print("ACCEPTED" if ok_all and report else "NOT ACCEPTED")
    return ok_all, report

if __name__ == "__main__":
    a = sys.argv[1:]
    lim = float(a[1]) if len(a) > 1 else 30.0
    grade(a[0], lim, set(a[2:]) or None)
