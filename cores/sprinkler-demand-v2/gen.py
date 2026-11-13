"""Builds the v2 core: three examples with results, one pending package without, eight hidden systems.

v2 = v0 (the program designs its one field flow test) plus flow tests on file in every package. In the pending
package and in six hidden systems one group the register carries a C for has aged since: the tests on file
show it (a drop between two gauges well beyond what the registered C gives) and nothing lists it. The examples
with results have no such group. Hidden systems are no larger than the largest example. Run: python3 gen.py
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
        outlets.append({"id": "DR-L", "node": "L%dH%d" % (NL // 2, NH), "K": spec.get("drain_K", 45.0),
                        "description": "auxiliary drain, end of branch line %d" % (NL // 2)})
        gauges.append("L%dH%d" % (NL // 2, NH))
        gauges.append("A%d" % (NL // 2))
    gauges += ["R1", "A1", "A%d" % (NL // 2), "A%d" % NL, "L%dH%d" % (NL, NH), "L1H%d" % NH]
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
    truth = {"C": {g: info.get("now", info["C"]) for g, info in spec["groups"].items()}, "valves": {}}
    for v in valves_unverified:
        truth["valves"][v["pipe"]] = spec["valve_factor"]
    # the flow tests on file: the system as it was in the year of the tests, every valve open
    then = {"C": {g: info.get("then", info["C"] if info.get("known", True) else
                              round(info["C"] + 0.35 * (120 - info["C"]))) for g, info in spec["groups"].items()},
            "valves": {v["pipe"]: 1.0 for v in valves_unverified}}
    rng = random.Random(spec.get("file_seed", 7) * 1000 + NL * 31 + NH)
    mid = NL // 2
    plan = [("FC-A", ["R1", "A1"]), ("FC-A", ["A%d" % mid, "A%d" % NL])]
    if grid:
        plan.append(("FC-B", ["B1", "B%d" % NL]))
    else:
        plan.append(("DR-L", ["A%d" % mid, "L%dH%d" % (mid, NH)]))
    on_file = []
    year = spec.get("file_year", 2019)
    for n, (oid, gs) in enumerate(plan):
        K = [o["K"] for o in outlets if o["id"] == oid][0]
        for Q in ([600, 450, 300, 200] if K > 100 else [160, 120, 90, 70, 50, 35]):
            rep = hyd.field_test(system, then, {"outlet": oid, "flow_gpm": Q, "gauges": gs}, rng)
            if "refused" not in rep:
                break
        assert "refused" not in rep, (spec["tag"], oid, rep)
        on_file.append(dict({"date": "%d-05-%02d" % (year, 13 + n)}, **rep))
    system["tests_on_file"] = on_file
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
# a group the register carries a C for, which has aged since: C at the tests on file, C as it stands
AGED = lambda yr, then, now: {"installed": yr, "service": "wet, city water", "C": 120, "known": True,  # noqa: E731
                              "then": then, "now": now}
SUPPLY = lambda s, r, q: {"static_psi": s, "residual_psi": r, "flow_gpm": q}                   # noqa: E731

COMMON = dict(K=8.0, hose=250, spacing_branch_ft=10.0, spacing_lines_ft=12.0, ceiling_ft=28.0,
              riser_top_ft=24.0, schedules={})

EXAMPLES = [
    dict(COMMON, tag="WH-A", kind="tree", lines=14, heads=10, feed_ft=180, feed_size="6", crossA_size="6",
         branch_size=sz((6, "2"), (99, "1-1/2")), density=0.20, area=2000,
         groups={"riser": NEW(2006), "feed": OLD(1979, 88), "crossA": OLD(1979, 88), "lines": NEW(2006)},
         supply=SUPPLY(92, 74, 1500)),
    dict(COMMON, tag="WH-B", kind="grid", lines=24, heads=20, feed_ft=150, feed_size="6", crossA_size="6",
         crossB_size="4", branch_size=sz((99, "1-1/2")), density=0.30, area=2500, slope_along=0.02,
         alias={"crossA": "mains", "crossB": "mains"},
         groups={"riser": NEW(1984), "feed": NEW(1984), "mains": OLD(1984, 95), "lines": OLD(1984, 78)},
         supply=SUPPLY(105, 88, 2000)),
    dict(COMMON, tag="WH-C", kind="tree", lines=12, heads=9, feed_ft=240, feed_size="6", crossA_size="4",
         branch_size=sz((5, "2"), (99, "1-1/2")), density=0.15, area=1500,
         groups={"riser": NEW(1991), "feed": OLD(1991, 92), "crossA": NEW(1991), "lines": NEW(1991)},
         feed_valve_unverified=True, valve_factor=400.0, supply=SUPPLY(95, 80, 1200)),
]

PENDING = [
    dict(COMMON, tag="PN-1", kind="tree", lines=16, heads=10, feed_ft=420, feed_size="6", crossA_size="6",
         branch_size=sz((6, "2"), (99, "1-1/2")), density=0.20, area=1800,
         groups={"riser": NEW(1994), "feed": AGED(1994, 94, 82), "crossA": OLD(1994, 86), "lines": NEW(1994)},
         supply=SUPPLY(98, 80, 1500)),
]

HIDDEN_SPECS = [
    dict(COMMON, tag="DC-1", kind="grid", lines=24, heads=20, feed_ft=200, feed_size="8", crossA_size="4",
         crossB_size="4", branch_size=sz((99, "1-1/2")), density=0.25, area=2500,
         groups={"riser": NEW(2003), "feed": NEW(2003), "crossA": AGED(2003, 100, 80), "crossB": OLD(1981, 70),
                 "lines": NEW(2003)},
         supply=SUPPLY(110, 90, 2500),
         shift="the aged registered group is cross main A of a grid (pending: the feed main of a tree)"),
    dict(COMMON, tag="DC-2", kind="grid", lines=22, heads=18, feed_ft=160, feed_size="6", crossA_size="6",
         crossB_size="4", branch_size=sz((99, "1-1/2")), density=0.30, area=2500,
         groups={"riser": NEW(2010), "feed": NEW(2010), "crossA": NEW(2010), "crossB": NEW(2010),
                 "lines": OLD(1988, 84)},
         sectional_valve_after=11, sectional_valve_unverified=True, valve_factor=150.0,
         supply=SUPPLY(100, 84, 2200),
         shift="no aged registered group; an unverified valve on a grid's cross main (example: a tree's feed)"),
    dict(COMMON, tag="DC-3", kind="tree", lines=18, heads=12, feed_ft=380, feed_size="6", crossA_size="6",
         branch_size=sz((6, "3"), (99, "2-1/2")), density=0.45, area=1800, K=16.8,
         groups={"riser": NEW(2001), "feed": AGED(2001, 96, 80), "crossA": OLD(1976, 74), "lines": NEW(2001)},
         supply=SUPPLY(115, 95, 2000),
         shift="aged feed main beside an open cross main, at a density and K-factor beyond the examples'"),
    dict(COMMON, tag="DC-4", kind="grid", lines=24, heads=20, feed_ft=220, feed_size="8", crossA_size="6",
         crossB_size="6", branch_size=sz((99, "1-1/2")), density=0.20, area=3000, slope_across=0.01,
         alias={"crossA": "mains", "crossB": "mains"},
         groups={"riser": NEW(1990), "feed": NEW(1990), "mains": OLD(1990, 96), "lines": OLD(1990, 82)},
         supply=SUPPLY(108, 92, 3000),
         shift="no aged registered group; a ceiling sloped across the lines"),
    dict(COMMON, tag="DC-5", kind="tree", lines=12, heads=10, feed_ft=420, feed_size="6", crossA_size="4",
         branch_size=sz((6, "2"), (99, "1-1/2")), density=0.20, area=1500, riser_top_ft=60.0,
         ceiling_ft=64.0, groups={"riser": NEW(1998), "feed": OLD(1972, 75), "crossA": AGED(1998, 102, 84),
                                   "lines": NEW(1998)},
         supply=SUPPLY(78, 52, 1000),
         shift="aged cross main beside an open feed main; a 60 ft riser and a weak supply"),
    dict(COMMON, tag="DC-6", kind="grid", lines=22, heads=18, feed_ft=300, feed_size="6", crossA_size="6",
         crossB_size="4", branch_size=sz((99, "1-1/2")), density=0.30, area=2500,
         groups={"riser": NEW(2012), "feed": AGED(1986, 98, 80), "crossA": NEW(2012), "crossB": OLD(1979, 72),
                 "lines": NEW(2012)},
         supply=SUPPLY(104, 88, 2400),
         shift="aged feed main of a grid beside an open far cross main"),
    dict(COMMON, tag="DC-7", kind="tree", lines=14, heads=11, feed_ft=260, feed_size="6", crossA_size="4",
         branch_size=sz((6, "2"), (99, "1-1/2")), density=0.20, area=1800,
         groups={"riser": NEW(1995), "feed": NEW(1995), "crossA": AGED(1982, 100, 78), "lines": NEW(1995)},
         feed_valve_unverified=True, valve_factor=350.0, supply=SUPPLY(110, 92, 1600),
         shift="aged cross main beside an unverified valve, no group left open by the register"),
    dict(COMMON, tag="DC-8", kind="grid", lines=22, heads=18, feed_ft=340, feed_size="6", crossA_size="6",
         crossB_size="4", branch_size=sz((99, "1-1/2")), density=0.35, area=2500, slope_across=0.025,
         groups={"riser": NEW(2008), "feed": AGED(1985, 96, 78), "crossA": OLD(1985, 90), "crossB": NEW(2008),
                 "lines": NEW(2008)},
         supply=SUPPLY(112, 96, 2600),
         shift="aged feed main of a grid beside an open cross main; a ceiling sloped across the lines"),
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
    for spec in PENDING:
        system, truth = build(spec)
        write(os.path.join(DATA, "pending", spec["tag"]), system, {})
        reg = {g: (v["C"] or truth["C"][g]) for g, v in system["groups"].items()}
        print(spec["tag"], hyd.design_demand(system, truth["C"], truth["valves"]), "| by the register:",
              hyd.design_demand(system, reg, truth["valves"]))
    manifest = {}
    for spec in HIDDEN_SPECS:
        system, truth = build(spec)
        res = hyd.design_demand(system, truth["C"], truth["valves"])
        reg = {g: (v["C"] or truth["C"][g]) for g, v in system["groups"].items()}
        byreg = hyd.design_demand(system, reg, truth["valves"])
        write(os.path.join(HIDDEN, spec["tag"]), system, {"truth.json": dict(truth, result=res)})
        manifest[spec["tag"]] = {"shift": spec["shift"], "register_error_pct":
                                 round(100 * (byreg["pressure_psi"] / res["pressure_psi"] - 1), 1)}
        print(spec["tag"], res, "| by the register: %+.1f%%" % manifest[spec["tag"]]["register_error_pct"])
    with open(os.path.join(HERE, "core", "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)


if __name__ == "__main__":
    main()
