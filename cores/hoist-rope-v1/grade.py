#!/usr/bin/env python3
"""grade.py PROGRAM [--visible]: runs a ropes program on the core's hidden works and compares the damage at
every station with the sealed result, within 6 per cent of the greatest damage of that rope."""
import csv, os, shutil, subprocess, sys, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__))


def run(prog, d, limit=60):
    tmp = tempfile.mkdtemp(prefix="hr_")
    try:
        shutil.copy(prog, os.path.join(tmp, "ropes.py")); out = os.path.join(tmp, "out.csv"); t = time.time()
        try:
            p = subprocess.run(["python3", "ropes.py", d, out], cwd=tmp, timeout=limit, capture_output=True, text=True)
        except subprocess.TimeoutExpired:
            return None, time.time() - t, "over the limit"
        if p.returncode != 0 or not os.path.exists(out):
            return None, time.time() - t, "exit %d %s" % (p.returncode, p.stderr.strip().splitlines()[-1:])
        return list(csv.reader(open(out))), time.time() - t, ""
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    prog = os.path.abspath(sys.argv[1]); c = os.path.join(HERE, "core")
    if "--visible" in sys.argv:
        ex = os.path.join(c, "environment", "data", "examples"); pe = os.path.join(c, "environment", "data", "pending")
        sets = [(n, os.path.join(ex, n), os.path.join(ex, n, "expected.csv")) for n in sorted(os.listdir(ex))]
        sets += [(n, os.path.join(pe, n), os.path.join(c, "truth", n + ".csv")) for n in sorted(os.listdir(pe))]
    else:
        hd = os.path.join(c, "hidden")
        sets = [(n, os.path.join(hd, n), os.path.join(c, "truth", n + ".csv")) for n in sorted(os.listdir(hd))]
    ok = True
    for name, d, truth in sets:
        rows, dt, why = run(prog, d)
        if rows is None or rows[0] != ["row", "damage"]:
            print("%-12s %5.1f s NOT ACCEPTED: %s" % (name, dt, why or "header")); ok = False; continue
        try:
            got = {r[0]: float(r[1]) for r in rows[1:] if r}
        except (ValueError, IndexError):
            print("%-12s NOT ACCEPTED: row not readable" % name); ok = False; continue
        tr = {r["row"]: float(r["damage"]) for r in csv.DictReader(open(truth))}
        if set(got) != set(tr):
            print("%-12s NOT ACCEPTED: rows are not the package's" % name); ok = False; continue
        by = {}
        for k, v in tr.items():
            by.setdefault(k.rsplit("-", 1)[0], []).append((v, got[k]))
        line = []; n_out = 0
        for cr, pairs in sorted(by.items()):
            mx = max(v for v, _ in pairs)
            e = [abs(g - v) / mx / 0.06 if g == g else 9e9 for v, g in pairs]
            bad = sum(x > 1 for x in e); n_out += bad
            line.append("%s %d/%d worst %.2f" % (cr, bad, len(e), max(e)))
        print("%-12s %5.1f s  stations out %3d of %3d | %s" % (name, dt, n_out, len(tr), "; ".join(line)))
        ok = ok and n_out == 0
    print("ACCEPTED" if ok else "NOT ACCEPTED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
