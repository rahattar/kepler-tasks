"""Grades independent_design.py (a second program sharing no code with solution/design.py) on the hidden cases.

    python3 authoring/evidence/independent.py > authoring/evidence/independent.txt
"""
import os

import common as C

if __name__ == "__main__":
    text = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "independent_design.py")).read()
    r = C.grade_text(text)
    print("Independent program on the hidden cases (the bound is 1 wrong of 8):\n")
    for name, v in sorted(r["cases"].items()):
        print("%-16s %s %s" % (name, "right" if v["right"] else "WRONG", v.get("error") or v["rating"]))
    print("\n%d of %d wrong" % (r["wrong"], len(r["cases"])))
