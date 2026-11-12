"""Builds the core's packages: three examples (with their expected results and the survey that settled their
unknowns) and eight hidden systems (with their truth). Run: python3 gen.py

Hidden shift, on purpose (each kind has a visible instance in the examples):
- size: hidden grids to 36 lines by 30 heads (examples to 16 by 12), so a per-placement solve that is not
  warm-started or pruned does not finish in the limit;
- where the unknown pipe is: on the far cross main of a grid, on the riser-end lines only, on the branch lines of
  a tree, on a long feed main up a 60 ft riser (examples: feed and cross main, a grid's lines and mains);
- an unverified valve on a grid's cross main between two lines (example: on a tree's feed main), and one beside
  an aged branch-line group;
- densities and areas beyond the examples' (0.45 gpm/ft2 against at most 0.30), a weak supply that refuses a
  test flow the examples' supplies would pass, and a ceiling sloped across the lines (an example slopes along).
"""
import json
import math
import os
import random
import shutil

import hyd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "core", "data")
HIDDEN = os.path.join(HERE, "core", "hidden")


def build(spec):
    """A system package (dict) and its truth from a spec."""
    NL, NH = spec["lines"], spec["heads"]
    Sb, Sl = spec["spacing_branch_ft"], spec["spacing_lines_ft"]
    zc = spec["ceiling_ft"]
    slope_x = spec.get("slope_along", 0.0)      # ft per ft along the lines
    slope_y = spec.get("slope_across", 0.0)     # ft per ft across the lines
    grid = spec["kind"] == "grid"

    def z_at(x, y):
        return round(zc + slope_x * x + slope_y * y, 2)

    nodes, pipes = {}, []

    def node(nid, x, y, z=None):
        nodes[nid] = dict(x=round(x, 2), y=round(y, 2), z=z_at(x, y) if z is None else z)

    def group_of_line(j):
        for g, (a, b) in spec.get("line_groups", {}).items():
            if a <= j <= b:
                return g
        return "lines"

    pid = [0]

    alias = spec.get("alias", {})

    def pipe(a, b, size, length, group, fittings=(), schedule=None):
        group = alias.get(group, group)
        pid[0] += 1
        pipes.append({"id": "P%04d" % pid[0], "from": a, "to": b, "size": size,
                      "schedule": schedule or spec["schedules"].get(group, "40"), "length_ft": round(length, 2),
                      "fittings": list(fittings), "group": group})
        return pipes[-1]["id"]

    feed_len = spec["feed_ft"]
    node("R0", -feed_len, -Sl, 0.0)
    node("R1", -feed_len, -Sl, spec["riser_top_ft"])
    pipe("R0", "R1", spec["feed_size"], spec["riser_top_ft"], "riser", ["check valve", "gate valve"])
    node("A0", 0.0, 0.0)
    feed_fit = ["elbow", "elbow", "gate valve"]
    pipe("R1", "A0", spec["feed_size"], feed_len + Sl, "feed", feed_fit)
    xB = (NH + 0.5) * Sb
    prev = "A0"
    for j in range(1, NL + 1):
        y = j * Sl - Sl / 2
        node("A%d" % j, 0.0, y)
        fit = ["butterfly valve"] if spec.get("sectional_valve_after") == j - 1 and j > 1 else []
        pipe(prev, "A%d" % j, spec["crossA_size"], Sl if j > 1 else Sl / 2, "crossA", fit)
        prev = "A%d" % j
    if grid:
        prev = None
        for j in range(1, NL + 1):
            y = j * Sl - Sl / 2
            node("B%d" % j, xB, y)
            if prev:
                pipe(prev, "B%d" % j, spec["crossB_size"], Sl, "crossB")
            prev = "B%d" % j
    lines, heads = [], []
    for j in range(1, NL + 1):
        y = j * Sl - Sl / 2
        g = group_of_line(j)
        hs = []
        prev = "A%d" % j
        for i in range(1, NH + 1):
            nid = "L%dH%d" % (j, i)
            node(nid, (i - 0.5) * Sb, y)
            pipe(prev, nid, spec["branch_size"](i, NH), Sb / 2 if i == 1 else Sb, g, ["tee"] if i == 1 else [])
            prev = nid
            hs.append(nid)
            heads.append({"node": nid, "K": spec["K"], "line": j, "column": i})
        if grid:
            pipe(prev, "B%d" % j, spec["branch_size"](NH, NH), Sb / 2, g, ["tee"])
        lines.append({"number": j, "heads": hs})
    groups = {}
    for g, info in spec["groups"].items():
        groups[g] = {"installed": info["installed"], "service": info["service"],
                     "C": info["C"] if info.get("known", True) else None}
    gauges = []
    outlets = [{"id": "FC-A", "node": "A%d" % NL, "K": spec.get("flush_K", 140.0),
                "description": "flushing connection, far end of cross main A"}]
    if grid:
        outlets.append({"id": "FC-B", "node": "B%d" % NL, "K": spec.get("flush_K", 140.0),
                        "description": "flushing connection, far end of cross main B"})
        outlets.append({"id": "FC-B1", "node": "B1", "K": spec.get("flush_K", 140.0),
                        "description": "flushing connection, near end of cross main B"})
    outlets.append({"id": "ITC", "node": "L%dH%d" % (NL, NH), "K": 5.6,
                    "description": "inspector's test connection, end of the last branch line"})
    if not grid:
        outlets.append({"id": "DR-L", "node": "L%dH%d" % (NL // 2, NH), "K": 22.0,
                        "description": "auxiliary drain, end of branch line %d" % (NL // 2)})
        gauges.append("L%dH%d" % (NL // 2, NH))
        gauges.append("A%d" % (NL // 2))
    gauges += ["R1", "A%d" % (NL // 2), "A%d" % NL, "L%dH%d" % (NL, NH), "L1H%d" % NH]
    if grid:
        gauges += ["A1", "B1", "B%d" % (NL // 2), "B%d" % NL]
    gauges += spec.get("extra_gauges", [])
    valves_unverified = []
    for p in pipes:
        if p["group"] == "feed" and spec.get("feed_valve_unverified"):
            valves_unverified.append({"pipe": p["id"], "fitting": "gate valve"})
        if "butterfly valve" in p["fittings"] and spec.get("sectional_valve_unverified"):
            valves_unverified.append({"pipe": p["id"], "fitting": "butterfly valve"})
    system = {
        "tag": spec["tag"], "kind": spec["kind"],
        "nodes": nodes, "pipes": pipes, "groups": groups,
        "lines": lines, "heads": heads, "riser_base": "R0",
        "hazard": {"density_gpm_ft2": spec["density"], "area_ft2": spec["area"], "hose_gpm": spec["hose"],
                   "spacing_branch_ft": Sb, "spacing_lines_ft": Sl},
        "supply": dict(spec["supply"]),
        "outlets": outlets, "gauge_ports": sorted(set(gauges)),
        "valves_unverified": valves_unverified,
    }
    truth = {"C": {g: info["C"] for g, info in spec["groups"].items()}, "valves": {}}
    for v in valves_unverified:
        truth["valves"][v["pipe"]] = spec["valve_factor"]
    return system, truth


def sz(*breaks):
    """Branch-line size by column: [(last column, size), ...] then the rest."""
    def f(i, nh):
        for last, s in breaks:
            if i <= last or (last < 0 and i <= nh + last):
                return s
        return breaks[-1][1]
    return f


NEW = lambda yr: {"installed": yr, "service": "wet, city water", "C": 120, "known": True}       # noqa: E731
OLD = lambda yr, c, svc="wet, city water": {"installed": yr, "service": svc, "C": c, "known": False}  # noqa: E731
SUPPLY = lambda s, r, q: {"static_psi": s, "residual_psi": r, "flow_gpm": q}                   # noqa: E731

COMMON = dict(K=8.0, hose=250, spacing_branch_ft=10.0, spacing_lines_ft=12.0, ceiling_ft=28.0,
              riser_top_ft=24.0, schedules={})

EXAMPLES = [
    dict(COMMON, tag="WH-A", kind="tree", lines=14, heads=10, feed_ft=180, feed_size="6", crossA_size="6",
         branch_size=sz((6, "2"), (99, "1-1/2")), density=0.20, area=2000,
         groups={"riser": NEW(2006), "feed": OLD(1979, 88), "crossA": OLD(1979, 88), "lines": NEW(2006)},
         supply=SUPPLY(92, 74, 1500)),
    dict(COMMON, tag="WH-B", kind="grid", lines=16, heads=12, feed_ft=150, feed_size="6", crossA_size="4",
         crossB_size="3", branch_size=sz((99, "1-1/2")), density=0.30, area=2500, slope_along=0.02,
         alias={"crossA": "mains", "crossB": "mains"},
         groups={"riser": NEW(1984), "feed": NEW(1984), "mains": OLD(1984, 95), "lines": OLD(1984, 78)},
         supply=SUPPLY(105, 88, 2000)),
    dict(COMMON, tag="WH-C", kind="tree", lines=12, heads=9, feed_ft=240, feed_size="6", crossA_size="4",
         branch_size=sz((5, "2"), (99, "1-1/2")), density=0.15, area=1500,
         groups={"riser": NEW(1991), "feed": OLD(1991, 92), "crossA": NEW(1991), "lines": NEW(1991)},
         feed_valve_unverified=True, valve_factor=400.0, supply=SUPPLY(95, 80, 1200)),
]

HIDDEN_SPECS = [
    dict(COMMON, tag="DC-1", kind="grid", lines=30, heads=24, feed_ft=200, feed_size="8", crossA_size="6",
         crossB_size="4", branch_size=sz((99, "1-1/2")), density=0.25, area=2500,
         groups={"riser": NEW(2003), "feed": NEW(2003), "crossA": NEW(2003), "crossB": OLD(1981, 70),
                 "lines": NEW(2003)},
         supply=SUPPLY(110, 90, 2500)),
    dict(COMMON, tag="DC-2", kind="grid", lines=24, heads=20, feed_ft=160, feed_size="6", crossA_size="6",
         crossB_size="4", branch_size=sz((99, "1-1/2")), density=0.30, area=2500,
         groups={"riser": NEW(2010), "feed": NEW(2010), "crossA": NEW(2010), "crossB": NEW(2010),
                 "lines": OLD(1988, 84)},
         sectional_valve_after=12, sectional_valve_unverified=True, valve_factor=150.0,
         supply=SUPPLY(100, 84, 2200)),
    dict(COMMON, tag="DC-3", kind="tree", lines=18, heads=12, feed_ft=150, feed_size="8", crossA_size="6",
         branch_size=sz((6, "3"), (99, "2-1/2")), density=0.45, area=1800, K=16.8,
         groups={"riser": NEW(2001), "feed": NEW(2001), "crossA": NEW(2001), "lines": OLD(1976, 70)},
         supply=SUPPLY(115, 95, 2000)),
    dict(COMMON, tag="DC-4", kind="grid", lines=36, heads=30, feed_ft=220, feed_size="8", crossA_size="6",
         crossB_size="6", branch_size=sz((99, "1-1/2")), density=0.20, area=3000, slope_across=0.01,
         alias={"crossA": "mains", "crossB": "mains"},
         groups={"riser": NEW(1990), "feed": NEW(1990), "mains": OLD(1990, 96), "lines": OLD(1990, 82)},
         supply=SUPPLY(108, 92, 3000)),
    dict(COMMON, tag="DC-5", kind="tree", lines=12, heads=10, feed_ft=420, feed_size="6", crossA_size="6",
         branch_size=sz((6, "2"), (99, "1-1/2")), density=0.20, area=1500, riser_top_ft=60.0,
         ceiling_ft=64.0, groups={"riser": NEW(1998), "feed": OLD(1972, 75), "crossA": NEW(1998),
                                   "lines": NEW(1998)},
         supply=SUPPLY(78, 52, 1000)),
    dict(COMMON, tag="DC-6", kind="grid", lines=28, heads=22, feed_ft=180, feed_size="8", crossA_size="6",
         crossB_size="4", branch_size=sz((99, "1-1/2")), density=0.30, area=2500,
         line_groups={"lines_old": (1, 10)},
         groups={"riser": NEW(2012), "feed": NEW(2012), "crossA": NEW(2012), "crossB": NEW(2012),
                 "lines": NEW(2012), "lines_old": OLD(1979, 72)},
         supply=SUPPLY(104, 88, 2400)),
    dict(COMMON, tag="DC-7", kind="tree", lines=14, heads=11, feed_ft=260, feed_size="6", crossA_size="6",
         branch_size=sz((6, "2"), (99, "1-1/2")), density=0.20, area=1800,
         groups={"riser": NEW(1995), "feed": NEW(1995), "crossA": OLD(1982, 85), "lines": NEW(1995)},
         feed_valve_unverified=True, valve_factor=350.0, supply=SUPPLY(110, 92, 1600)),
    dict(COMMON, tag="DC-8", kind="grid", lines=26, heads=20, feed_ft=170, feed_size="6", crossA_size="6",
         crossB_size="4", branch_size=sz((99, "1-1/2")), density=0.35, area=2500, slope_across=0.025,
         groups={"riser": NEW(2008), "feed": NEW(2008), "crossA": OLD(1985, 90), "crossB": NEW(2008),
                 "lines": NEW(2008)},
         supply=SUPPLY(112, 96, 2600)),
]


def write(dirpath, system, files):
    if os.path.isdir(dirpath):
        shutil.rmtree(dirpath)
    os.makedirs(dirpath)
    with open(os.path.join(dirpath, "system.json"), "w") as f:
        json.dump(system, f, indent=1)
    for name, obj in files.items():
        with open(os.path.join(dirpath, name), "w") as f:
            json.dump(obj, f, indent=1)


def main():
    for spec in EXAMPLES:
        system, truth = build(spec)
        res = hyd.design_demand(system, truth["C"], truth["valves"])
        survey = {"note": "settled by the 2025 investigation's flow tests", "C": truth["C"],
                  "valves": truth["valves"]}
        write(os.path.join(DATA, "examples", spec["tag"]), system,
              {"expected.json": res, "survey.json": survey})
        print(spec["tag"], res)
    for spec in HIDDEN_SPECS:
        system, truth = build(spec)
        res = hyd.design_demand(system, truth["C"], truth["valves"])
        write(os.path.join(HIDDEN, spec["tag"]), system, {"truth.json": dict(truth, result=res)})
        print(spec["tag"], res)


if __name__ == "__main__":
    main()
