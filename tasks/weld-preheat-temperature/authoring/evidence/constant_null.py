"""Method-free answers, measured by the verifier: each is a complete program that writes a fixed preheat, or a rule
of thumb from the package, run through tests/grade.py on the seven hidden joints exactly as a submission.

    python3 authoring/evidence/constant_null.py > authoring/evidence/constant_null.txt
"""
import json, os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

out = tempfile.mktemp(suffix=".json")
subprocess.run([sys.executable, "-I", C.REFERENCE, C.EXAMPLE, out], check=True)
ex = json.load(open(out))["min_preheat_c"]
FIXED = '''import json, sys
json.dump({"min_preheat_c": %r}, open(sys.argv[2], "w"))
'''
# a shop rule of thumb: the example's preheat scaled by the plates' highest CEV printed on the certificates of the joint
# sheet's heats, at 75 C per 0.05 of CEV
RULE = r'''import json, re, sys
d = sys.argv[1]
js = open(d + "/joint_sheet.md").read()
heats = re.findall(r"heat (\S+), \d+ mm", js)
mc = open(d + "/mill_certificates.md").read()
cev = max(float(re.search(r"## Heat %s,.*?CEV \(IIW\): (\d+\.\d+)" % h, mc, re.S).group(1)) for h in heats)
json.dump({"min_preheat_c": max(EX + 1500 * (cev - CEV0), 20.0)}, open(sys.argv[2], "w"))
'''
NULLS = [("the example's preheat (%.1f C) for every joint" % ex, FIXED % ex),
         ("150 C for every joint", FIXED % 150.0),
         ("the example's preheat moved 75 C per 0.05 of the highest CEV", RULE.replace("EX", repr(ex)).replace("CEV0", "0.41"))]
T = C.truth(); PK = sorted(T)
print("Method-free answers as complete programs through tests/grade.py (run as %s); seven hidden joints; accepted when "
      "at most %d is wrong.\n" % ("nobody" if C.AS_NOBODY else "the current user", C.MAX_WRONG))
print("columns: the signed deviation from the truth in C (* wrong) for " + ", ".join("%d %s" % (i + 1, p) for i, p in enumerate(PK)) + "\n")
for name, src in NULLS:
    r = C.verify(C.write_program(src))
    cells = "  ".join("%+.1f%s" % (C.dev(r["packages"][p]), "" if r["packages"][p]["right"] else "*") for p in PK)
    print("%-62s wrong %d  %s  %s" % (name, r["wrong"], cells, "accepted" if r["accepted"] else "rejected"))
