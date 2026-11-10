"""Spread of correct methods, measured by the verifier. Each method is a complete program run through tests/grade.py
on the seven hidden joints exactly as a submission; the columns are each joint's signed deviation from the truth (C).

    python3 authoring/evidence/method_spread.py > authoring/evidence/method_spread.txt
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

VARIANTS = [
    ("reference, each hourly climate reading held until the next one",
     [("        return float(np.trapezoid(np.interp(x, ct, cp), x) / 60)",
       "        return float(np.trapezoid(cp[np.clip(np.searchsorted(ct, x, side='right') - 1, 0, None)], x) / 60)")]),
    ("reference, the first half of each waveform record only",
     [('                w = np.loadtxt(os.path.join(d, r["waveform"]), delimiter=",", skiprows=1)\n                I = w[:, 1] / fac',
       '                w = np.loadtxt(os.path.join(d, r["waveform"]), delimiter=",", skiprows=1)[:5000]\n                I = w[:, 1] / fac')]),
    ("reference, the pick-up rate fitted to the tests of 4 h or more only",
     [("        if len(c) == 6 and re.fullmatch(r\"[\\d.]+\", c[2]):",
       "        if len(c) == 6 and re.fullmatch(r\"[\\d.]+\", c[2]) and float(c[2]) >= 4:")]),
]
T = C.truth(); PK = sorted(T)
print("Correct methods as complete programs through tests/grade.py (run as %s), seven hidden joints; a joint is right "
      "when its minimum preheat is within %.0f C of the truth.\n" % ("nobody" if C.AS_NOBODY else "the current user", C.G.TOL_C))
print("columns: the signed deviation from the truth (C) for " + ", ".join("%d %s" % (i + 1, p) for i, p in enumerate(PK)) + "\n")
rows = [("solution/preheat.py (reference)", C.REFERENCE), ("independent.py (shares no code with the reference)", C.INDEPENDENT)]
rows += [(n, C.program(replace=rep)) for n, rep in VARIANTS]
big = 0
for name, prog in rows:
    r = C.verify(prog)
    w = [C.dev(r["packages"][p]) for p in PK]
    big = max([big] + [abs(x) for x in w if x is not None])
    print("%-70s wrong %d  %s" % (name, r["wrong"], "  ".join("%+6.2f" % x if x is not None else "  none" for x in w)))
print("\nevery correct method: largest deviation from the truth %.2f C (tolerance %.0f C)" % (big, C.G.TOL_C))
