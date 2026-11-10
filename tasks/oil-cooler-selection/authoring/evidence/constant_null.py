"""Programs that do not read the case, against the bound of 1 wrong of 8: one that always writes the example
cooler's selection, and one that always writes the most expensive catalogue design.

    python3 authoring/evidence/constant_null.py > authoring/evidence/constant_null.txt
"""
import json
import os

import common as C

FIXED = 'import json, sys\njson.dump(%r, open(sys.argv[2], "w"))\n'

if __name__ == "__main__":
    ex = json.load(open(os.path.join(C.ROOT, "environment", "data", "examples", "e410-k400-lube", "selection.json")))
    ex = {k: ex[k] for k in C.grade_cases.KEYS}
    big = dict(shell_id_mm=838, tube="19.05x1.65", tube_length_m=6.1, tube_passes=2, layout_deg=30, baffle_cut_pct=25,
               baffle_spacing_mm=500, shells_in_series=3)
    for label, d in (("the example's selection", ex), ("the largest catalogue design", big)):
        r = C.grade_text(FIXED % d)
        print("%-35s %d of %d wrong" % (label, r["wrong"], len(r["cases"])))
