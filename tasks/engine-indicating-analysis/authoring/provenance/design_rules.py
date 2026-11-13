"""The rules the cells were designed to, recomputed from the generator's table and the shipped files.

    python3 design_rules.py > ../evidence/design_rules.txt

Each line begins `holds` or `FAILS`. The figures quoted in README.md come from here.
"""
import sys

sys.dont_write_bytecode = True
import csv
import hashlib
import json
import os
import sys

import numpy as np

import cells
import cylinder

HERE = os.path.dirname(os.path.abspath(__file__))
BUNDLE = os.path.dirname(os.path.dirname(HERE))
count = [0, 0]


def rule(holds, text):
    count[0] += 1
    count[1] += not holds
    print("%s   %s" % ("holds" if holds else "FAILS", text))


def folder(c):
    return os.path.join(BUNDLE, cells.PLACE[c["role"]], c["cell"])


def points(c):
    with open(os.path.join(folder(c), "points.csv"), newline="") as handle:
        return list(csv.DictReader(handle))


def sealed(c):
    path = os.path.join(folder(c), "expected.csv") if c["role"] == "example" else os.path.join(
        BUNDLE, cells.SEALED[c["role"]], c["cell"] + ".csv")
    with open(path, newline="") as handle:
        return list(csv.DictReader(handle))


def span(values, form="%.1f"):
    return (form + " to " + form) % (min(values), max(values))


def first_heat(c):
    """The earliest crank angle, over the points and cylinders of a cell, at which the mean cycle has released
    1 per cent of its heat: IS-2 section 7 on the records at the cell's true index and gain."""
    eng = c["eng"]
    theta = cells.ENC + c["index_deg"]
    vol = cylinder.volume(theta, eng)
    k0, k1 = int(np.searchsorted(theta, eng["ivc_deg"])), int(np.searchsorted(theta, eng["evo_deg"], side="right")) - 1
    earliest = 180.0
    for p in points(c):
        rec = np.load(os.path.join(folder(c), p["record"])).astype(float) * c["scale"] / c["gain"]
        rec = rec - rec[:, :, :20].mean(axis=2, keepdims=True) + float(p["p_man_bar"])
        mean = rec.mean(axis=1)[:, k0:k1 + 1] * 1e5
        vm, dv = 0.5 * (vol[k0 + 1:k1 + 1] + vol[k0:k1]), np.diff(vol[k0:k1 + 1])
        pm, dp = 0.5 * (mean[:, 1:] + mean[:, :-1]), np.diff(mean, axis=1)
        mass = float(p["p_man_bar"]) * 1e5 * cylinder.volume(eng["ivc_deg"], eng) / (cylinder.R_GAS * float(p["t_ivc_K"]))
        temp = pm * vm / (mass * cylinder.R_GAS)
        speed = float(p["speed_rpm"])
        wall = cylinder.hohenberg(pm, temp, vm, 2 * eng["stroke_mm"] * 1e-3 * speed / 60) * cylinder.wall_area(vm, eng) * (
            temp - float(p["t_wall_K"])) * 0.5 / (6.0 * speed)
        burned = np.zeros_like(pm)
        for _ in range(8):
            g = cylinder.gamma(temp, burned)
            q = np.cumsum(g / (g - 1) * pm * dv + vm * dp / (g - 1) + wall, axis=1)
            share = np.clip(q / q[:, -1:], 0, 1)
            burned = np.concatenate([0.5 * share[:, :1], 0.5 * (share[:, 1:] + share[:, :-1])], axis=1)
        for row in q / q[:, -1:]:
            late = np.nonzero(row >= 0.01)[0]
            # the first sample from which the share stays at or above 1 per cent
            below = np.nonzero(row < 0.01)[0]
            start = (below[-1] + 1) if len(below) else 0
            earliest = min(earliest, theta[k0 + 1 + start])
    return earliest


def work_per_degree(c):
    """Per cent change of the mean effective pressure of each point's mean cycle when the crank angle is taken
    one degree away from the true one (the records at the cell's true gain and index, and one degree off)."""
    eng = c["eng"]
    out = []
    for p in points(c):
        rec = np.load(os.path.join(folder(c), p["record"])).astype(float) * c["scale"] / c["gain"]
        rec = rec - rec[:, :, :20].mean(axis=2, keepdims=True) + float(p["p_man_bar"])
        mean = rec.mean(axis=(0, 1))
        work = [float(np.sum(0.5 * (mean[1:] + mean[:-1]) * np.diff(cylinder.volume(cells.ENC + c["index_deg"] + off, eng))))
                for off in (0.0, 1.0)]
        out.append(100 * (work[1] / work[0] - 1))
    return out


def main():
    book = cells.CELLS
    by_role = {role: [c for c in book if c["role"] == role] for role in ("example", "pending", "hidden")}
    names = [c["cell"] for c in book]
    rule(len(by_role["example"]) == 2 and len(by_role["pending"]) == 2 and len(by_role["hidden"]) == 6 and len(set(names)) == 10,
         "10 cells: 2 with their results beside them, 2 without results, 6 the program is run on; no name twice")
    for c in by_role["example"]:
        rule(os.path.exists(os.path.join(folder(c), "expected.csv")), "%s carries expected.csv" % c["cell"])
    for c in by_role["pending"]:
        rule(not os.path.exists(os.path.join(folder(c), "expected.csv")), "%s carries no results" % c["cell"])

    def digests(group):
        found = set()
        for c in group:
            for base, _, files in os.walk(folder(c)):
                for name in files:
                    with open(os.path.join(base, name), "rb") as handle:
                        found.add(hashlib.sha256(handle.read()).hexdigest())
        return found
    shared = digests(by_role["hidden"]) & digests(by_role["example"] + by_role["pending"])
    rule(not shared, "no file of a cell the program is run on is a file of a visible cell (%d shared)" % len(shared))

    def cycles(c):
        return c["cyl"] * c["points"] * cells.CYCLES[c["role"]]
    for c in book:
        shape_ok = all(np.load(os.path.join(folder(c), p["record"]), mmap_mode="r").shape == (c["cyl"], cells.CYCLES[c["role"]], 720)
                       for p in points(c))
        if not shape_ok:
            rule(False, "%s: a record is not cylinders by cycles by 720" % c["cell"])
    rule(max(cycles(c) for c in book) <= 20000 and max(c["cyl"] for c in book) <= 6,
         "cycles in a package: %s in the examples, %s in the pending packages, %s where the program is run; the stated most is 20,000, and 6 cylinders" % (
             span([cycles(c) for c in by_role["example"]], "%d"), span([cycles(c) for c in by_role["pending"]], "%d"),
             span([cycles(c) for c in by_role["hidden"]], "%d")))
    rule(max(cycles(c) for c in by_role["hidden"]) <= max(cycles(c) for c in by_role["pending"]),
         "the largest package the program is run on (%d cycles) is no larger than the largest visible one (%d cycles)" % (
             max(cycles(c) for c in by_role["hidden"]), max(cycles(c) for c in by_role["pending"])))

    rule(all(c["index_deg"] == 0.0 and c["gain"] == 1.0 for c in by_role["example"]),
         "in the two examples the index mark is on top dead centre and the scale is the transducer's, exactly")
    p11, p13 = by_role["pending"]
    rule(p11["index_deg"] != 0 and p11["gain"] == 1.0, "pending %s: the index is %+.2f degrees out and the scale is right" % (p11["cell"], p11["index_deg"]))
    rule(p13["index_deg"] == 0 and p13["gain"] != 1.0, "pending %s: the index is right and the transducer gives %.3f of what the scale assumes" % (p13["cell"], p13["gain"]))
    kinds = {"exact": [], "index": [], "gain": [], "both": []}
    for c in by_role["hidden"]:
        kinds["both" if c["index_deg"] and c["gain"] != 1 else "index" if c["index_deg"] else "gain" if c["gain"] != 1 else "exact"].append(c)
    rule([len(kinds[k]) for k in ("exact", "index", "gain", "both")] == [1, 1, 2, 2],
         "the six cells: 1 exact (%s), 1 with the index out (%s), 2 with the gain out (%s), 2 with both (%s)" % tuple(
             ", ".join(c["cell"] for c in kinds[k]) for k in ("exact", "index", "gain", "both")))
    off_index = [abs(c["index_deg"]) for c in by_role["hidden"] if c["index_deg"]]
    off_gain = [100 * abs(c["gain"] - 1) for c in by_role["hidden"] if c["gain"] != 1]
    rule(min(off_index) >= 1.0 and min(off_gain) >= 4.0,
         "where it is out, the index is %s degrees out, of either sign, and the gain %s per cent, of either sign" % (
             span(off_index, "%.2f"), span(off_gain, "%.1f")))
    rule(any(c["index_deg"] > 0 for c in by_role["hidden"]) and any(c["index_deg"] < 0 for c in by_role["hidden"])
         and any(c["gain"] > 1 for c in by_role["hidden"]) and any(c["gain"] < 1 for c in by_role["hidden"]),
         "both signs of each occur among the six, and the visible instances have one sign of each (%+.2f degrees, gain %.3f)" % (
             p11["index_deg"], p13["gain"]))
    rule(all(0.90 <= c["f_ht"] <= 1.10 for c in book),
         "each engine's wall heat is %s of Hohenberg's with IS-2's constants; IS-2 says within 10 per cent" % span([c["f_ht"] for c in book], "%.2f"))

    def reach(group, key, form="%.1f"):
        return span([c["eng"][key] for c in group], form)
    vis = by_role["example"] + by_role["pending"]
    hid = by_role["hidden"]
    speeds = lambda g: [float(p["speed_rpm"]) for c in g for p in points(c)]
    mans = lambda g: [float(p["p_man_bar"]) for c in g for p in points(c)]
    rule(max(c["eng"]["compression_ratio"] for c in hid) > max(c["eng"]["compression_ratio"] for c in vis)
         and max(c["eng"]["bore_mm"] for c in hid) > max(c["eng"]["bore_mm"] for c in vis)
         and max(mans(hid)) > max(mans(vis)) and min(speeds(hid)) < min(speeds(vis)) and max(speeds(hid)) > max(speeds(vis)),
         "the engines the program is run on reach past the visible ones: compression ratio %s against %s, bore %s against %s mm, "
         "manifold pressure %s against %s bar, speed %s against %s rpm" % (
             reach(hid, "compression_ratio"), reach(vis, "compression_ratio"), reach(hid, "bore_mm", "%.0f"), reach(vis, "bore_mm", "%.0f"),
             span(mans(hid), "%.2f"), span(mans(vis), "%.2f"), span(speeds(hid), "%.0f"), span(speeds(vis), "%.0f")))
    rule(sum(c["ignition"] == "compression" for c in hid) == 3 and all(c["ignition"] == "spark" for c in vis),
         "3 of the six are compression-ignition engines; every visible engine is spark-ignited")
    in_scope = all(70 <= c["eng"]["bore_mm"] <= 140 and 9 <= c["eng"]["compression_ratio"] <= 18 and c["cyl"] <= 6 for c in book) and \
        600 <= min(speeds(book)) and max(speeds(book)) <= 5000 and 0.3 <= min(mans(book)) and max(mans(book)) <= 2.6
    rule(in_scope, "every engine and operating point of every package is within the scope of IS-2 section 1")

    rows = [r for c in hid for r in sealed(c)]
    col = lambda name: [float(r[name]) for r in rows]
    rule(len(rows) == sum(c["cyl"] * c["points"] for c in hid),
         "results at the six cells (%d rows): mean effective pressure %s bar, peak pressure %s bar at %s degrees, 10 per cent burned at %s "
         "and 50 per cent at %s degrees, heat released %s J" % (
             len(rows), span(col("imep_bar")), span(col("pmax_bar"), "%.0f"), span(col("apmax_deg")), span(col("ca10_deg")),
             span(col("ca50_deg")), span(col("q_gross_J"), "%.0f")))
    per_degree = [abs(v) for c in hid for v in work_per_degree(c)]
    rule(min(per_degree) > 1.0,
         "at the six cells a degree of index error moves the mean effective pressure by %s per cent, and every angle by a degree; "
         "a gain error moves every pressure, the work and the heat by its own share" % span(per_degree))
    starts = {c["cell"]: first_heat(c) for c in book}
    rule(min(starts.values()) > -40.0,
         "at its true index and gain, no mean cycle of any cell has released 1 per cent of its heat before %.1f degrees; "
         "the compression stroke is free of combustion to 40 degrees before top dead centre" % min(starts.values()))
    print("\n%d rules, %d not holding" % (count[0], count[1]))
    return 1 if count[1] else 0


if __name__ == "__main__":
    sys.exit(main())
