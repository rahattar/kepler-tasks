"""The routes of route_study.py on the example main kestrel-lane, against the design the utility's engineer reported
for it: each route is the same complete program, run as a command (`python3 -I surge.py MAIN_DIR OUT_JSON`) on the
example's package. The example's records are sound, so a route that only matters on faulty records gives the
reported design here.

    python3 authoring/evidence/route_example.py > authoring/evidence/route_example.txt
"""
import json, os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

ns = {"__file__": os.path.join(os.path.dirname(os.path.abspath(__file__)), "route_study.py")}
exec(open(ns["__file__"]).read().split("T = C.truth()")[0], ns)      # the ROUTES of route_study.py
rep = json.load(open(os.path.join(C.EXAMPLE, "reported_design.json")))
print("Routes on the example kestrel-lane; reported design %.1f m3 vessel / %.1f m3 gas.\n" % (
    rep["vessel_volume_m3"], rep["gas_volume_m3"]))
print("%-86s %10s %8s %9s" % ("route", "vessel m3", "gas m3", "/reported"))
for name, kw in [("reference (no check left out)", {})] + ns["ROUTES"]:
    out = tempfile.mktemp(suffix=".json")
    subprocess.run([sys.executable, "-I", C.program(**kw), C.EXAMPLE, out], check=True)
    d = json.load(open(out))
    print("%-86s %10.2f %8.2f %9.3f" % (name, d["vessel_volume_m3"], d["gas_volume_m3"],
                                         d["vessel_volume_m3"] / rep["vessel_volume_m3"]), flush=True)
