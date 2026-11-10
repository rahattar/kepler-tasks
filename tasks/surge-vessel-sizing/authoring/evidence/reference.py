"""The reference program (solution/surge.py) through tests/grade.py on the six hidden mains, as the verifier runs it;
and as a command on the example against the engineer's reported design.

    python3 authoring/evidence/reference.py > authoring/evidence/reference.txt
"""
import json, os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

T = C.truth()
print("Reference program solution/surge.py through tests/grade.py (run as %s); a main is right when the design meets "
      "MS-SV clause 3 on the main as installed and is at most 15 percent above the smallest vessel that does.\n"
      % ("nobody" if C.AS_NOBODY else "the current user"))
out = tempfile.mktemp(suffix=".json")
subprocess.run([sys.executable, "-I", C.REFERENCE, C.EXAMPLE, out], check=True)
got, rep = json.load(open(out)), json.load(open(os.path.join(C.EXAMPLE, "reported_design.json")))
print("Example kestrel-lane: reference %.2f m3 vessel / %.2f m3 gas; reported %.1f / %.1f (ratio %.3f / %.3f)\n" % (
    got["vessel_volume_m3"], got["gas_volume_m3"], rep["vessel_volume_m3"], rep["gas_volume_m3"],
    got["vessel_volume_m3"] / rep["vessel_volume_m3"], got["gas_volume_m3"] / rep["gas_volume_m3"]))
r = C.verify(C.REFERENCE)
print("%-14s %10s %8s %10s %10s %8s %9s %8s %7s" % ("main", "vessel m3", "gas m3", "smallest", "its gas", "ratio",
                                                     "crown m", "gas/V", "right"))
for p in sorted(T):
    v = r["packages"][p]
    print("%-14s %10.2f %8.2f %10.2f %10.2f %8.3f %9.2f %8.3f %7s" % (p, v["vessel_volume_m3"], v["gas_volume_m3"],
          T[p]["vmin_m3"], T[p]["gas_m3"], v["ratio_to_smallest"], v["worst"]["pmin"], v["worst"]["gas"], v["right"]))
rs = [v["ratio_to_smallest"] for v in r["packages"].values()]
print("\nmains %d; wrong %d (%s); ratio to the smallest vessel %.3f to %.3f (limit 1.15)" % (
    r["mains"], r["wrong"], "accepted" if r["accepted"] else "rejected", min(rs), max(rs)))
print("smallest vessels of the hidden mains: %s m3" % ", ".join("%.1f" % T[p]["vmin_m3"] for p in sorted(T)))
