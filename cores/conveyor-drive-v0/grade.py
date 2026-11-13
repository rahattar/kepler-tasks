#!/usr/bin/env python3
"""grade.py PROGRAM [--visible] [--limit S]: runs a drives program on the core's hidden lines, one run a line,
and compares every row with the sealed results: mean, greatest and least power within 4 per cent of the drive's rated
power, peak traction ratio within 3 per cent."""
import csv, os, shutil, subprocess, sys, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__))
HEAD = ["row", "mean_kW", "max_kW", "min_kW", "traction_peak"]


def run(prog, d, limit):
    tmp = tempfile.mkdtemp(prefix="cv_")
    try:
        shutil.copy(prog, os.path.join(tmp, "drives.py"))
        out = os.path.join(tmp, "out.csv"); t = time.time()
        try:
            p = subprocess.run(["python3", "drives.py", d, out], cwd=tmp, timeout=limit, capture_output=True, text=True,
                               env=dict(os.environ, OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1"))
        except subprocess.TimeoutExpired:
            return None, time.time() - t, "over the limit"
        if p.returncode != 0:
            return None, time.time() - t, "exit status %d %s" % (p.returncode, p.stderr.strip().splitlines()[-1:])
        return (list(csv.reader(open(out))) if os.path.exists(out) else None), time.time() - t, "no table"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def compare(rows, d, truth_csv):
    if not rows or rows[0] != HEAD:
        return None, "header"
    rated = {(r["flight"], r["drive"]): float(r["rated_kW"]) for r in csv.DictReader(open(os.path.join(d, "drives.csv")))}
    try:
        got = {r[0]: [float(x) for x in r[1:5]] for r in rows[1:] if r}
    except (ValueError, IndexError):
        return None, "row not readable"
    truth = list(csv.DictReader(open(truth_csv)))
    if set(got) != {t["row"] for t in truth}:
        return None, "rows are not the package's"
    by = {}
    for t in truth:
        fl, role, _ = t["row"].rsplit("-", 2)
        pr = rated[(fl, role)]; g = got[t["row"]]
        e = (abs(g[0] - float(t["mean_kW"])) / pr / 0.04, max(abs(g[1] - float(t["max_kW"])), abs(g[2] - float(t["min_kW"]))) / pr / 0.04,
             abs(g[3] / float(t["traction_peak"]) - 1) / 0.03)
        b = by.setdefault((fl, role), [0, 0, [0.0, 0.0, 0.0]])
        b[1] += 1; b[0] += not all(x <= 1 for x in e)
        b[2] = [max(a, x if x == x else 9e9) for a, x in zip(b[2], e)]
    return by, ""


def main():
    prog = os.path.abspath(sys.argv[1]); limit = 30.0
    if "--limit" in sys.argv:
        limit = float(sys.argv[sys.argv.index("--limit") + 1])
    c = os.path.join(HERE, "core")
    if "--visible" in sys.argv:
        ex = os.path.join(c, "environment", "data", "examples"); pe = os.path.join(c, "environment", "data", "pending")
        sets = [(n, os.path.join(ex, n), os.path.join(ex, n, "expected.csv")) for n in sorted(os.listdir(ex))]
        sets += [(n, os.path.join(pe, n), os.path.join(c, "truth", n + ".csv")) for n in sorted(os.listdir(pe))]
    else:
        hd = os.path.join(c, "hidden")
        sets = [(n, os.path.join(hd, n), os.path.join(c, "truth", n + ".csv")) for n in sorted(os.listdir(hd))]
    ok = True
    for name, d, truth in sets:
        rows, dt, why = run(prog, d, limit)
        by, why2 = compare(rows, d, truth) if rows else (None, why)
        if by is None:
            print("%-12s %5.1f s  NOT ACCEPTED: %s" % (name, dt, why2 or why)); ok = False; continue
        n_out = sum(b[0] for b in by.values()); n = sum(b[1] for b in by.values())
        print("%-12s %5.1f s  rows out %4d of %4d   worst, in bands: mean %.2f max/min %.2f traction %.2f" %
              (name, dt, n_out, n, *[max(b[2][i] for b in by.values()) for i in range(3)]))
        for k, b in sorted(by.items()):
            if b[0]:
                print("      %s %-5s %3d of %3d out   mean %.2f max/min %.2f traction %.2f" % (k[0], k[1], b[0], b[1], *b[2]))
        ok = ok and n_out == 0
    print("ACCEPTED" if ok else "NOT ACCEPTED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
