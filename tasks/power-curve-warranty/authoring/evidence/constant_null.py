"""Method-free answers, measured by the verifier: each is a complete program that reads only the turbine list of the
package (site description) and writes a fixed answer, run through tests/grade.py on the six hidden packages exactly as
the verifier runs a submission. None is accepted, and none is within the allowance on any single package: every one
gets at least two turbines of every hidden package wrong.

    python3 authoring/evidence/constant_null.py > authoring/evidence/constant_null.txt
"""
import csv, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

T = C.truth()
PK = sorted(T)
rep = {r["turbine"]: (float(r["aep_ratio"]), r["warranty_claim"])
       for r in csv.DictReader(open(os.path.join(C.EXAMPLE, "reported_results.csv")))}
PROGRAM = '''import csv, os, re, sys
ANSWER = %r
DEFAULT = %r
pkg, out = sys.argv[1], sys.argv[2]
ts = re.findall(r"^\\| (T\\d+) \\|", open(os.path.join(pkg, "site_description.md")).read(), re.M)
with open(out, "w", newline="") as f:
    w = csv.writer(f); w.writerow(["turbine", "aep_ratio", "warranty_claim"])
    for t in ts:
        a, c = ANSWER.get(t, DEFAULT)
        w.writerow([t, "%%.4f" %% a, c])
'''
NULLS = [("every turbine 1.000, no claim", {}, (1.0, "no")),
         ("every turbine 0.995, no claim", {}, (0.995, "no")),
         ("every turbine 0.950, claim", {}, (0.95, "yes")),
         ("every turbine 0.970, no claim", {}, (0.97, "no")),
         ("the example's reported results by turbine number (T11, T12 as 1.000, no)", rep, (1.0, "no"))]
print("Method-free answers as complete programs through tests/grade.py (run as %s); six hidden packages, 59 turbines "
      "(%d claims); accepted when at most %d is wrong.\n" % ("nobody" if C.AS_NOBODY else "the current user",
                                                          sum(v["warranty_claim"] == "yes" for p in T for v in T[p].values()), C.MAX_WRONG))
print("wrong turbines per package: " + ", ".join("%d %s" % (i + 1, p) for i, p in enumerate(PK)) + "\n")
print("%-74s %5s   %s   %s" % ("answer", "wrong", "  ".join("%3d" % (i + 1) for i in range(len(PK))), "fewest in a package"))
floor = 99
for name, ans, dflt in NULLS:
    r = C.verify(C.write_program(PROGRAM % (ans, dflt)))
    per = [r["packages"][p]["wrong"] for p in PK]
    floor = min(floor, min(per))
    print("%-74s %5d   %s   %d  %s" % (name, r["wrong"], "  ".join("%3d" % n for n in per), min(per),
                                      "accepted" if r["accepted"] else "rejected"))
print("\nfewest wrong turbines of any method-free answer on any one package: %d (allowance %d)" % (floor, C.MAX_WRONG))
