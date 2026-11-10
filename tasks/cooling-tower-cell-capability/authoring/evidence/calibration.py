"""Recomputes the sealed values in tests/ct2.py from the sealed definition (authoring/provenance/cells.py), and
checks the design fill constant the documents quote.

    python3 authoring/evidence/calibration.py > authoring/evidence/calibration.txt
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "authoring", "provenance"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import cells  # noqa: E402
import ct2    # noqa: E402
import psy    # noqa: E402

if __name__ == "__main__":
    t = cells.truth_table()
    worst = 0.0
    print("cell  definition  tests/ct2.py")
    for c in cells.CELLS:
        worst = max(worst, abs(t[c] - ct2.CAPABILITY[c]))
        print("%-4s  %10.4f  %12.4f" % (c, t[c], ct2.CAPABILITY[c]))
    print("largest difference %.2e pp" % worst)
    k = psy.merkel(40.0, 30.0, cells.LG_DESIGN, psy.hsat(24.0, cells.P_DESIGN_PA), cells.P_DESIGN_PA)
    print("design point 40/30/24 degC at L/G %.2f: KaV/L %.4f, C_d %.4f (documents: 1.4001); G_d %.1f kg/s "
          "(documents: 424.8); rho_d %.4f kg/m3 (documents: 1.0654)"
          % (cells.LG_DESIGN, k, cells.C_DESIGN, cells.G_DESIGN, cells.RHO_DESIGN))
    assert worst < 1e-6
