"""The reference program (solution/pumpdown.py) through tests/grade.py on the seven hidden chambers, as the verifier
runs it; and as a command on the example.

    python3 authoring/evidence/reference.py > authoring/evidence/reference.txt
"""
import json, os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

T = C.truth()
print("Reference program solution/pumpdown.py through tests/grade.py (run as %s); a chamber is right when its job's "
      "pump-down time is within %.0f percent of the truth.\n" % ("nobody" if C.AS_NOBODY else "the current user", 100 * C.G.TOL))
out = tempfile.mktemp(suffix=".json")
subprocess.run([sys.executable, "-I", C.REFERENCE, C.EXAMPLE, out], check=True)
print("Example chamber-ex: %.2f min\n" % json.load(open(out))["pumpdown_min"])
r = C.verify(C.REFERENCE)
print("%-16s %10s %10s %8s %8s %10s %10s %6s" % ("chamber", "time min", "true min", "ratio", "turbo", "crossover", "leak", "right"))
for p in sorted(T):
    v = r["packages"][p]
    c = T[p]["chamber"]
    print("%-16s %10.2f %10.2f %8.4f %8s %10g %10.1e %6s" % (p, v["pumpdown_min"], v["true_min"], v["ratio"], c["turbo"], c["p_x"], c["leak"], v["right"]))
dev = [abs(v["ratio"] - 1) for v in r["packages"].values()]
print("\nchambers %d; wrong %d (%s); largest deviation from the truth %.2f percent" % (r["jobs"], r["wrong"], "accepted" if r["accepted"] else "rejected", 100 * max(dev)))
print("true pump-down times of the hidden jobs: %s min" % "; ".join("%s %.1f" % (p, T[p]["pumpdown_min"]) for p in sorted(T)))
