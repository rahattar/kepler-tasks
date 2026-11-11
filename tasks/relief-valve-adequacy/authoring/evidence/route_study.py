#!/usr/bin/env python3
"""Defective routes through the assessment: each takes one wrong turn and is graded against the sealed answer.

Every route must fail on the shipped records. The last column counts the laboratory seeds on which the route still
gets all nine valves right; a route that passes on many seeds is held up by scatter rather than by the design.

    python3 route_study.py [--seeds]
"""
import os
import shutil
import sys
import tempfile

import common
import solve

SEEDS = list(range(7301, 7321))

ROUTES = [
    ("the data sheet coefficient for every control valve", dict(cv="sheet")),
    ("a linear characteristic for every control valve", dict(cv="linear")),
    ("the largest logged flow taken as the relieving rate", dict(cv="maxflow")),
    ("the feed meter read as indicated", dict(meter="raw")),
    ("the reboiler coefficient-area from the data sheet duty", dict(ua="design")),
    ("the data sheet duty taken as the relieving duty", dict(ua="duty")),
    ("no credit for instrumented protection", dict(credit="none")),
    ("credit taken without testing independence", dict(credit="all")),
    ("credit taken without the proof test interval", dict(credit="proof")),
    ("the two-thirds rule applied to the wrong ratio", dict(rupture="skip")),
    ("one tube area discharging instead of two", dict(rupture="one")),
    ("the register's orifice letter", dict(orifice="register")),
    ("the register's set pressure", dict(setp="register")),
    ("the rupture disc combination factor left out", dict(disc="ignore")),
    ("elevation changes since the data book left out", dict(raised="ignore")),
    ("no insulation credit anywhere", dict(insul="none")),
    ("the viscosity correction left at 1", dict(kv="one")),
    ("the pump's data sheet curve", dict(pump="sheet")),
    ("properties at the item's normal pressure", dict(props="normal")),
    ("the inlet line rule not checked", dict(inlet="skip")),
    ("10 per cent accumulation for the fire case", dict(accum="flat")),
    ("no drainage or firefighting credit", dict(firec="bare")),
    ("the whole shell taken as wetted", dict(level="full")),
    ("the vapour discharge coefficient used for liquid", dict(kdliq="vap")),
]


def study_sheet(d):
    """The 2019 study's findings read off as the answer."""
    rows = []
    for r in common.solve._md_table(d["relief_study_2019"], "| valve | governing contingency |"):
        rows.append((r["valve"], r["governing contingency"].strip("`"),
                     float(r["required area, mm2"]), r["finding"]))
    return sorted(rows)


def main():
    want_seeds = "--seeds" in sys.argv
    mod, tru = common.truth()
    d = solve.load(common.DATA)
    tol = mod.TOL

    per_valve = {v: 0 for v in tru}
    results = []
    for name, sw in ROUTES:
        n, notes = common.compare(common.run(d, **sw), tru, tol)
        for v in notes:
            if notes[v]:
                per_valve[v] += 1
        results.append((name, n, notes))
    n, notes = common.compare(study_sheet(d), tru, tol)
    for v in notes:
        if notes[v]:
            per_valve[v] += 1
    results.append(("the 2019 study's findings taken as the answer", n, notes))

    counts = {}
    if want_seeds:
        tmp = tempfile.mkdtemp(prefix="rv_seed_")
        os.environ["GEN_QUIET"] = "1"
        import gen
        try:
            for seed in SEEDS:
                out = os.path.join(tmp, "data")
                shutil.rmtree(out, ignore_errors=True)
                os.makedirs(os.path.join(out, "docs"), exist_ok=True)
                gen.main(out, seed)
                ds = solve.load(out)
                for name, sw in ROUTES:
                    k, _ = common.compare(common.run(ds, **sw), tru, tol)
                    counts[name] = counts.get(name, 0) + (1 if k == len(tru) else 0)
                k, _ = common.compare(study_sheet(ds), tru, tol)
                counts["the 2019 study's findings taken as the answer"] = \
                    counts.get("the 2019 study's findings taken as the answer", 0) + (1 if k == len(tru) else 0)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    print("Defective routes, graded against the sealed definition. Area tolerance %.3f relative.\n" % tol)
    print("| Route | Right of 9 | Worst valve | Seeds with 9 |")
    print("|---|---|---|---|")
    for name, n, notes in results:
        seeds = "%d of %d" % (counts.get(name, 0), len(SEEDS)) if want_seeds else "-"
        print("| %s | %d | %s | %s |" % (name, n, common.worst(notes) or "-", seeds))
    print("\nRoutes failing each valve:")
    for v in sorted(per_valve):
        print("  %s %d" % (v, per_valve[v]))
    bad = [v for v in per_valve if per_valve[v] < 3]
    full = [name for name, n, _ in results if n == len(tru)]
    print("\nvalves failed by fewer than 3 routes: %s" % (", ".join(sorted(bad)) if bad else "none"))
    print("routes that pass on the shipped records: %s" % (", ".join(full) if full else "none"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
