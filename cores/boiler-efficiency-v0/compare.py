"""compare.py PROGRAM: runs PROGRAM on every boiler and reports departures in bands (0.15 points, 1 per cent)."""
import os, subprocess, sys, tempfile, time
import pandas as pd
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
places = [(os.path.join(ROOT, "environment/data/examples", n), os.path.join(ROOT, "environment/data/examples", n, "expected.csv"))
          for n in sorted(os.listdir(os.path.join(ROOT, "environment/data/examples")))]
places += [(os.path.join(ROOT, "environment/data/pending", n), os.path.join(ROOT, "authoring/provenance/pending_results", n + ".csv"))
           for n in sorted(os.listdir(os.path.join(ROOT, "environment/data/pending")))]
places += [(os.path.join(ROOT, "tests/boilers", n), os.path.join(ROOT, "tests/sealed/results", n + ".csv"))
           for n in sorted(os.listdir(os.path.join(ROOT, "tests/boilers")))]
prog = sys.argv[1]
allok = True
for pkg, truth in places:
    out = tempfile.mktemp(suffix=".csv")
    t0 = time.process_time(); w0 = time.time()
    p = subprocess.run([sys.executable, prog, pkg, out], capture_output=True, text=True)
    took = time.time() - w0
    if p.returncode:
        print(os.path.basename(pkg), "FAILED", p.stderr[-400:]); allok = False; continue
    a = pd.read_csv(out).set_index("date"); b = pd.read_csv(truth).set_index("date")
    a = a.reindex(b.index)
    de = (a.efficiency_pct - b.efficiency_pct).abs() / 0.15
    dc = ((a.coal_t - b.coal_t).abs() / b.coal_t) / 0.01
    bad = ((de > 1) | (dc > 1) | a.isna().any(axis=1)).sum()
    allok &= bad == 0
    print("%-10s %5.2f s  eff worst %6.2f  coal worst %6.2f  days out %3d of %d" % (os.path.basename(pkg), took, de.max(), dc.max(), bad, len(b)))
    os.remove(out)
print("ALL IN BAND" if allok else "NOT ALL IN BAND")
