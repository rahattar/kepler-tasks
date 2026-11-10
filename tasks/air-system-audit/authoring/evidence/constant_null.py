"""Programs that do not compute the audit, against the bound of 1 wrong of 8: one that always writes the example's
results, and one that writes the compressors' combined capacity and a typical specific power.

    python3 authoring/evidence/constant_null.py > authoring/evidence/constant_null.txt
"""
import json
import os

import common as C

FIXED = 'import json, sys\njson.dump(%r, open(sys.argv[2], "w"))\n'
CAPACITY = '''import json, sys
s = json.load(open(sys.argv[1] + "/site.json"))
cap = 0.0
for c in s["compressors"]:
    t = c.get("performance") or c.get("performance_at_set_point")
    cap += max(r["fad_m3_min"] for r in t)
json.dump({"avg_demand_m3_min": 0.5 * cap, "peak_demand_m3_min": cap, "leak_m3_min": 0.2 * cap,
           "specific_power_kw_per_m3_min": 6.5}, open(sys.argv[2], "w"))
'''

if __name__ == "__main__":
    ex = json.load(open(os.path.join(C.ROOT, "environment", "data", "examples", "s-201", "audit_result.json")))
    for label, text in (("the example's results", FIXED % ex), ("fractions of the installed capacity", CAPACITY)):
        r = C.grade_text(text)
        print("%-40s %d of %d wrong" % (label, r["wrong"], len(r["cases"])))
