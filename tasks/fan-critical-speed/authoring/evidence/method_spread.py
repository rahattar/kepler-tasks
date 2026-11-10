"""Spread of correct methods, measured by the verifier. Each method is a complete program run through tests/grade.py
on the six hidden fans exactly as a submission; the columns are each fan's larger relative deviation of its two
critical speeds from the truth.

    python3 authoring/evidence/method_spread.py > authoring/evidence/method_spread.txt
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

VARIANTS = [
    ("reference, shaft elements of 10 mm (not 20)", [("def assemble(S, sh, imp, kH, kV, mesh=0.02):", "def assemble(S, sh, imp, kH, kV, mesh=0.01):")]),
    ("reference, shaft elements of 50 mm (not 20)", [("def assemble(S, sh, imp, kH, kV, mesh=0.02):", "def assemble(S, sh, imp, kH, kV, mesh=0.05):")]),
    ("reference, the shaft's own polar inertia left out", [("            G[4 * nn + 2, 4 * nn + 3] += RHO * 2 * I * L / 2; G[4 * nn + 3, 4 * nn + 2] -= RHO * 2 * I * L / 2",
                                                           "            pass")]),
    ("reference, test frequencies rounded to 0.1 Hz", [('fH=float(re.search(r"\\| horizontal \\| ([\\d.]+) \\|", r).group(1)), fV=float(re.search(r"\\| vertical \\| ([\\d.]+) \\|", r).group(1))',
                                                        'fH=round(float(re.search(r"\\| horizontal \\| ([\\d.]+) \\|", r).group(1)), 1), fV=round(float(re.search(r"\\| vertical \\| ([\\d.]+) \\|", r).group(1)), 1)')]),
]
T = C.truth(); PK = sorted(T)
print("Correct methods as complete programs through tests/grade.py (run as %s), six hidden fans; a fan is right when "
      "both critical speeds are within %.0f percent of the truth.\n" % ("nobody" if C.AS_NOBODY else "the current user", 100 * C.G.TOL))
print("columns: the larger signed relative deviation of the two critical speeds for " + ", ".join("%d %s" % (i + 1, p) for i, p in enumerate(PK)) + "\n")
rows = [("solution/fan.py (reference)", C.REFERENCE), ("independent.py (shares no code with the reference)", C.INDEPENDENT)]
rows += [(n, C.program(replace=rep)) for n, rep in VARIANTS]
big = 0
for name, prog in rows:
    r = C.verify(prog)
    w = [C.worst(r["packages"][p]) for p in PK]
    big = max([big] + [abs(x) for x in w if x is not None])
    print("%-56s wrong %d  %s" % (name, r["wrong"], "  ".join("%+.4f" % x if x is not None else "  none " for x in w)))
print("\nevery correct method: largest deviation from the truth %.4f (tolerance %.2f)" % (big, C.G.TOL))
