"""Grades independent_gtperf.py (a second program sharing no code with solution/gtperf.py) on the hidden record sets.

    python3 authoring/evidence/independent.py > authoring/evidence/independent.txt
"""
import os

import common as C

if __name__ == "__main__":
    text = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "independent_gtperf.py")).read()
    text = text.replace('DOCS = "/app/data/docs"', 'DOCS = %r' % os.path.join(C.ROOT, "environment", "data", "docs"))
    r = C.grade_text(text)
    print("Independent program on the hidden record sets (miss in percent, output / heat rate):\n")
    for k, v in sorted(r["sets"].items()):
        print("%-3s %s" % (k, v.get("error") or "%+.3f / %+.3f" % (100 * v["output_miss"], 100 * v["heat_rate_miss"])))
    n, w, _ = C.summary(r)
    print("\n%d of 8 sets outside 0.3 %%; largest miss %.3f %%" % (n, w))
