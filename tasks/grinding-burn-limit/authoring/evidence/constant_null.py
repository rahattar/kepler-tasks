"""Method-free answers, measured by the verifier: each is a complete program that writes a fixed limit, or a rule of
thumb from the package, run through tests/grade.py on the seven hidden jobs exactly as a submission.

    python3 authoring/evidence/constant_null.py > authoring/evidence/constant_null.txt
"""
import json, os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

out = tempfile.mktemp(suffix=".json")
subprocess.run([sys.executable, "-I", C.REFERENCE, C.EXAMPLE, out], check=True)
ex = json.load(open(out))["max_depth_um"]
FIXED = '''import json, sys
json.dump({"max_depth_um": %r}, open(sys.argv[2], "w"))
'''
# a shop rule of thumb: the depth that keeps the specific removal rate Q' = ae vw at the example's value
RULE = '''import json, re, sys
s = open(sys.argv[1] + "/job_sheet.md").read()
v = float(re.search(r"work speed (\\d+) m/min", s).group(1))
json.dump({"max_depth_um": %r * %r / v}, open(sys.argv[2], "w"))
'''
NULLS = [("the example's depth (%.2f um) for every job" % ex, FIXED % ex),
         ("15 um for every job", FIXED % 15.0),
         ("the example's specific removal rate at the job's work speed", RULE % (ex, 15.0))]
T = C.truth(); PK = sorted(T)
print("Method-free answers as complete programs through tests/grade.py (run as %s); seven hidden jobs; accepted when "
      "at most %d is wrong.\n" % ("nobody" if C.AS_NOBODY else "the current user", C.MAX_WRONG))
print("columns: the signed relative deviation from the truth (* wrong) for " + ", ".join("%d %s" % (i + 1, p) for i, p in enumerate(PK)) + "\n")
for name, src in NULLS:
    r = C.verify(C.write_program(src))
    cells = "  ".join("%+.3f%s" % (C.dev(r["packages"][p]), "" if r["packages"][p]["right"] else "*") for p in PK)
    print("%-62s wrong %d  %s  %s" % (name, r["wrong"], cells, "accepted" if r["accepted"] else "rejected"))
