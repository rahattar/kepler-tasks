"""The reference program (solution/chatter.py) through tests/grade.py on the seven hidden jobs, as the verifier runs
it; and as a command on the example.

    python3 authoring/evidence/reference.py > authoring/evidence/reference.txt
"""
import json, os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

T = C.truth()
print("Reference program solution/chatter.py through tests/grade.py (run as %s); a job is right when its stability limit "
      "is within %.0f percent of the truth.\n" % ("nobody" if C.AS_NOBODY else "the current user", 100 * C.G.TOL))
out = tempfile.mktemp(suffix=".json")
subprocess.run([sys.executable, "-I", C.REFERENCE, C.EXAMPLE, out], check=True)
print("Example job-ex: %.4f mm\n" % json.load(open(out))["stable_depth_mm"])
r = C.verify(C.REFERENCE)
print("%-16s %10s %10s %8s %10s %8s %6s" % ("job", "limit mm", "true mm", "ratio", "speed rpm", "teeth", "right"))
for p in sorted(T):
    v = r["packages"][p]
    print("%-16s %10.4f %10.4f %8.4f %10d %8d %6s" % (p, v["stable_depth_mm"], v["true_mm"], v["ratio"], T[p]["job"]["speed_rpm"],
          T[p]["job"]["teeth"], v["right"]))
dev = [abs(v["ratio"] - 1) for v in r["packages"].values()]
print("\njobs %d; wrong %d (%s); largest deviation from the truth %.4f" % (r["jobs"], r["wrong"], "accepted" if r["accepted"] else "rejected", max(dev)))
print("true stability limits of the hidden jobs: %s mm" % "; ".join("%s %.3f" % (p, T[p]["stable_depth_mm"]) for p in sorted(T)))
