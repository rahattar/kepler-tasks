"""grade.py PROGRAM [LIMIT_S] [visible]: run the program on the hidden sites (or on the three visible ones) and
compare with the sealed results: pressure drop within 1.5 per cent, outlet temperature within 0.5 K.

Each run: a scratch directory holding a copy of the program alone, threads pinned to one, `heatsurvey` on the
PATH answering from the crew's sealed books (for every site here, the pending one included). The limit is on
CPU time, because the probe machine is shared."""
import csv, os, resource, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
FILES = ("site.json", "oils.csv", "lines.csv", "surveys.csv", "work_log.csv", "records.csv")
LAB = os.path.join(HERE, "core", "environment", "rig", "lab.py")

def cases(visible):
    if not visible:
        root = os.path.join(HERE, "hidden")
        return [(n, os.path.join(root, n), os.path.join(root, n, "truth.csv")) for n in sorted(os.listdir(root))]
    data = os.path.join(HERE, "core", "environment", "data"); out = []
    for kind in ("examples", "pending"):
        for n in sorted(os.listdir(os.path.join(data, kind))) if os.path.isdir(os.path.join(data, kind)) else []:
            out.append((n, os.path.join(data, kind, n), os.path.join(HERE, "hidden_lab", "truth", n + ".csv")))
    return out

def grade(program, limit=60.0, visible=False, verbose=True):
    lab = tempfile.mkdtemp(prefix="ol_lab_"); shutil.copytree(os.path.join(HERE, "hidden_lab", "sealed"), os.path.join(lab, "sealed")); os.makedirs(os.path.join(lab, "state"))
    tools = os.path.join(lab, "bin"); os.makedirs(tools)
    with open(os.path.join(tools, "heatsurvey"), "w") as f: f.write('#!/bin/bash\nexec %s -B %s heatsurvey "$@"\n' % (sys.executable, LAB))
    os.chmod(os.path.join(tools, "heatsurvey"), 0o755)
    ok_all = True; rep = []
    for name, case, truthfile in cases(visible):
        box = tempfile.mkdtemp(prefix="ol_run_"); shutil.copy(program, os.path.join(box, "lines.py"))
        inp = os.path.join(box, "pkg"); os.makedirs(inp)
        for f in FILES: shutil.copy(os.path.join(case, f), inp)
        out = os.path.join(box, "out.csv")
        env = dict(PATH=tools + os.pathsep + os.environ["PATH"], OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1", HOME=box, LAB_DIR=lab)
        def lim(): resource.setrlimit(resource.RLIMIT_CPU, (int(limit), int(limit) + 1))
        r0 = resource.getrusage(resource.RUSAGE_CHILDREN); status = "ran"
        try:
            p = subprocess.run([sys.executable, "lines.py", inp, out], cwd=box, env=env, capture_output=True, text=True, timeout=limit * 6, preexec_fn=lim)
            if p.returncode < 0: status = "timed out"
            elif p.returncode != 0: status = "crashed: " + (p.stderr.strip().splitlines() or ["?"])[-1][:90]
        except subprocess.TimeoutExpired:
            status = "timed out (wall)"
        r1 = resource.getrusage(resource.RUSAGE_CHILDREN); cpu = r1.ru_utime + r1.ru_stime - r0.ru_utime - r0.ru_stime
        bad = n = 0; lines_out = set(); worst = 0.0
        if status == "ran":
            try: got = {r["record"]: r for r in csv.DictReader(open(out))}
            except Exception: got = {}; status = "no table"
            for t in csv.DictReader(open(truthfile)):
                n += 1
                try:
                    e1 = abs(float(got[t["record"]]["dp_kPa"]) / float(t["dp_kPa"]) - 1) / 0.015; e2 = abs(float(got[t["record"]]["t_out_C"]) - float(t["t_out_C"])) / 0.5
                    e = max(e1, e2); e = e if e == e else 9e9
                except Exception: e = 9e9
                if e < 9e8: worst = max(worst, e)
                if e > 1.0: bad += 1; lines_out.add(t["record"].split("/")[0])
        st = os.path.join(lab, "state")
        orders = [open(os.path.join(st, f)).read() for f in os.listdir(st) if f.startswith(name + ".")]
        for f in os.listdir(st): os.unlink(os.path.join(st, f))
        ok_all &= status == "ran" and bad == 0
        rep.append((name, status, cpu, bad, n, sorted(lines_out), worst, orders[0] if orders else "no order"))
        shutil.rmtree(box, ignore_errors=True)
    shutil.rmtree(lab, ignore_errors=True)
    if verbose:
        for r in rep:
            print("%-12s %5.1f s cpu  %4d of %4d records out on %d lines %s  worst %.2f of a band  %s  [%s]" % (r[0], r[2], r[3], r[4], len(r[5]), ",".join(r[5][:6]), r[6], r[1], r[7]), flush=True)
        print("ACCEPTED" if ok_all and rep else "NOT ACCEPTED")
    return ok_all, rep

if __name__ == "__main__":
    a = sys.argv[1:]
    grade(a[0], float(a[1]) if len(a) > 1 else 60.0, visible=len(a) > 2 and a[2] == "visible")
