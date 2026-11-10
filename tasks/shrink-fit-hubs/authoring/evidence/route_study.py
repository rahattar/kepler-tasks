"""Defective routes: each changes one thing in the reference method (top of the range less an allowance, steel
expansion measured, friction tested at each pair's lowest pressure) or takes a common shortcut, and is graded on the
shipped seed and on the laboratory seeds 7101-7120. Routes that name a mid-window pick or a friction plan replace the
reference's pick or plan with it.

    python3 authoring/evidence/route_study.py > authoring/evidence/route_study.txt
"""
import common as C

HB = {"dry": 0.15, "oiled": 0.10, "paste": 0.08}
ROUTES = [
    ("maintenance log missed for J07 (oil)", dict(log=("J10", "J11"))),
    ("maintenance log missed for J10 (solid shaft)", dict(log=("J07", "J11"))),
    ("maintenance log missed for J11 (55 kW torque)", dict(log=("J07", "J10"))),
    ("J07 log missed, with friction at each pair's highest pressure and a mid-window pick",
     dict(log=("J10", "J11"), friction="highest", pick="mid")),
    ("J11 log missed, with friction at each pair's highest pressure and a mid-window pick",
     dict(log=("J07", "J10"), friction="highest", pick="mid")),
    ("hub stress checked at rest only", dict(running_stress=False)),
    ("thermal change in running taken as a loss only", dict(clip_gain=True)),
    ("steady running ignored (torque and stress at rest)", dict(running=False)),
    ("smoothing not deducted", dict(smooth=False)),
    ("smoothing not deducted, friction at each pair's highest pressure, mid-window pick",
     dict(smooth=False, friction="highest", pick="mid")),
    ("steel expansion from the 20-100 C table", dict(cte="table")),
    ("steel expansion assumed 12.8 (handbook)", dict(cte="assume", cte_assumed=12.8e-6)),
    ("steel expansion assumed 13.0 (handbook)", dict(cte="assume", cte_assumed=13.0e-6)),
    ("friction at 80 MPa for every pair, mid-window pick", dict(friction="flat", flat_p=80, pick="mid")),
    ("friction at 80 MPa for every pair, least + 3 um", dict(friction="flat", flat_p=80, pick="min+3")),
    ("friction at each pair's lowest pressure, mid-window pick", dict(friction="lowest", pick="mid")),
    ("handbook friction (0.15 / 0.10 / 0.08), mid-window pick", dict(friction="handbook", handbook=HB, pick="mid")),
    ("handbook friction, least + 3 um", dict(friction="handbook", handbook=HB, pick="min+3")),
]


def main():
    print("route | right of 12 (seed %d) | worst joint, requirement, margin | seeds 7101-7120 with 12 | joints failed on the shipped seed" % C.SEED)
    matrix = {}
    for name, kw in ROUTES:
        f, _ = C.solve_route(seed=C.SEED, **kw)
        n, res, (wk, wq, wv) = C.grade(f)
        allseeds = sum(C.grade(C.solve_route(seed=s, **kw)[0])[0] == 12 for s in C.SEEDS)
        failed = [k for k in C.IDS if not res[k][0]]
        matrix[name] = failed
        print("%-66s | %2d | %s %-6s %+.3f | %2d of 20 | %s" % (name, n, wk, wq, wv, allseeds, " ".join(failed)))
    print()
    print("joint: routes above that fail it")
    for k in C.IDS:
        print("%s: %d" % (k, sum(k in v for v in matrix.values())))


if __name__ == "__main__":
    main()
