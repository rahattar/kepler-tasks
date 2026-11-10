"""Method-free answers, measured by the verifier: each is a complete program that writes a fixed limit, or a rule of
thumb from the package, run through tests/grade.py on the seven hidden jobs exactly as a submission.

    python3 authoring/evidence/constant_null.py > authoring/evidence/constant_null.txt
"""
import json, os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

out = tempfile.mktemp(suffix=".json")
subprocess.run([sys.executable, "-I", C.REFERENCE, C.EXAMPLE, out], check=True)
ex = json.load(open(out))["stable_depth_mm"]
FIXED = '''import json, sys
json.dump({"stable_depth_mm": %r}, open(sys.argv[2], "w"))
'''
# the example's limit scaled by the job's coefficients and teeth: a ~ 1 / (N Kt)
SCALED = '''import json, re, sys
s = open(sys.argv[1] + "/setup_sheet.md").read()
mat = re.search(r"Material: (.+?)\\.\\n", s).group(1)
N = int(re.search(r"(\\d+) (?:flutes|insert pockets)", s).group(1))
Kt = {r.split("|")[1].strip(): float(r.split("|")[2]) for r in open("/app/data/docs/cutting_coefficients.md") if r.count("|") == 4 and r.split("|")[2].strip().isdigit()}[mat]
json.dump({"stable_depth_mm": %r * 3 * 700.0 / (N * Kt)}, open(sys.argv[2], "w"))
'''
NULLS = [("the example's limit (%.3f mm) for every job" % ex, FIXED % ex),
         ("2.5 mm for every job", FIXED % 2.5),
         ("the example's limit scaled by 1 / (teeth x Kt)", SCALED % ex)]
T = C.truth(); PK = sorted(T)
print("Method-free answers as complete programs through tests/grade.py (run as %s); seven hidden jobs; accepted when "
      "at most %d is wrong.\n" % ("nobody" if C.AS_NOBODY else "the current user", C.MAX_WRONG))
print("columns: the signed relative deviation from the truth (* wrong) for " + ", ".join("%d %s" % (i + 1, p) for i, p in enumerate(PK)) + "\n")
for name, src in NULLS:
    r = C.verify(C.write_program(src))
    cells = "  ".join("%+.3f%s" % (C.dev(r["packages"][p]), "" if r["packages"][p]["right"] else "*") for p in PK)
    print("%-52s wrong %d  %s  %s" % (name, r["wrong"], cells, "accepted" if r["accepted"] else "rejected"))
