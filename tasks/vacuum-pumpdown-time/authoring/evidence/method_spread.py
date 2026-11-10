"""Spread of correct methods, measured by the verifier. Each method is a complete program run through tests/grade.py
on the seven hidden chambers exactly as a submission; the columns are each chamber's signed deviation from the truth
(percent).

    python3 authoring/evidence/method_spread.py > authoring/evidence/method_spread.txt
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

VARIANTS = [
    ("reference, the high-vacuum gas load taken as S_eff p (quasi-static)", [], {"quasi"}),
    ("reference, every second high-vacuum sample of each record only",
     [("        t0 = hv[0][0] + 600\n        hv = [h for h in hv if h[0] >= t0]",
       "        t0 = hv[0][0] + 600\n        hv = [h for h in hv if h[0] >= t0][::2]")], set()),
    ("reference, the records' high-vacuum samples from 20 minutes after the crossover",
     [("        t0 = hv[0][0] + 600\n", "        t0 = hv[0][0] + 1200\n")], set()),
]
T = C.truth(); PK = sorted(T)
print("Correct methods as complete programs through tests/grade.py (run as %s), seven hidden chambers; a chamber is "
      "right when its job's pump-down time is within %.0f percent of the truth.\n" % ("nobody" if C.AS_NOBODY else "the current user", 100 * C.G.TOL))
print("columns: the signed deviation from the truth (percent) for " + ", ".join("%d %s" % (i + 1, p) for i, p in enumerate(PK)) + "\n")
rows = [("solution/pumpdown.py (reference)", C.REFERENCE), ("independent.py (shares no code with the reference)", C.INDEPENDENT)]
rows += [(n, C.program(replace=rep, skip=sk)) for n, rep, sk in VARIANTS]
big = 0
for name, prog in rows:
    r = C.verify(prog)
    w = [C.dev(r["packages"][p]) for p in PK]
    big = max([big] + [abs(x) for x in w if x is not None])
    print("%-80s wrong %d  %s" % (name, r["wrong"], "  ".join("%+6.2f" % (100 * x) if x is not None else "  none" for x in w)))
print("\nevery correct method: largest deviation from the truth %.2f percent (tolerance %.0f percent)" % (100 * big, 100 * C.G.TOL))
