"""Grades independent_diagnose.py (a second program sharing no code with solution/diagnose.py) on the hidden route
packages.

    python3 authoring/evidence/independent.py > authoring/evidence/independent.txt
"""
import os

import common as C

if __name__ == "__main__":
    text = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "independent_diagnose.py")).read()
    r = C.grade_text(text)
    print("Independent program on the hidden route packages (60 machines; the bound is 2 wrong):\n")
    for name, v in sorted(r["routes"].items()):
        print("%-16s %s" % (name, v.get("error") or "%d wrong" % v["wrong"]))
    print("\n%d of %d misdiagnosed%s" % (r["wrong"], r["machines"], (": " + "; ".join(C.misses(r))) if r["wrong"] else ""))
