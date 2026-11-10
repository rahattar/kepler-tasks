"""The routes of route_study.py on the example fan boiler-fd-fan: each route is the same complete program, run as a
command (`python3 -I fan.py FAN_DIR OUT_JSON`) on the example's package. The example's records are sound (one test,
as installed; one rotor change, entered after its work but before the test), so a route that matters only on faulty
records gives the reference's result there.

    python3 authoring/evidence/route_example.py > authoring/evidence/route_example.txt
"""
import json, os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

ns = {"__file__": os.path.join(os.path.dirname(os.path.abspath(__file__)), "route_study.py")}
exec(open(ns["__file__"]).read().split("T = C.truth()")[0], ns)
print("Routes on the example boiler-fd-fan.\n")
print("%-78s %10s %10s" % ("route", "first rpm", "second rpm"))
for name, kw in [("reference (no check left out)", {})] + ns["ROUTES"]:
    out = tempfile.mktemp(suffix=".json")
    subprocess.run([sys.executable, "-I", C.program(**kw), C.EXAMPLE, out], check=True)
    d = json.load(open(out))
    print("%-78s %10.1f %10.1f" % (name, d["first_critical_rpm"], d["second_critical_rpm"]), flush=True)
