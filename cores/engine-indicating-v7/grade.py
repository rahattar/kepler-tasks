"""Grade a program on the trial cells (hidden and example), printing what it found and the widest departure."""
import csv, subprocess, sys, tempfile, os
sys.dont_write_bytecode = True
BANDS = {"imep_bar": ("s", 0.02), "pmax_bar": ("s", 0.01), "apmax_deg": ("u", 0.3), "ca10_deg": ("u", 0.3), "ca50_deg": ("u", 0.3), "q_gross_J": ("s", 0.03)}
prog, root = sys.argv[1], sys.argv[2]
cells = [(n, os.path.join(root, "tests/cells", n), os.path.join(root, "tests/sealed/results", n + ".csv")) for n in sorted(os.listdir(os.path.join(root, "tests/cells")))]
cells += [(n, os.path.join(root, "environment/data/examples", n), os.path.join(root, "environment/data/examples", n, "expected.csv")) for n in sorted(os.listdir(os.path.join(root, "environment/data/examples")))]
if len(sys.argv) > 3:
    cells = [c for c in cells if c[0] in sys.argv[3:]]
ok = True
for name, pkg, truth in cells:
    out = tempfile.mktemp(suffix=".csv")
    r = subprocess.run([sys.executable, "-B", prog, pkg, out], capture_output=True, text=True)
    if r.returncode:
        print(name, "FAILED", r.stderr[-400:]); ok = False; continue
    got = {(row["point"], row["cylinder"]): row for row in csv.DictReader(open(out))}
    worst, bad = {}, 0
    for row in csv.DictReader(open(truth)):
        g = got[(row["point"], row["cylinder"])]
        rowbad = False
        for k, (kind, w) in BANDS.items():
            t, v = float(row[k]), float(g[k])
            d = abs(v - t) / (w * abs(t) if kind == "s" else w)
            worst[k] = max(worst.get(k, 0), d)
            rowbad |= d > 1
        bad += rowbad
    ok &= bad == 0
    print("%-8s rows out %2d  widest %s  | %s" % (name, bad, " ".join("%s %.2f" % (k.split("_")[0], v) for k, v in worst.items()), r.stderr.strip()[-150:]))
print("ALL IN" if ok else "NOT ALL IN")
