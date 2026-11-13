"""grade.py PROGRAM [HIDDEN_DIR] [LIMIT_S]: run the program on every hidden site and compare with truth.csv
(pressure drop within 1.5 per cent, outlet temperature within 0.5 K).
The limit is on CPU time (user plus system) because the probe machine is shared; a run over it is killed."""
import csv, os, resource, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
BAND_DP = 0.015; BAND_T = 0.5
FILES = ("site.json", "oils.csv", "lines.csv", "records.csv")

def run_one(program, case, limit):
    box = tempfile.mkdtemp(prefix="ol_run_")
    shutil.copy(program, os.path.join(box, "lines.py"))
    inp = os.path.join(box, "pkg"); os.makedirs(inp)
    for f in FILES: shutil.copy(os.path.join(case, f), inp)
    out = os.path.join(box, "out.csv")
    env = dict(PATH=os.environ["PATH"], OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
    def lim():
        resource.setrlimit(resource.RLIMIT_CPU, (int(limit), int(limit) + 1))
    r0 = resource.getrusage(resource.RUSAGE_CHILDREN)
    status = "ran"
    try:
        p = subprocess.run([sys.executable, "lines.py", inp, out], cwd=box, env=env, capture_output=True, text=True,
                           timeout=limit * 6, preexec_fn=lim)
        if p.returncode < 0: status = "timed out (cpu)"
        elif p.returncode != 0: status = "crashed: " + (p.stderr.strip().splitlines() or ["?"])[-1][:90]
    except subprocess.TimeoutExpired:
        status = "timed out (wall)"
    r1 = resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu = (r1.ru_utime + r1.ru_stime) - (r0.ru_utime + r0.ru_stime)
    got = {}
    if status == "ran":
        try:
            got = {r["record"]: r for r in csv.DictReader(open(out))}
        except Exception:
            status = "no output"
    shutil.rmtree(box, ignore_errors=True)
    return status, cpu, got

def compare(got, truth_path):
    bad = 0; n = 0; worst = {"dp_kPa": 0.0, "t_out_C": 0.0}; bad_un = 0; un = 0
    for tr in csv.DictReader(open(truth_path)):
        n += 1; miss = False
        u = int(tr.get("uneven", 0))
        for k in worst:
            try:
                g = float(got[tr["record"]][k]); t = float(tr[k])
                err = abs(g - t) / abs(t) / BAND_DP if k == "dp_kPa" else abs(g - t) / BAND_T
                if not err == err: err = 9e9
            except Exception:
                err = 9e9
            worst[k] = max(worst[k], err); miss |= err > 1.0
        bad += miss; un += u; bad_un += miss and u
    return bad, n, worst, bad_un, un

def grade(program, hidden=None, limit=60.0, verbose=True):
    hidden = hidden or os.path.join(HERE, "core", "hidden")
    ok_all = True; rep = []
    for name in sorted(os.listdir(hidden)):
        case = os.path.join(hidden, name)
        tp = os.path.join(case, "truth.csv")
        if not os.path.exists(tp): tp = os.path.join(case, "expected.csv")
        if not os.path.exists(tp): continue
        status, cpu, got = run_one(program, case, limit)
        bad, n, worst, bad_thin, thin = compare(got, tp) if status == "ran" else (0, 0, {}, 0, 0)
        good = status == "ran" and bad == 0
        ok_all &= good
        rep.append((name, status, cpu, bad, n, worst, bad_thin, thin))
        if verbose:
            print("%-13s %5.1f s cpu  %4d of %4d records out (%d of the %d with one pipe stalled)  %s  worst/band %s" % (
                name, cpu, bad, n, bad_thin, thin, status, {k: round(v, 2) for k, v in worst.items()}), flush=True)
    if verbose: print("ACCEPTED" if ok_all else "NOT ACCEPTED")
    return ok_all, rep

if __name__ == "__main__":
    a = sys.argv
    grade(a[1], a[2] if len(a) > 2 and a[2] != "-" else None, float(a[3]) if len(a) > 3 else 60.0)
