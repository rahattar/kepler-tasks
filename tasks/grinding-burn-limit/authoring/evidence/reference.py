"""The reference program (solution/burn.py) through tests/grade.py on the seven hidden jobs, as the verifier runs
it; and as a command on the example.

    python3 authoring/evidence/reference.py > authoring/evidence/reference.txt
"""
import json, os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

T = C.truth()
print("Reference program solution/burn.py through tests/grade.py (run as %s); a job is right when its burn-limited "
      "depth is within %.0f percent of the truth.\n" % ("nobody" if C.AS_NOBODY else "the current user", 100 * C.G.TOL))
out = tempfile.mktemp(suffix=".json")
subprocess.run([sys.executable, "-I", C.REFERENCE, C.EXAMPLE, out], check=True)
print("Example job-ex: %.4f um\n" % json.load(open(out))["max_depth_um"])
r = C.verify(C.REFERENCE)
print("%-16s %10s %10s %8s %12s %10s %6s" % ("job", "depth um", "true um", "ratio", "speed mm/s", "coolant C", "right"))
for p in sorted(T):
    v = r["packages"][p]
    print("%-16s %10.4f %10.4f %8.4f %12.1f %10d %6s" % (p, v["max_depth_um"], v["true_um"], v["ratio"], T[p]["job"]["work_speed_mm_s"],
          T[p]["job"]["coolant_C"], v["right"]))
dev = [abs(v["ratio"] - 1) for v in r["packages"].values()]
print("\njobs %d; wrong %d (%s); largest deviation from the truth %.4f" % (r["jobs"], r["wrong"], "accepted" if r["accepted"] else "rejected", max(dev)))
print("true burn-limited depths of the hidden jobs: %s um" % "; ".join("%s %.2f" % (p, T[p]["max_depth_um"]) for p in sorted(T)))
