"""Programs that do not reduce the record set, against the 0.3 % bound: one that always writes the same pair of values
(the contractor's 2025-04-09 results, and the best single pair for the hidden sets), and the plant's program as shipped.

    python3 authoring/evidence/constant_null.py > authoring/evidence/constant_null.txt
"""
import json
import os

import common as C

FIXED = 'import sys\nopen(sys.argv[2], "w").write("corrected_output_mw,corrected_heat_rate_kj_kwh\\n%.4f,%.2f\\n")\n'

if __name__ == "__main__":
    truth = json.load(open(os.path.join(C.HIDDEN, "truth.json")))
    po = sorted(v["output_mw"] for v in truth.values())
    ph = sorted(v["heat_rate"] for v in truth.values())
    print("Hidden truths: output %.2f-%.2f MW, heat rate %.0f-%.0f kJ/kWh" % (po[0], po[-1], ph[0], ph[-1]))
    for label, p, h in [("contractor's 2025-04-09 values", 42.37, 10811.0),
                        ("median of the hidden truths", po[len(po) // 2], ph[len(ph) // 2])]:
        n, _, _ = C.summary(C.grade_text(FIXED % (p, h)))
        print("A program that always writes %s (%.2f MW, %.0f kJ/kWh): %d of 8 sets fail" % (label, p, h, n))
    n, _, _ = C.summary(C.grade_text(C.bugs.make(C.bugs.ALL)))
    print("The plant's program as shipped: %d of 8 sets fail" % n)
