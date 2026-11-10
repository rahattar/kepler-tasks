"""Spread of correct methods, measured by the verifier: each method is a complete program run through tests/grade.py
on the six hidden packages exactly as the verifier runs a submission, and judged by grade.py against the sealed truth.

    python3 authoring/evidence/method_spread.py > authoring/evidence/method_spread.txt

The methods are the reference, the independent program (independent.py, which shares no code with the reference), and
the reference with one source fragment replaced where PP-12 leaves the method open (the fragments are listed below).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

YAW_DAILY = ("        direc = (yaw + corr) % 360\n",
             "        corr = -pd.Series(diff).groupby(day.values).transform('median').values\n"
             "        corr = np.where(np.abs(corr) > 5.0, corr, 0.0)\n"
             "        direc = (yaw + corr) % 360\n")
VARIANTS = [
    ("NTF re-established on M1 4 to 16 m/s (not 3 to 18)", ("(mws > 3) & (mws < 18)", "(mws > 4) & (mws < 16)")),
    ("barometer outage: feed reduced to M1 by the barometric formula (not scaled on the overlap)",
     ("    elif good.sum() > 1000:", "    elif False:")),
    ("yaw corrected day by day where the daily offset exceeds 5 deg (not one located step)", YAW_DAILY),
    ("calibration-turbine drift against the fleet mean (not median)",
     ("fleet = pd.concat([ratio_d[t] for t in others], axis=1).median(axis=1)",
      "fleet = pd.concat([ratio_d[t] for t in others], axis=1).mean(axis=1)")),
    ("commissioning NTF verification threshold 2 percent (not 3)", ("abs(np.median(v) - 1) > 0.03", "abs(np.median(v) - 1) > 0.02")),
    ("M1 clock step at the start of the first lagged week (not at the gap in M1's stamps)",
     ("        t0 = idx[j[0] + 1] if len(j) and (i == 0 or lags[i - 1] != h) else w0", "        t0 = w0")),
    ("NTF step threshold 3 percent (not 4)", ("- 1) < 0.04: continue", "- 1) < 0.03: continue")),
]
T = C.truth()
PK = sorted(T)
print("Correct methods as complete programs through tests/grade.py (run as %s), six hidden packages, 59 turbines; "
      "tolerance %.2f on the ratio, claim exact.\n" % ("nobody" if C.AS_NOBODY else "the current user", C.TOL))
rows = [("solution/pp12.py (reference)", C.REFERENCE), ("independent.py (shares no code with the reference)", C.INDEPENDENT)]
rows += [(name, C.reference_program(replace=rep)) for name, rep in VARIANTS]
print("worst |error| per package: " + ", ".join("%d %s" % (i + 1, p) for i, p in enumerate(PK)) + "\n")
print("%-90s %5s %8s   %s" % ("method", "wrong", "worst", "  ".join("%6d" % (i + 1) for i in range(len(PK)))))
overall = 0.0
for name, prog in rows:
    r = C.verify(prog)
    s = C.summary(r, T)
    worst = max(v[1] for v in s.values())
    overall = max(overall, worst)
    print("%-90s %5d %8.4f   %s  %s" % (name, r["wrong"], worst, "  ".join("%6.4f" % s[p][1] for p in PK),
                                        "accepted" if r["accepted"] else "rejected"))
print("\nlargest error of any correct method: %.4f (%.2f of the tolerance)" % (overall, overall / C.TOL))
