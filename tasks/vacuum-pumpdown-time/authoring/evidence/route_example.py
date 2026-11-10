"""The routes of route_study.py on the example chamber chamber-ex: each route is the same complete program, run as a
command (`python3 -I pumpdown.py JOB_DIR OUT_JSON`) on the example's package. The example's records are sound (the
chamber sheet's pumps, gauges and crossover, empty air-vent records, no changes in the equipment log), so a route that
matters only on faulty records gives the reference's result there.

    python3 authoring/evidence/route_example.py > authoring/evidence/route_example.txt
"""
import json, os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

ns = {"__file__": os.path.join(os.path.dirname(os.path.abspath(__file__)), "route_study.py")}
exec(open(ns["__file__"]).read().split("T = C.truth()")[0], ns)
print("Routes on the example chamber-ex.\n")
print("%-106s %10s" % ("route", "time min"))
for name, kw in [("reference (no check left out)", {})] + ns["ROUTES"]:
    out = tempfile.mktemp(suffix=".json")
    subprocess.run([sys.executable, "-I", C.program(**kw), C.EXAMPLE, out], check=True)
    print("%-106s %10.2f" % (name, json.load(open(out))["pumpdown_min"]), flush=True)
