"""Grades independent_hpu.py (a second program sharing no code with solution/hpu.py) on the hidden packages.

    python3 authoring/evidence/independent.py > authoring/evidence/independent.txt
"""
import os

import common as C

r = C.grade_hpu.score(os.path.join(os.path.dirname(os.path.abspath(__file__)), "independent_hpu.py"), hidden=C.HIDDEN, as_nobody=False)
print("Independent program on the hidden packages (the bound is 1 wrong of 8); errors in percent (efficiency absolute):\n")
for name, v in sorted(r["cases"].items()):
    print("%-6s %s %s" % (name, "right" if v["right"] else "WRONG", v.get("error") or v["error_pct"]))
print("\n%d of 8 wrong" % r["wrong"])
w = C.worst(r)
print("largest absolute error: " + ", ".join("%s %.2f" % (C.SHORT[k], w[k]) for k in w))
