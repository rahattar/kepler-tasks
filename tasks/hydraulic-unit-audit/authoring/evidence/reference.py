"""The reference program on the hidden packages: per-press errors and the largest of each; and the true results
against the simulated per-cycle means (simulated.json), to show what the procedure's model costs.

    python3 authoring/evidence/reference.py > authoring/evidence/reference.txt
"""
import json
import os

import common as C

r = C.grade_hpu.score(C.SOLUTION, hidden=C.HIDDEN, as_nobody=False)
print("Reference program (solution/hpu.py) on the hidden packages (the bound is 1 wrong of 8); errors in percent")
print("(efficiency: absolute):\n")
for name, v in sorted(r["cases"].items()):
    print("%-6s %s %s" % (name, "right" if v["right"] else "WRONG", v["error_pct"]))
print("\n%d of 8 wrong" % r["wrong"])
w = C.worst(r)
print("largest absolute error: " + ", ".join("%s %.2f" % (C.SHORT[k], w[k]) for k in w))

truth = json.load(open(os.path.join(C.HIDDEN, "truth.json")))
sim = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "simulated.json")))
print("\nTrue results (HP-2 on the true log) against the simulated per-cycle means, percent:")
for name in sorted(truth):
    d = {k: round(100 * (truth[name][k] / sim[name][k] - 1), 2) for k in sim[name]}
    print("%-6s %s" % (name, d))
