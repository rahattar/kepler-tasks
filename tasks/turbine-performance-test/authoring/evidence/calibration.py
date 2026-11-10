"""Recomputes the sealed values in tests/gt1_truth.py from the sealed definition (authoring/provenance/gt.py) and checks
that every OEM correction factor is 1 at the contract reference conditions.

    python3 authoring/evidence/calibration.py > authoring/evidence/calibration.txt
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "authoring", "provenance"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import gt          # noqa: E402
import gt1_truth   # noqa: E402

if __name__ == "__main__":
    worst = 0.0
    print("condition  definition (MW, kJ/kWh)  tests/gt1_truth.py")
    for c in gt1_truth.CONDITIONS:
        s = gt.truth_table()[c]
        worst = max(worst, abs(s["p_mw"] - gt1_truth.OUTPUT_MW[c]), abs(s["hr"] - gt1_truth.HEAT_RATE[c]))
        print("%-9s  %.4f %.1f            %.4f %.1f" % (c, s["p_mw"], s["hr"], gt1_truth.OUTPUT_MW[c], gt1_truth.HEAT_RATE[c]))
    print("largest difference %.2e" % worst)
    r = gt.REF
    f = gt.f_cit(r["cit"]) * gt.f_p(r["p_kpa"]) * gt.f_hum(gt.W_REF) * gt.f_in(r["dp_in"]) * gt.f_ex(r["dp_ex"])
    g = gt.g_cit(r["cit"]) * gt.g_hum(gt.W_REF) * gt.g_in(r["dp_in"]) * gt.g_ex(r["dp_ex"])
    print("product of output factors at reference %.6f, of heat rate factors %.6f" % (f, g))
    assert worst < 1e-9 and abs(f - 1) < 1e-12 and abs(g - 1) < 1e-12
