"""grade.py PROGRAM [LIMIT_S] [DIR] [BOOKS]: run the program on every network of DIR (default core/hidden) under
the CPU limit, the field team answering from BOOKS (default crew/run), and compare with the results to GD-3."""
import csv
import os
import resource
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOL = 0.02
FILES = ("network.json", "mains.csv", "surveys.csv", "work_log.csv", "prs.csv", "governors.csv", "design_day.csv",
         "customers.csv", "customer_meters.csv", "boundary_valves.csv")


def main(argv):
    program = argv[1]
    limit = float(argv[2]) if len(argv) > 2 else 15.0
    hid = argv[3] if len(argv) > 3 else os.path.join(HERE, "core", "hidden")
    books = argv[4] if len(argv) > 4 else os.path.join(HERE, "crew", "run")
    ok_all = True
    for tag in sorted(os.listdir(hid)):
        case = os.path.join(hid, tag)
        truthf = os.path.join(case, "truth.csv")
        if not os.path.exists(truthf):
            truthf = os.path.join(case, "expected.csv")
        box = tempfile.mkdtemp(prefix="gd_")
        shutil.copy(program, os.path.join(box, "designday.py"))
        os.makedirs(os.path.join(box, "pkg"))
        for f in FILES:
            shutil.copy(os.path.join(case, f), os.path.join(box, "pkg"))
        os.makedirs(os.path.join(box, "bin"))
        state = os.path.join(box, "state")
        with open(os.path.join(box, "bin", "gdsurvey"), "w") as f:
            f.write('#!/bin/bash\nexec python3 -B %s gdsurvey "$@"\n' % os.path.join(HERE, "crew", "lab.py"))
        os.chmod(os.path.join(box, "bin", "gdsurvey"), 0o755)
        env = dict(PATH=os.path.join(box, "bin") + ":" + os.environ["PATH"], OMP_NUM_THREADS="1",
                   OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1", GASCREW_BOOKS=books,
                   GASCREW_STATE=state)
        soft = int(limit) + 2
        ru0 = resource.getrusage(resource.RUSAGE_CHILDREN)
        status = "ran"
        try:
            p = subprocess.run([sys.executable, "designday.py", "pkg", "out.csv"], cwd=box, env=env,
                               capture_output=True, text=True, timeout=4 * limit,
                               preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_CPU, (soft, soft + 3)))
            if p.returncode != 0:
                status = "exit %d: %s" % (p.returncode, (p.stderr.strip().splitlines() or ["?"])[-1][:70])
        except subprocess.TimeoutExpired:
            status = "timed out"
        ru1 = resource.getrusage(resource.RUSAGE_CHILDREN)
        cpu = ru1.ru_utime + ru1.ru_stime - ru0.ru_utime - ru0.ru_stime
        if status == "ran" and cpu > limit:
            status = "over the limit"
        bad, n, worst = 0, 0, 0.0
        if status == "ran":
            truth = {r["governor"]: float(r["min_pressure_barg"]) for r in csv.DictReader(open(truthf))}
            try:
                got = {r["governor"]: float(r["min_pressure_barg"])
                       for r in csv.DictReader(open(os.path.join(box, "out.csv")))}
            except Exception:
                got = {}
            for g, v in truth.items():
                n += 1
                e = abs(got[g] - v) if g in got else 9.9
                worst = max(worst, e)
                bad += e > TOL
        orders = []
        if os.path.isdir(state):
            for f in os.listdir(state):
                orders.append(open(os.path.join(state, f)).read())
        ok = status == "ran" and bad == 0
        ok_all &= ok
        print("%-5s %-8s cpu %5.1f s  %3d of %3d governors out  worst %.3f bar  %s  order: %s"
              % ("ok" if ok else "FAIL", tag, cpu, bad, n, worst, status, " | ".join(orders) or "none"), flush=True)
        shutil.rmtree(box, ignore_errors=True)
    print("ACCEPTED" if ok_all else "NOT ACCEPTED")


if __name__ == "__main__":
    main(sys.argv)
