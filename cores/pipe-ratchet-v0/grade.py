#!/usr/bin/env python3
"""grade.py PROGRAM [--visible] [--limit S]: runs a ratchet program on the core's hidden works (or the visible
ones) from a scratch directory holding a copy of it alone, and holds every checkpoint to the sealed result:
within BAND of the greatest ratchet strain of that line. CPU time of the run (user + system of the child) is
held to the limit as well as the clock."""
import csv, os, resource, shutil, subprocess, sys, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__))
BAND = 0.03
LIMIT = 15.0


def run(prog, d, limit):
    tmp = tempfile.mkdtemp(prefix="pr_")
    try:
        shutil.copy(prog, os.path.join(tmp, "ratchet.py")); out = os.path.join(tmp, "out.csv")
        before = resource.getrusage(resource.RUSAGE_CHILDREN); t = time.time()
        try:
            p = subprocess.run(["python3", "ratchet.py", d, out], cwd=tmp, timeout=2 * limit + 5, capture_output=True, text=True,
                               env=dict(os.environ, OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1"))
        except subprocess.TimeoutExpired:
            return None, time.time() - t, 2 * limit + 5, "over the limit (clock)"
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        cpu = (after.ru_utime - before.ru_utime) + (after.ru_stime - before.ru_stime)
        if cpu > limit:
            return None, time.time() - t, cpu, "over the limit (%.1f s of CPU)" % cpu
        if p.returncode != 0 or not os.path.exists(out):
            return None, time.time() - t, cpu, "exit %d %s" % (p.returncode, p.stderr.strip().splitlines()[-1:])
        return list(csv.reader(open(out))), time.time() - t, cpu, ""
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    prog = os.path.abspath(args[0]); c = os.path.join(HERE, "core")
    limit = float(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else LIMIT
    if "--visible" in sys.argv:
        ex = os.path.join(c, "environment", "data", "examples"); pe = os.path.join(c, "environment", "data", "pending")
        sets = [(n, os.path.join(ex, n), os.path.join(ex, n, "expected.csv")) for n in sorted(os.listdir(ex))]
        sets += [(n, os.path.join(pe, n), os.path.join(c, "truth", n + ".csv")) for n in sorted(os.listdir(pe))]
    else:
        hd = os.path.join(c, "hidden")
        sets = [(n, os.path.join(hd, n), os.path.join(c, "truth", n + ".csv")) for n in sorted(os.listdir(hd))]
    ok = True
    for name, d, truth in sets:
        rows, dt, cpu, why = run(prog, d, limit)
        if rows is None or rows[0] != ["row", "ratchet_pct"]:
            print("%-13s %5.1f s NOT ACCEPTED: %s" % (name, cpu, why or "header")); ok = False; continue
        try:
            got = {r[0]: float(r[1]) for r in rows[1:] if r}
        except (ValueError, IndexError):
            print("%-13s NOT ACCEPTED: unreadable row" % name); ok = False; continue
        tr = {r["row"]: float(r["ratchet_pct"]) for r in csv.DictReader(open(truth))}
        if set(got) != set(tr):
            print("%-13s NOT ACCEPTED: rows are not the package's (%d of %d)" % (name, len(set(got) & set(tr)), len(tr))); ok = False; continue
        by = {}
        for k, v in tr.items():
            by.setdefault(k.rsplit("-", 1)[0], []).append((k, v))
        parts, out = [], 0
        for line in sorted(by):
            top = max(abs(v) for _, v in by[line])
            bad = sum(abs(got[k] - v) > BAND * top for k, v in by[line])
            worst = max(abs(got[k] - v) for k, v in by[line]) / (BAND * top)
            out += bad
            parts.append("%s %d/%d %.2f" % (line, bad, len(by[line]), worst))
        ok = ok and out == 0
        print("%-13s %5.1f s CPU  out %3d of %4d | %s" % (name, cpu, out, len(tr), "; ".join(parts)))
    print("ACCEPTED" if ok else "NOT ACCEPTED")


if __name__ == "__main__":
    main()
