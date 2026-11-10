"""Spread of correct methods, measured by the verifier. Each method is a complete program run through tests/grade.py
on the seven hidden jobs exactly as a submission; the columns are each job's signed relative deviation from the truth.

    python3 authoring/evidence/method_spread.py > authoring/evidence/method_spread.txt
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

VARIANTS = [
    ("reference, every second frequency point (1 Hz)", [('    t["f"], t["G"] = f, G\n', '    t["f"], t["G"] = f[::2], G[::2]\n')]),
    ("reference, FRF smoothed over 3 points", [('    t["f"], t["G"] = f, G\n', '    G = np.convolve(G, np.ones(3) / 3, mode="same"); t["f"], t["G"] = f[1:-1], G[1:-1]\n')]),
    ("reference, chatter frequencies up to 3000 Hz only", [('    t["f"], t["G"] = f, G\n', '    keep = f <= 3000.0; t["f"], t["G"] = f[keep], G[keep]\n')]),
]
T = C.truth(); PK = sorted(T)
print("Correct methods as complete programs through tests/grade.py (run as %s), seven hidden jobs; a job is right when "
      "its limit is within %.0f percent of the truth.\n" % ("nobody" if C.AS_NOBODY else "the current user", 100 * C.G.TOL))
print("columns: the signed relative deviation from the truth for " + ", ".join("%d %s" % (i + 1, p) for i, p in enumerate(PK)) + "\n")
rows = [("solution/chatter.py (reference)", C.REFERENCE), ("independent.py (shares no code with the reference)", C.INDEPENDENT)]
rows += [(n, C.program(replace=rep)) for n, rep in VARIANTS]
big = 0
for name, prog in rows:
    r = C.verify(prog)
    w = [C.dev(r["packages"][p]) for p in PK]
    big = max([big] + [abs(x) for x in w if x is not None])
    print("%-52s wrong %d  %s" % (name, r["wrong"], "  ".join("%+.4f" % x if x is not None else "  none " for x in w)))
print("\nevery correct method: largest deviation from the truth %.4f (tolerance %.2f)" % (big, C.G.TOL))
