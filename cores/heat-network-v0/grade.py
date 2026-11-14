"""grade.py PROGRAM [LIMIT_S] [visible]: run a heatnet.py on the six hidden networks (or the three visible ones)
the way the tests would: a scratch directory holding the program alone, one thread to numerical libraries, the
CPU time of the run against the limit."""
import csv, os, resource, shutil, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "core", "environment", "data")
BAND_T, BAND_SHARE, BAND_FLOOR = 0.01, 1e-4, 0.01
HIDDEN = ["north_bank", "west_hill", "old_town", "river_side", "east_gate", "south_docks"]


def judge(program, limit, visible=False):
    sets = ([(os.path.join(DATA, "examples", n), os.path.join(DATA, "examples", n, "expected.csv")) for n in ("harbour_east", "mill_quarter")]
            if visible else [(os.path.join(HERE, "hidden", n), os.path.join(HERE, "hidden", "_result_%s.csv" % n)) for n in HIDDEN])
    ok = True
    for pkg, exp in sets:
        room = tempfile.mkdtemp(prefix="hn_grade_")
        shutil.copy(program, os.path.join(room, "heatnet.py"))
        out = os.path.join(room, "out.csv")
        env = dict(os.environ, OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
        r0 = resource.getrusage(resource.RUSAGE_CHILDREN); t = time.time()
        try:
            p = subprocess.run([sys.executable, "heatnet.py", pkg, out], cwd=room, env=env, capture_output=True, text=True, timeout=3 * limit)
            code = p.returncode; err = p.stderr
        except subprocess.TimeoutExpired:
            code = None; err = ""
        wall = time.time() - t; r1 = resource.getrusage(resource.RUSAGE_CHILDREN)
        cpu = (r1.ru_utime - r0.ru_utime) + (r1.ru_stime - r0.ru_stime)
        name = os.path.basename(pkg)
        if code is None or cpu > limit:
            print("  %-13s over the limit (%.1f s CPU, %.1f s wall)" % (name, cpu, wall)); ok = False; break
        if code != 0:
            print("  %-13s exit status %s: %s" % (name, code, (err.strip().splitlines() or [""])[-1][:120])); ok = False; continue
        want = {r["point"]: float(r["value"]) for r in csv.DictReader(open(exp))}
        try:
            got = {r["point"]: float(r["value"]) for r in csv.DictReader(open(out))}
        except Exception as e:
            print("  %-13s no table (%s)" % (name, e)); ok = False; continue
        out_n = 0; worst = 0.0
        for k, w in want.items():
            g = got.get(k)
            band = BAND_T if k.endswith("-T") else max(BAND_SHARE * abs(w), BAND_FLOOR)
            e = abs(g - w) / band if g is not None else 9e9
            worst = max(worst, e); out_n += e > 1.0
        print("  %-13s %5.1f s CPU %5.1f s wall  %5d of %5d points out of band  worst %.3g of the band" % (name, cpu, wall, out_n, len(want), worst))
        ok &= out_n == 0
        shutil.rmtree(room, ignore_errors=True)
    print("accepted" if ok else "not accepted")
    return ok


if __name__ == "__main__":
    judge(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 12.0, len(sys.argv) > 3)
