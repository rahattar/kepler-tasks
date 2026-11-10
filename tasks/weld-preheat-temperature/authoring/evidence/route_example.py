"""The routes of route_study.py on the example joint joint-ex: each route is the same complete program, run as a
command (`python3 -I preheat.py JOB_DIR OUT_JSON`) on the example's package. The example's records are sound (the
joint sheet's plates, cast analyses only, electrodes in a heated quiver, no pulsed runs, nothing in the shop log), so
a route that matters only on faulty records gives the reference's result there.

    python3 authoring/evidence/route_example.py > authoring/evidence/route_example.txt
"""
import json, os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

ns = {"__file__": os.path.join(os.path.dirname(os.path.abspath(__file__)), "route_study.py")}
exec(open(ns["__file__"]).read().split("T = C.truth()")[0], ns)
print("Routes on the example joint-ex.\n")
print("%-104s %10s" % ("route", "preheat C"))
for name, kw in [("reference (no check left out)", {})] + ns["ROUTES"]:
    out = tempfile.mktemp(suffix=".json")
    subprocess.run([sys.executable, "-I", C.program(**kw), C.EXAMPLE, out], check=True)
    print("%-104s %10.2f" % (name, json.load(open(out))["min_preheat_c"]), flush=True)
