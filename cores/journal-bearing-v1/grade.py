"""grade.py PROGRAM HIDDEN_DIR [LIMIT_S]: run the program on every hidden case under the limit and compare."""
import csv, os, shutil, subprocess, sys, tempfile, time

BANDS = {"h_min_um": ("rel", 0.015), "power_kW": ("rel", 0.015), "p_max_MPa": ("rel", 0.015),
         "attitude_deg": ("abs", 1.0), "t_eff_C": ("abs", 0.5)}

def grade(program, hidden, limit=60.0, verbose=True):
    ok_all = True; report = []
    for name in sorted(os.listdir(hidden)):
        case = os.path.join(hidden, name)
        if not os.path.exists(os.path.join(case, "truth.csv")): continue
        box = tempfile.mkdtemp(prefix="jb_run_")
        shutil.copy(program, os.path.join(box, "bearing.py"))
        inp = os.path.join(box, "case"); os.makedirs(inp)
        for f in ("datasheet.json", "history.csv", "oil_samples.csv", "points.csv"): shutil.copy(os.path.join(case, f), inp)
        out = os.path.join(box, "out.csv")
        env = dict(PATH=os.environ["PATH"], OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
        t = time.time(); status = "ran"
        try:
            p = subprocess.run(["taskset", "-c", "0", sys.executable, "-I", "bearing.py", inp, out], cwd=box, env=env,
                               capture_output=True, text=True, timeout=limit)
            if p.returncode != 0: status = "crashed: " + (p.stderr.strip().splitlines() or ["?"])[-1][:80]
        except subprocess.TimeoutExpired:
            status = "timed out"
        dt = time.time() - t
        bad, worst, n = 0, {}, 0
        if status == "ran":
            truth = {r["point"]: r for r in csv.DictReader(open(os.path.join(case, "truth.csv")))}
            try:
                got = {r["point"]: r for r in csv.DictReader(open(out))}
            except Exception as e:
                got = {}; status = "no output"
            for pt, tr in truth.items():
                n += 1; miss = False
                for k, (kind, band) in BANDS.items():
                    try:
                        g = float(got[pt][k]); tv = float(tr[k])
                        err = abs(g - tv) / abs(tv) if kind == "rel" else abs(g - tv)
                        if not err == err: err = 9e9
                    except Exception:
                        err = 9e9
                    worst[k] = max(worst.get(k, 0.0), err / band)
                    miss |= err > band
                bad += miss
        good = status == "ran" and bad == 0
        ok_all &= good
        report.append((name, status, round(dt, 1), bad, n, {k: round(v, 2) for k, v in worst.items()}))
        shutil.rmtree(box, ignore_errors=True)
    if verbose:
        for r in report:
            print("%-18s %-10s %5.1f s  %3d of %3d points out  worst/band %s" % r)
        print("ACCEPTED" if ok_all else "NOT ACCEPTED")
    return ok_all, report

if __name__ == "__main__":
    grade(sys.argv[1], sys.argv[2], float(sys.argv[3]) if len(sys.argv) > 3 else 60.0)
