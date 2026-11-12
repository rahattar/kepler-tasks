#!/usr/bin/env python3
"""The laser contractor. usage: laservisit <tag> <tag> ... : the whole programme of visits in one order."""
import json, os, sys
RIG = os.environ["ALIGN_RIG"]; APP = os.environ["ALIGN_APP"]
d = json.load(open(os.path.join(RIG, "truth.json")))
state = os.path.join(RIG, "visits.json")
n = d["budget"]
usage = "usage: laservisit <tag> ... <tag>   (the %d trains to visit, named together in one order)" % n
tags = sys.argv[1:]
if os.path.exists(state):
    sys.exit("the programme was placed already, for %s; the contractor takes no second order" % ", ".join(json.load(open(state))))
if len(tags) != n or any(t not in d["trains"] for t in tags):
    sys.exit(usage)
if len(set(tags)) != n:
    sys.exit("the contractor does not return to a train; name %d different trains" % n)
json.dump(tags, open(state, "w"))
os.makedirs(os.path.join(APP, "laser_reports"), exist_ok=True)
for tag in tags:
    t = d["trains"][tag]; sr, sl, mr, ml = t["change_now"]
    rows = [("y_stationary_plane", t["ys"]), ("y_movable_plane", t["ym"]), ("z_stationary_plane", t["zs"]),
            ("z_movable_plane", t["zm"]), ("stationary_rise", sr), ("stationary_lateral", sl),
            ("movable_rise", mr), ("movable_lateral", ml)]
    path = os.path.join(APP, "laser_reports", "%s.csv" % tag)
    with open(path, "w") as f:
        f.write("quantity,mm\n" + "".join("%s,%.3f\n" % r for r in rows))
    print("# %s written to %s" % (tag, path))
