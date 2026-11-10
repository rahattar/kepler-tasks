"""Reviews that do not follow the standard's method, against the verifier: answers that ignore the building
(constant verdicts) and the contractor's own figures, with and without the right verdicts.

    python3 authoring/evidence/constant_null.py > authoring/evidence/constant_null.txt
"""
import json, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import openpyxl
import project as P, grade as G

wb = openpyxl.load_workbook(os.path.join(ROOT, "environment", "data", "contractor", "hvac_load_calcs.xlsx"), data_only=True)
SHEET = {}
for r in wb["Units"].iter_rows(min_row=2, values_only=True):
    if r[0] in P.UNITS:
        SHEET[r[0]] = dict(outdoor_air_l_s=r[3], coil_entering_wb_c=19.4, block_total_kw=r[9], block_sensible_kw=r[10],
                           block_latent_kw=r[11], net_capacity_total_kw=r[13], net_capacity_sensible_kw=r[14],
                           net_capacity_latent_kw=round(r[13] - r[14], 2))
T = P.truth()


def review(verdict_of, submittal, numbers=SHEET):
    units = {}
    for u in P.UNITS:
        v = verdict_of(u)
        units[u] = dict(verdict=v, missing="tenant_fitout_loads") if v == "undetermined" else dict(verdict=v, **numbers[u])
    return dict(units=units, submittal=submittal)


CASES = {
    "the contractor's sheet: every unit accepted, approve": review(lambda u: "accept", "approve"),
    "every unit undetermined (tenant fit-out), return": review(lambda u: "undetermined", "return_for_revision"),
    "every unit undersized, contractor's figures, return": review(lambda u: "reject_undersized", "return_for_revision"),
    "every unit oversized, contractor's figures, return": review(lambda u: "reject_oversized", "return_for_revision"),
    "the District's verdicts, contractor's figures": review(lambda u: T[u]["verdict"], T["submittal"]),
}

if __name__ == "__main__":
    print("Reviews that ignore the building or reuse the contractor's figures; each must fail.\n")
    d = tempfile.mkdtemp()
    for name, rv in CASES.items():
        p = os.path.join(d, "review.json"); json.dump(rv, open(p, "w"))
        g = G.grade(p)
        print("%-54s %s  units wrong %d of 7%s" % (name, "PASS" if g["passed"] else "FAIL", len(g["wrong"]),
              "" if g["submittal_ok"] else ", submittal wrong"))
