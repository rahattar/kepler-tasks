"""Spread of correct methods, measured by the verifier. Each method is a complete program run through tests/grade.py
on the seven hidden jobs exactly as a submission; the columns are each job's signed relative deviation from the truth.

    python3 authoring/evidence/method_spread.py > authoring/evidence/method_spread.txt
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

VARIANTS = [
    ("reference, each session's idle power from its first air pass only", [('        Pn = P - (gidle if "idle" in skip else np.mean(idle[r["date"]]))',
                                                                               '        Pn = P - (gidle if "idle" in skip else idle[r["date"]][0])')]),
    ("reference, every second grind pass of the records only", [('    for r in rows:\n        if r["pass"] != "grind" or r["date"] < start:',
                                                                 '    for r in [x for x in rows if x["pass"] == "grind"][::2]:\n        if r["pass"] != "grind" or r["date"] < start:')]),
    ("reference, the power model fitted per unit width", [('        X.append([bb, bb * V, bb * a / 1000 * vv]); y.append(Pn)',
                                                           '        X.append([1.0, V, a / 1000 * vv]); y.append(Pn / bb)')]),
]
T = C.truth(); PK = sorted(T)
print("Correct methods as complete programs through tests/grade.py (run as %s), seven hidden jobs; a job is right when "
      "its depth is within %.0f percent of the truth.\n" % ("nobody" if C.AS_NOBODY else "the current user", 100 * C.G.TOL))
print("columns: the signed relative deviation from the truth for " + ", ".join("%d %s" % (i + 1, p) for i, p in enumerate(PK)) + "\n")
rows = [("solution/burn.py (reference)", C.REFERENCE), ("independent.py (shares no code with the reference)", C.INDEPENDENT)]
rows += [(n, C.program(replace=rep)) for n, rep in VARIANTS]
big = 0
for name, prog in rows:
    r = C.verify(prog)
    w = [C.dev(r["packages"][p]) for p in PK]
    big = max([big] + [abs(x) for x in w if x is not None])
    print("%-70s wrong %d  %s" % (name, r["wrong"], "  ".join("%+.4f" % x if x is not None else "  none " for x in w)))
print("\nevery correct method: largest deviation from the truth %.4f (tolerance %.2f)" % (big, C.G.TOL))
