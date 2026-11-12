#!/usr/bin/env python3
"""The laser contractor. usage: laservisit <tag>"""
import json, os, sys
RIG = os.environ["ALIGN_RIG"]; APP = os.environ["ALIGN_APP"]
d = json.load(open(os.path.join(RIG, "truth.json")))
state = os.path.join(RIG, "visits.json")
done = json.load(open(state)) if os.path.exists(state) else []
if len(sys.argv) != 2 or sys.argv[1] not in d["trains"]:
    sys.exit("usage: laservisit <tag>   (a tag from the train register)")
tag = sys.argv[1]
if tag in done:
    sys.exit("%s has been visited; the contractor does not return to a train" % tag)
if len(done) >= d["budget"]:
    sys.exit("the contractor's time is used up: %d of %d visits" % (len(done), d["budget"]))
done.append(tag); json.dump(done, open(state, "w"))
t = d["trains"][tag]; sr, sl, mr, ml = t["change"]
rows = [("y_stationary_plane", t["ys"]), ("y_movable_plane", t["ym"]), ("z_stationary_plane", t["zs"]),
        ("z_movable_plane", t["zm"]), ("stationary_rise", sr), ("stationary_lateral", sl),
        ("movable_rise", mr), ("movable_lateral", ml)]
os.makedirs(os.path.join(APP, "laser_reports"), exist_ok=True)
path = os.path.join(APP, "laser_reports", "%s.csv" % tag)
with open(path, "w") as f:
    f.write("quantity,mm\n" + "".join("%s,%.3f\n" % r for r in rows))
print(open(path).read().strip()); print("# visit %d of %d, written to %s" % (len(done), d["budget"], path))
