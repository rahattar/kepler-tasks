"""Builds the core's packages: the visible examples (with their expected results) and the hidden systems (with
their truth). Run: python3 gen.py [SEED]

A package is a system as the site's records describe it (system.json) and the readings of its re-rating
campaign (campaign.csv). The truth is the system as it stands, which the records need not match:

- a group the pipe register gives a C for may have aged below it (`WRONG`);
- a valve may be off its seat (`valves`: a factor on its equivalent length);
- the campaign sheet may carry a gauge with a zero error, two ports entered against each other's tags, or a
  run whose flow was written down wrong (`sheet`).

Hidden shift, on purpose: see SHIFT below, written into each hidden truth.json.
"""
import csv
import json
import os
import random
import shutil
import sys

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
    valve_pipe = {}

    def pipe(a, b, size, length, group, fittings=(), valve=None):
        group = alias.get(group, group)
        pid[0] += 1
        pipes.append({"id": "P%04d" % pid[0], "from": a, "to": b, "size": size,
                      "schedule": spec["schedules"].get(group, "40"), "length_ft": round(length, 2),
                      "fittings": list(fittings), "group": group})
        if valve:
            valve_pipe[valve] = pipes[-1]["id"]
        return pipes[-1]["id"]

    feed_len = spec["feed_ft"]
    node("R0", -feed_len, -Sl, 0.0)
    node("R1", -feed_len, -Sl, spec["riser_top_ft"])
    pipe("R0", "R1", spec["feed_size"], spec["riser_top_ft"], "riser", ["check valve", "gate valve"], "riser")
    node("A0", 0.0, 0.0)
    pipe("R1", "A0", spec["feed_size"], feed_len + Sl, "feed", ["elbow", "elbow", "gate valve"], "feed")
    xB = (NH + 0.5) * Sb
    mid = NL // 2
    prev = "A0"
    for j in range(1, NL + 1):
        y = j * Sl - Sl / 2
        node("A%d" % j, 0.0, y)
        sect = j - 1 == mid
        pipe(prev, "A%d" % j, spec["crossA_size"], Sl if j > 1 else Sl / 2, "crossA",
             ["butterfly valve"] if sect else [], "sectional" if sect else None)
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
    groups = {g: {"installed": info["installed"], "service": info["service"], "C": info["register"]}
              for g, info in spec["groups"].items()}
    t1, t2 = max(2, NL // 3), (2 * NL) // 3 + 1
    outlets = [{"id": "FC-A", "node": "A%d" % NL, "K": spec.get("flush_K", 140.0),
                "description": "flushing connection, far end of cross main A"}]
    gauges = ["R1", "A%d" % t1, "A%d" % t2, "A%d" % NL, "L1H%d" % NH, "L%dH%d" % (NL, NH)]
    if grid:
        outlets.append({"id": "FC-B", "node": "B%d" % NL, "K": spec.get("flush_K", 140.0),
                        "description": "flushing connection, far end of cross main B"})
        outlets.append({"id": "FC-B1", "node": "B1", "K": spec.get("flush_K", 140.0),
                        "description": "flushing connection, near end of cross main B"})
        gauges += ["A1", "A%d" % mid, "B1", "B%d" % mid, "B%d" % NL, "L%dH%d" % (t1, NH // 2),
                   "L%dH%d" % (t2, NH // 2)]
    else:
        outlets.append({"id": "DR-L", "node": "L%dH%d" % (mid, NH), "K": spec.get("drain_K", 22.0),
                        "description": "auxiliary drain, end of branch line %d" % mid})
        gauges += ["L%dH%d" % (mid, NH), "L%dH%d" % (mid, NH // 2)]
    system = {
        "tag": spec["tag"], "kind": spec["kind"],
        "nodes": nodes, "pipes": pipes, "groups": groups,
        "lines": lines, "heads": heads, "riser_base": "R0",
        "hazard": {"density_gpm_ft2": spec["density"], "area_ft2": spec["area"], "hose_gpm": spec["hose"],
                   "spacing_branch_ft": Sb, "spacing_lines_ft": Sl},
        "outlets": outlets, "gauge_ports": sorted(set(gauges)),
    }
    truth = {"C": {g: info["C"] for g, info in spec["groups"].items()},
             "valves": {valve_pipe[v]: f for v, f in spec.get("valves", {}).items()}}
    return system, truth


def plan_of(system, truth, spec):
    """The campaign's runs: a static run, each outlet of the plan at its flows, a closing static run."""
    outs = {o["id"]: o for o in system["outlets"]}
    plan = [(None, 0.0)]
    for oid, fracs in spec["plan"]:
        lim = hyd.outlet_limit(system, truth, spec["supply"], outs[oid])
        for fr in fracs:
            plan.append((oid, float(5 * round(fr * lim / 5))))
    plan.append((None, 0.0))
    return plan


def sheet(system, truth, spec, seed):
    """The campaign as it was written down: rows (run, outlet, flow_gpm, port, reading_psi)."""
    rng = random.Random("%s/%d" % (spec["tag"], seed))
    runs = hyd.campaign(system, truth, spec["supply"], plan_of(system, truth, spec), rng)
    base = system["riser_base"]
    ports = [base] + list(system["gauge_ports"])
    faults = spec.get("sheet", [])
    zero = {f["port"]: f["psi"] for f in faults if f["kind"] == "zero"}
    swap = {}
    for f in faults:
        if f["kind"] == "swap":
            a, b = f["ports"]
            swap[a], swap[b] = b, a
    wrong_flow = {f["run"]: f["recorded"] for f in faults if f["kind"] == "flow"}
    rows = []
    for k, run in enumerate(runs, start=1):
        got = {n: hyd.read(run["p"][n] + zero.get(n, 0.0), rng) for n in ports}
        q = run["flow_gpm"]
        if k in wrong_flow:
            q = float(wrong_flow[k]) if wrong_flow[k] > 5 else float(5 * round(wrong_flow[k] * q / 5))
        for n in ports:
            rows.append([k, run["outlet"] or "", "%.0f" % q, n, "%.1f" % got[swap.get(n, n)]])
    return rows, [(r["outlet"], r["flow_gpm"]) for r in runs]


def sz(*breaks):
    """Branch-line size by column: [(last column, size), ...] then the rest."""
    def f(i, nh):
        for last, s in breaks:
            if i <= last:
                return s
        return breaks[-1][1]
    return f


def NEW(yr, c=120):
    return {"installed": yr, "service": "wet, city water", "register": c, "C": c}


def OLD(yr, c):
    """Aged pipe the register has no C for."""
    return {"installed": yr, "service": "wet, city water", "register": None, "C": c}


def WRONG(yr, register, c):
    """Pipe the register gives a C for, which has aged below it."""
    return {"installed": yr, "service": "wet, city water", "register": register, "C": c}


def SUPPLY(s, r, q):
    return {"static_psi": s, "residual_psi": r, "flow_gpm": q}


TREE_PLAN = [("FC-A", (0.45, 0.7, 0.92)), ("DR-L", (0.5, 0.75, 0.95))]
GRID_PLAN = [("FC-A", (0.6, 0.9)), ("FC-B", (0.6, 0.9)), ("FC-B1", (0.6, 0.9))]
COMMON = dict(K=8.0, hose=250, spacing_branch_ft=10.0, spacing_lines_ft=12.0, ceiling_ft=28.0,
              riser_top_ft=24.0, schedules={})


def write(dirpath, system, rows, files):
    if os.path.isdir(dirpath):
        shutil.rmtree(dirpath)
    os.makedirs(dirpath)
    with open(os.path.join(dirpath, "system.json"), "w") as f:
        json.dump(system, f, indent=1)
    with open(os.path.join(dirpath, "campaign.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["run", "outlet", "flow_gpm", "port", "reading_psi"])
        w.writerows(rows)
    for name, obj in files.items():
        with open(os.path.join(dirpath, name), "w") as f:
            json.dump(obj, f, indent=1)


def make(spec, seed):
    system, truth = build(spec)
    rows, actual = sheet(system, truth, spec, seed)
    res = hyd.design_demand(system, truth["C"], truth["valves"])
    return system, truth, rows, actual, res


def main(seed=1):
    from specs import EXAMPLES, HIDDEN_SPECS
    for spec in EXAMPLES:
        system, truth, rows, actual, res = make(spec, seed)
        write(os.path.join(DATA, "examples", spec["tag"]), system, rows, {"expected.json": res})
        print(spec["tag"], res)
    for spec in HIDDEN_SPECS:
        system, truth, rows, actual, res = make(spec, seed)
        write(os.path.join(HIDDEN, spec["tag"]), system, rows,
              {"truth.json": dict(truth, sheet=spec.get("sheet", []), actual_runs=actual,
                                  shift=spec.get("shift", ""), result=res)})
        print(spec["tag"], res)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 1)
