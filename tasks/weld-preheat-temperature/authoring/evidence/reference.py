"""The reference program (solution/preheat.py) through tests/grade.py on the seven hidden joints, as the verifier
runs it; and as a command on the example.

    python3 authoring/evidence/reference.py > authoring/evidence/reference.txt
"""
import json, os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

T = C.truth()
print("Reference program solution/preheat.py through tests/grade.py (run as %s); a joint is right when its minimum "
      "preheat is within %.0f C of the truth.\n" % ("nobody" if C.AS_NOBODY else "the current user", C.G.TOL_C))
out = tempfile.mktemp(suffix=".json")
subprocess.run([sys.executable, "-I", C.REFERENCE, C.EXAMPLE, out], check=True)
print("Example joint-ex: %.2f C\n" % json.load(open(out))["min_preheat_c"])
r = C.verify(C.REFERENCE)
print("%-16s %10s %10s %8s %12s %12s %6s" % ("joint", "preheat C", "true C", "dev C", "hydrogen C", "hardness C", "right"))
for p in sorted(T):
    v = r["packages"][p]
    pl = T[p]["joint"]["plates"]
    print("%-16s %10.2f %10.2f %+8.2f %12.1f %12.1f %6s" % (p, v["min_preheat_c"], v["true_c"], v["dev_c"],
          max(x["hydrogen_c"] for x in pl), max(x["hardness_c"] for x in pl), v["right"]))
dev = [abs(v["dev_c"]) for v in r["packages"].values()]
print("\njoints %d; wrong %d (%s); largest deviation from the truth %.2f C" % (r["jobs"], r["wrong"], "accepted" if r["accepted"] else "rejected", max(dev)))
print("true minimum preheats of the hidden joints: %s C" % "; ".join("%s %.1f" % (p, T[p]["min_preheat_c"]) for p in sorted(T)))
