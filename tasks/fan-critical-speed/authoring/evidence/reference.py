"""The reference program (solution/fan.py) through tests/grade.py on the six hidden fans, as the verifier runs it;
and as a command on the example.

    python3 authoring/evidence/reference.py > authoring/evidence/reference.txt
"""
import json, os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

T = C.truth()
print("Reference program solution/fan.py through tests/grade.py (run as %s); a fan is right when both of its two lowest "
      "critical speeds with the new impeller are within %.0f percent of the truth.\n" % ("nobody" if C.AS_NOBODY else "the current user", 100 * C.G.TOL))
out = tempfile.mktemp(suffix=".json")
subprocess.run([sys.executable, "-I", C.REFERENCE, C.EXAMPLE, out], check=True)
got = json.load(open(out))
print("Example boiler-fd-fan: first %.1f rpm, second %.1f rpm\n" % (got["first_critical_rpm"], got["second_critical_rpm"]))
r = C.verify(C.REFERENCE)
print("%-18s %12s %12s %12s %12s %8s %8s %6s" % ("fan", "first rpm", "true", "second rpm", "true", "ratio 1", "ratio 2", "right"))
for p in sorted(T):
    v = r["packages"][p]
    print("%-18s %12.1f %12.1f %12.1f %12.1f %8.4f %8.4f %6s" % (p, v["first_critical_rpm"], v["true_rpm"][0], v["second_critical_rpm"],
          v["true_rpm"][1], v["ratios"][0], v["ratios"][1], v["right"]))
dev = [abs(x - 1) for v in r["packages"].values() for x in v["ratios"]]
print("\nfans %d; wrong %d (%s); largest deviation from the truth %.4f" % (r["fans"], r["wrong"], "accepted" if r["accepted"] else "rejected", max(dev)))
print("true critical speeds of the hidden fans: %s rpm" % "; ".join("%s %.0f and %.0f" % (p, *T[p]["critical_rpm"]) for p in sorted(T)))
