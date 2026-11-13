#!/usr/bin/env python3
"""grade.py PROGRAM [--limit SECONDS] [--visible]: runs a rodlift program on the hidden fields of the core, one
run a field, each under the per-run limit on one CPU, and compares every setting with the sealed results.
A run over the limit ends the assessment: nothing it wrote is read and the program is not accepted."""
import csv, os, shutil, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
LIMIT = 45.0
TOL_STROKE, TOL_LIQUID, TOL_LOAD = 0.03, 0.03, 0.03
HEAD = ["setting", "plunger_stroke_m", "liquid_m3_d", "pprl_kN", "mprl_kN"]


def run(prog, field_dir, limit):
    tmp = tempfile.mkdtemp(prefix="rp_")
    try:
        shutil.copy(prog, os.path.join(tmp, "rodlift.py"))
        out = os.path.join(tmp, "out.csv")
        env = dict(os.environ, OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
        cmd = ["python3", "rodlift.py", field_dir, out]
        if shutil.which("taskset"):
            cmd = ["taskset", "-c", "0"] + cmd
        t = time.time()
        try:
            p = subprocess.run(cmd, cwd=tmp, env=env, timeout=limit, capture_output=True, text=True)
        except subprocess.TimeoutExpired:
            return None, time.time() - t, "over the limit"
        dt = time.time() - t
        if p.returncode != 0:
            return None, dt, "exit status %d: %s" % (p.returncode, p.stderr.strip().splitlines()[-1:] or "")
        if not os.path.exists(out):
            return None, dt, "no table written"
        rows = list(csv.reader(open(out)))
        return rows, dt, ""
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def compare(rows, truth_csv):
    if not rows or rows[0] != HEAD:
        return None, "header is not " + ",".join(HEAD)
    got = {}
    for r in rows[1:]:
        if not r:
            continue
        try:
            got[r[0]] = [float(v) for v in r[1:5]]
        except (ValueError, IndexError):
            return None, "row not readable: %r" % (r,)
    truth = list(csv.DictReader(open(truth_csv)))
    if set(got) != {t["setting"] for t in truth}:
        return None, "the table's settings are not the package's"
    bad = {}
    n_out = 0
    for t in truth:
        g = got[t["setting"]]
        st, lq, pp, mp = (float(t[k]) for k in HEAD[1:])
        e = (abs(g[0] / st - 1) / TOL_STROKE, abs(g[1] / lq - 1) / TOL_LIQUID, abs(g[2] - pp) / pp / TOL_LOAD,
             abs(g[3] - mp) / pp / TOL_LOAD)
        well = t["setting"].rsplit("-", 1)[0]
        b = bad.setdefault(well, [0, 0, [0.0] * 4])
        b[1] += 1
        if not all(x <= 1.0 and x == x for x in e):
            b[0] += 1; n_out += 1
        b[2] = [max(a, x if x == x else 9e9) for a, x in zip(b[2], e)]
    return (n_out, len(truth), bad), ""


def main():
    prog = os.path.abspath(sys.argv[1])
    limit = LIMIT
    if "--limit" in sys.argv:
        limit = float(sys.argv[sys.argv.index("--limit") + 1])
    sets = []
    if "--visible" in sys.argv:
        ex = os.path.join(HERE, "core", "environment", "data", "examples")
        sets += [(n, os.path.join(ex, n), os.path.join(ex, n, "expected.csv")) for n in sorted(os.listdir(ex))]
        pe = os.path.join(HERE, "core", "environment", "data", "pending")
        sets += [(n, os.path.join(pe, n), os.path.join(HERE, "core", "truth", n + ".csv")) for n in sorted(os.listdir(pe))]
    else:
        hd = os.path.join(HERE, "core", "hidden")
        sets += [(n, os.path.join(hd, n), os.path.join(HERE, "core", "truth", n + ".csv")) for n in sorted(os.listdir(hd))]
    accepted = True
    for name, d, truth in sets:
        rows, dt, why = run(prog, d, limit)
        if rows is None:
            print("%-12s %5.1f s  NOT ACCEPTED: %s" % (name, dt, why))
            accepted = False
            if why == "over the limit":
                break
            continue
        res, why = compare(rows, truth)
        if res is None:
            print("%-12s %5.1f s  NOT ACCEPTED: %s" % (name, dt, why)); accepted = False; continue
        n_out, n, bad = res
        worst = [max(b[2][i] for b in bad.values()) for i in range(4)]
        print("%-12s %5.1f s  settings out %4d of %4d   worst, in bands: stroke %.2f liquid %.2f pprl %.2f mprl %.2f" %
              (name, dt, n_out, n, *worst))
        for w, b in sorted(bad.items()):
            if b[0]:
                print("      %s  %3d of %3d out   stroke %.2f liquid %.2f pprl %.2f mprl %.2f" % (w, b[0], b[1], *b[2]))
        accepted = accepted and n_out == 0
    print("ACCEPTED" if accepted else "NOT ACCEPTED")
    return 0 if accepted else 1


if __name__ == "__main__":
    sys.exit(main())
