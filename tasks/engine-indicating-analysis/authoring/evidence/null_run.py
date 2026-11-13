"""Programs with no physics in them, run by the verifier's checker on the six cells.

    python3 null_run.py > null_run.txt

Two programs written from the visible results alone. Neither opens a pressure record.
  mean      every row gets the mean of the two examples' expected results
  nearest   every row gets the expected results of the example point nearest in speed and manifold pressure
A row counts only when all six of its values are within their bands.
"""
import csv
import os
import sys

import common

TEMPLATE = '''import csv, json, os, sys
package, out = sys.argv[1], sys.argv[2]
known = %(known)r
names = ["imep_bar", "pmax_bar", "apmax_deg", "ca10_deg", "ca50_deg", "q_gross_J"]
with open(os.path.join(package, "engine.json")) as handle:
    cylinders = json.load(handle)["cylinders"]
with open(os.path.join(package, "points.csv"), newline="") as handle:
    points = list(csv.DictReader(handle))
with open(out, "w") as handle:
    handle.write("point,cylinder," + ",".join(names) + "\\n")
    for p in points:
        if %(nearest)r:
            best = min(known, key=lambda k: ((k[0] - float(p["speed_rpm"])) / 1000.0) ** 2 + (k[1] - float(p["p_man_bar"])) ** 2)
            values = best[2]
        else:
            values = [sum(k[2][i] for k in known) / len(known) for i in range(6)]
        for c in range(1, cylinders + 1):
            handle.write("%%s,%%d,%%s\\n" %% (p["point"], c, ",".join("%%.4f" %% v for v in values)))
'''


def known_points():
    """(speed, manifold pressure, mean results over the cylinders) of every example point."""
    out = []
    for c in common.EXAMPLES:
        folder = os.path.join(common.VISIBLE, "examples", c["cell"])
        with open(os.path.join(folder, "points.csv"), newline="") as handle:
            pts = {r["point"]: r for r in csv.DictReader(handle)}
        with open(os.path.join(folder, "expected.csv"), newline="") as handle:
            rows = list(csv.DictReader(handle))
        for name, p in pts.items():
            mine = [r for r in rows if r["point"] == name]
            values = [sum(float(r[q]) for r in mine) / len(mine) for q in common.check_program.HEADER[2:]]
            out.append((float(p["speed_rpm"]), float(p["p_man_bar"]), values))
    return out


def main():
    known = known_points()
    best = 0
    for name, nearest in (("mean", False), ("nearest", True)):
        report = common.assess(common.program(TEMPLATE % dict(known=known, nearest=nearest)))
        rows = sum(f.get("rows", 0) for f in report["cells"].values())
        right = sum(f.get("rows", 0) - f.get("rows_out", 0) for f in report["cells"].values())
        best = max(best, right)
        print("%-8s %s; rows with all six values in band: %d of %d" % (name, "accepted" if report["accepted"] else "not accepted", right, rows))
        if report["accepted"]:
            print("PROBLEM: a program without physics is accepted")
    print("\n2 programs, 0 accepted; most rows right: %d of 250" % best)
    return 0


if __name__ == "__main__":
    sys.exit(main())
