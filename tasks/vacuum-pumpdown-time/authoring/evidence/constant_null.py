"""Method-free answers, measured by the verifier: each is a complete program that writes a fixed pump-down time, or a
rule of thumb from the package, run through tests/grade.py on the seven hidden chambers exactly as a submission.

    python3 authoring/evidence/constant_null.py > authoring/evidence/constant_null.txt
"""
import json, os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

out = tempfile.mktemp(suffix=".json")
subprocess.run([sys.executable, "-I", C.REFERENCE, C.EXAMPLE, out], check=True)
ex = json.load(open(out))["pumpdown_min"]
FIXED = """import json, sys
json.dump({"pumpdown_min": %r}, open(sys.argv[2], "w"))
"""
# the time at which the chamber's latest record reached the job's process pressure (cold cathode as indicated)
LATEST = r"""import csv, glob, json, re, sys
d = sys.argv[1]
pt = float(re.search(r"Process pressure: ([\d.e+-]+) mbar", open(d + "/job_sheet.md").read()).group(1))
f = sorted(glob.glob(d + "/pumpdown_records/*.csv"))[-1]
rows = list(csv.DictReader([l for l in open(f) if not l.startswith("#")]))
t = next((float(r["time_s"]) for r in rows if r["cold_cathode_mbar"] and float(r["cold_cathode_mbar"]) <= pt), float(rows[-1]["time_s"]))
json.dump({"pumpdown_min": t / 60}, open(sys.argv[2], "w"))
"""
NULLS = [("the example's pump-down time (%.1f min) for every job" % ex, FIXED % ex),
         ("100 min for every job", FIXED % 100.0),
         ("the time the chamber's latest record reached the process pressure", LATEST)]
T = C.truth(); PK = sorted(T)
print("Method-free answers as complete programs through tests/grade.py (run as %s); seven hidden chambers; accepted "
      "when at most %d is wrong.\n" % ("nobody" if C.AS_NOBODY else "the current user", C.MAX_WRONG))
print("columns: the signed deviation from the truth in percent (* wrong) for " + ", ".join("%d %s" % (i + 1, p) for i, p in enumerate(PK)) + "\n")
for name, src in NULLS:
    r = C.verify(C.write_program(src))
    cells = "  ".join("%+.1f%s" % (100 * C.dev(r["packages"][p]), "" if r["packages"][p]["right"] else "*") for p in PK)
    print("%-72s wrong %d  %s  %s" % (name, r["wrong"], cells, "accepted" if r["accepted"] else "rejected"))
