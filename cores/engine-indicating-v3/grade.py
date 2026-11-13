"""grade.py PROGRAM [LIMIT_S] [--examples]: runs PROGRAM on the hidden cells (or the examples) and compares with the sealed results."""
import csv, os, subprocess, sys, tempfile, time, shutil
HERE = os.path.dirname(os.path.abspath(__file__))
CORE = os.path.join(HERE, "core")
BANDS = dict(imep_bar=("rel", 0.015, 0.03), pmax_bar=("rel", 0.01, 0.0), apmax_deg=("abs", 0.25), ca10_deg=("abs", 0.25),
             ca50_deg=("abs", 0.25), q_gross_J=("rel", 0.025, 0.0))


def read(path):
    rows = list(csv.DictReader(open(path)))
    return {(r["point"], r["cylinder"]): r for r in rows}


def compare(got, want):
    bad, worst = 0, {}
    for key, w in want.items():
        g = got.get(key)
        ok = g is not None
        for col, band in BANDS.items():
            if w[col] == "":
                continue
            try:
                gv, wv = float(g[col]), float(w[col])
            except Exception:
                ok = False
                continue
            lim = max(band[1] * abs(wv), band[2]) if band[0] == "rel" else band[1]
            ratio = abs(gv - wv) / lim
            worst[col] = max(worst.get(col, 0.0), ratio)
            if not ratio <= 1.0:
                ok = False
        bad += not ok
    return bad, worst


def main():
    prog = os.path.abspath(sys.argv[1])
    limit = float(sys.argv[2]) if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else 30.0
    if "--examples" in sys.argv:
        cells = [(os.path.join(CORE, "environment/data/examples", c), os.path.join(CORE, "environment/data/examples", c, "expected.csv"))
                 for c in sorted(os.listdir(os.path.join(CORE, "environment/data/examples")))]
    else:
        cells = [(os.path.join(CORE, "hidden", c), os.path.join(CORE, "truth", c + ".csv")) for c in sorted(os.listdir(os.path.join(CORE, "hidden")))]
    env = dict(os.environ, OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
    failed = 0
    for pkg, truth in cells:
        tmp = tempfile.mkdtemp()
        shutil.copy(prog, os.path.join(tmp, "indicate.py"))
        out = os.path.join(tmp, "out.csv")
        t = time.time()
        try:
            r = subprocess.run(["taskset", "-c", "0", sys.executable, "indicate.py", pkg, out], cwd=tmp, env=env, timeout=limit,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        except subprocess.TimeoutExpired:
            print("%-8s over the limit of %.0f s: not accepted" % (os.path.basename(pkg), limit))
            failed += 1
            continue
        dt = time.time() - t
        if r.returncode != 0 or not os.path.exists(out):
            print("%-8s exit %d %s" % (os.path.basename(pkg), r.returncode, r.stderr.strip()[-300:]))
            failed += 1
            continue
        try:
            bad, worst = compare(read(out), read(truth))
        except Exception as ex:
            print("%-8s unreadable table: %r" % (os.path.basename(pkg), ex))
            failed += 1
            continue
        n = len(read(truth))
        print("%-8s %5.1f s  rows out %3d of %3d  worst/band %s  %s" % (os.path.basename(pkg), dt, bad, n,
              " ".join("%s %.2f" % (k.split("_")[0], v) for k, v in worst.items()), r.stderr.strip()[-60:]))
        failed += bad > 0
        shutil.rmtree(tmp, ignore_errors=True)
    print("ACCEPTED" if failed == 0 else "not accepted: %d of %d cells" % (failed, len(cells)))


if __name__ == "__main__":
    main()
