"""The reference program on the hidden audits, with its per-site errors and the largest of each, and the hidden
sites' true results (the realism figures quoted in the README: leak share of demand, system specific power).

    python3 authoring/evidence/reference.py > authoring/evidence/reference.txt
"""
import json
import os

import common as C

r = C.grade_audits.score(C.SOLUTION, hidden=C.HIDDEN, as_nobody=False)
print("Reference program (solution/audit.py) on the hidden audits (the bound is 1 wrong of 8); errors in percent:\n")
worst = {k: 0.0 for k in C.grade_audits.TOL}
for name, v in sorted(r["cases"].items()):
    print("%-7s %s %s" % (name, "right" if v["right"] else "WRONG", v["error_pct"]))
    for k, e in v["error_pct"].items():
        worst[k] = max(worst[k], abs(e))
print("\n%d of 8 wrong" % r["wrong"])
print("largest absolute error, percent: " + ", ".join("%s %.2f" % (C.SHORT[k], worst[k]) for k in worst))

truth = json.load(open(os.path.join(C.HIDDEN, "truth.json")))
print("\nTrue results of the hidden sites:")
share = []
for name, t in sorted(truth.items()):
    s = t["leak_m3_min"] / t["avg_demand_m3_min"]
    share.append(s)
    print("%-7s leak / average demand %.3f, specific power %.2f kW per m3/min" % (
        name, s, t["specific_power_kw_per_m3_min"]))
sp = [t["specific_power_kw_per_m3_min"] for t in truth.values()]
print("leak share %.1f to %.1f %% of average demand; specific power %.2f to %.2f kW per m3/min" % (
    100 * min(share), 100 * max(share), min(sp), max(sp)))
