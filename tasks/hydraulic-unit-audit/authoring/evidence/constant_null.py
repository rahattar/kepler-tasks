"""Programs that do not reduce the log, against the bound of 1 wrong of 8: one that always writes the example's
results, and one that writes typical figures scaled by the pump displacement.

    python3 authoring/evidence/constant_null.py > authoring/evidence/constant_null.txt
"""
import json
import os

import common as C

ex = json.load(open(os.path.join(C.ROOT, "environment", "data", "examples", "p-01", "results.json")))
A = "import json, sys\njson.dump(%r, open(sys.argv[2], 'w'))\n" % ex
B = '''import json, sys
u = json.load(open(sys.argv[1] + "/unit.json"))
vg = u["pump"]["displacement_cm3_per_rev"]
s = vg / 28.0
json.dump({"oil_delivered_l": 2.88 * s, "peak_flow_l_min": 55.0 * s, "hydraulic_energy_kj": 50.9 * s,
           "electrical_energy_kj": 71.5 * s, "unit_efficiency": 0.71}, open(sys.argv[2], "w"))
'''
for name, text in (("the example's results", A), ("typical figures scaled by the displacement", B)):
    r = C.grade_text(text)
    print("%-45s %d of 8 wrong" % (name, r["wrong"]))
