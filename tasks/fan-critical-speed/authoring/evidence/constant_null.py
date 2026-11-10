"""Method-free answers, measured by the verifier: each is a complete program that writes fixed critical speeds, or a
rule of thumb from the package, run through tests/grade.py on the six hidden fans exactly as a submission.

    python3 authoring/evidence/constant_null.py > authoring/evidence/constant_null.txt
"""
import json, os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

out = tempfile.mktemp(suffix=".json")
subprocess.run([sys.executable, "-I", C.REFERENCE, C.EXAMPLE, out], check=True)
ex = json.load(open(out))
FIXED = '''import json, sys
json.dump({"first_critical_rpm": %r, "second_critical_rpm": %r}, open(sys.argv[2], "w"))
'''
# the latest impact test's frequencies, as rpm: the critical speeds taken as the measured standstill frequencies
TEST_RPM = '''import glob, json, re, sys
p = sorted(glob.glob(sys.argv[1] + "/impact_tests/*.md"))[-1]; t = open(p).read()
h = float(re.search(r"\\| horizontal \\| ([\\d.]+) \\|", t).group(1)); v = float(re.search(r"\\| vertical \\| ([\\d.]+) \\|", t).group(1))
json.dump({"first_critical_rpm": 60 * min(h, v), "second_critical_rpm": 60 * max(h, v)}, open(sys.argv[2], "w"))
'''
# the example's critical speeds, scaled by the fan's latest test frequencies over the example's
SCALED = '''import glob, json, re, sys
def f(d):
    t = open(sorted(glob.glob(d + "/impact_tests/*.md"))[-1]).read()
    return [float(re.search(r"\\| %%s \\| ([\\d.]+) \\|" %% k, t).group(1)) for k in ("horizontal", "vertical")]
h, v = f(sys.argv[1]); h0, v0 = %r, %r
json.dump({"first_critical_rpm": %r * h / h0, "second_critical_rpm": %r * v / v0}, open(sys.argv[2], "w"))
'''
t0 = open(sorted(__import__("glob").glob(C.EXAMPLE + "/impact_tests/*.md"))[-1]).read()
import re
h0 = float(re.search(r"\| horizontal \| ([\d.]+) \|", t0).group(1)); v0 = float(re.search(r"\| vertical \| ([\d.]+) \|", t0).group(1))
NULLS = [("the example's critical speeds (%.1f, %.1f rpm) on every fan" % (ex["first_critical_rpm"], ex["second_critical_rpm"]),
          FIXED % (ex["first_critical_rpm"], ex["second_critical_rpm"])),
         ("1000 and 1500 rpm on every fan", FIXED % (1000.0, 1500.0)),
         ("the latest impact test's frequencies, as rpm", TEST_RPM),
         ("the example's critical speeds scaled by the latest test's frequencies", SCALED % (h0, v0, ex["first_critical_rpm"], ex["second_critical_rpm"]))]
T = C.truth(); PK = sorted(T)
print("Method-free answers as complete programs through tests/grade.py (run as %s); six hidden fans; accepted when "
      "at most %d is wrong.\n" % ("nobody" if C.AS_NOBODY else "the current user", C.MAX_WRONG))
print("columns: the larger signed relative deviation of the two critical speeds (* wrong) for " + ", ".join("%d %s" % (i + 1, p) for i, p in enumerate(PK)) + "\n")
for name, src in NULLS:
    r = C.verify(C.write_program(src))
    cells = "  ".join("%+.3f%s" % (C.worst(r["packages"][p]), "" if r["packages"][p]["right"] else "*") for p in PK)
    print("%-72s wrong %d  %s  %s" % (name, r["wrong"], cells, "accepted" if r["accepted"] else "rejected"))
