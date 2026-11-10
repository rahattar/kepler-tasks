"""The routes of route_study.py on the example job job-ex: each route is the same complete program, run as a command
(`python3 -I burn.py JOB_DIR OUT_JSON`) on the example's package. The example's records are sound (one wheel and one
coolant over the records, one lot tempered once, the dressing interval in mm3/mm, no table or chiller work in the
log), so a route that matters only on faulty records gives the reference's result there.

    python3 authoring/evidence/route_example.py > authoring/evidence/route_example.txt
"""
import json, os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

ns = {"__file__": os.path.join(os.path.dirname(os.path.abspath(__file__)), "route_study.py")}
exec(open(ns["__file__"]).read().split("T = C.truth()")[0], ns)
print("Routes on the example job-ex.\n")
print("%-92s %10s" % ("route", "depth um"))
for name, kw in [("reference (no check left out)", {})] + ns["ROUTES"]:
    out = tempfile.mktemp(suffix=".json")
    subprocess.run([sys.executable, "-I", C.program(**kw), C.EXAMPLE, out], check=True)
    print("%-92s %10.4f" % (name, json.load(open(out))["max_depth_um"]), flush=True)
