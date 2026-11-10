"""Method-free answers, measured by the verifier: each is a complete program that writes a fixed design (or the
example's design scaled by a rule of thumb), run through tests/grade.py on the six hidden mains exactly as a
submission. None is accepted.

    python3 authoring/evidence/constant_null.py > authoring/evidence/constant_null.txt
"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

ex = json.load(open(os.path.join(C.EXAMPLE, "reported_design.json")))


def length_flow(d):
    """The main's length (m) and the new sets' total rated flow (L/s), as the scaled rule reads them."""
    t = open(os.path.join(d, "system_description.md")).read(); p = open(os.path.join(d, "pump_datasheets.md")).read()
    L = float(re.search(r"; ([\d,]+) m from PS-2", t).group(1).replace(",", ""))
    n = dict(one=1, two=2, three=3)[re.search(r"(\w+) sets running together", t).group(1)]
    return L, float(re.search(r"([\d.]+) L/s at", p).group(1)) * n


Lx, Qx = length_flow(C.EXAMPLE)
FIXED = '''import json, sys
json.dump({"vessel_volume_m3": %r, "gas_volume_m3": %r}, open(sys.argv[2], "w"))
'''
# rule of thumb: vessel in proportion to the steady flow times the main's length (the water column's momentum)
SCALED = '''import json, math, re, sys
t = open(sys.argv[1] + "/system_description.md").read(); p = open(sys.argv[1] + "/pump_datasheets.md").read()
L = float(re.search(r"; ([\\d,]+) m from PS-2", t).group(1).replace(",", ""))
n = dict(one=1, two=2, three=3)[re.search(r"(\\w+) sets running together", t).group(1)]
Q = float(re.search(r"([\\d.]+) L/s at", p).group(1)) * n
V = %r * L * Q
json.dump({"vessel_volume_m3": V, "gas_volume_m3": V * %r}, open(sys.argv[2], "w"))
'''
NULLS = [("the example's reported design on every main", FIXED % (ex["vessel_volume_m3"], ex["gas_volume_m3"])),
         ("a 50 m3 vessel with 25 m3 gas on every main", FIXED % (50.0, 25.0)),
         ("a 100 m3 vessel with 50 m3 gas on every main", FIXED % (100.0, 50.0)),
         ("the example's design scaled by flow x length", SCALED % (ex["vessel_volume_m3"] / (Lx * Qx), ex["gas_volume_m3"] / ex["vessel_volume_m3"]))]
T = C.truth(); PK = sorted(T)
print("Method-free answers as complete programs through tests/grade.py (run as %s); six hidden mains; accepted when "
      "at most %d is wrong.\n" % ("nobody" if C.AS_NOBODY else "the current user", C.MAX_WRONG))
print("columns: ratio of the design to the true smallest vessel (* wrong) for " + ", ".join("%d %s" % (i + 1, p) for i, p in enumerate(PK)) + "\n")
for name, src in NULLS:
    r = C.verify(C.write_program(src))
    cells = "  ".join("%6.3f%s" % (r["packages"][p].get("ratio_to_smallest") or float("nan"), "" if r["packages"][p]["right"] else "*") for p in PK)
    print("%-50s wrong %d  %s  %s" % (name, r["wrong"], cells, "accepted" if r["accepted"] else "rejected"))
