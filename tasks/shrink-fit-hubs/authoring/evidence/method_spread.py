"""Correct methods: variations of a sound method, graded on the shipped seed and on the laboratory seeds 7101-7120.

    python3 authoring/evidence/method_spread.py > authoring/evidence/method_spread.txt
"""
import common as C

METHODS = [
    ("reference (solution/solve.py)", {}),
    ("dilatometer test last", dict(order=2)),
    ("steel expansion measured to 260 C", dict(cte_T=260)),
    ("steel expansion measured to 270 C", dict(cte_T=270)),
    ("steel expansion measured to 280 C", dict(cte_T=280)),
    ("steel expansion measured to 300 C", dict(cte_T=300)),
    ("friction at each pair's highest pressure", dict(friction="highest")),
    ("friction at each pair's median pressure", dict(friction="median")),
    ("friction at 80 MPa for every pair", dict(friction="flat", flat_p=80)),
    ("every hub heated to its heating limit", dict(oven="limit")),
    ("allowance 1.5 % of the oven expansion", dict(allowance=0.015)),
    ("allowance 3 % of the oven expansion", dict(allowance=0.03)),
    ("friction at each pair's highest pressure, mid-window pick", dict(friction="highest", pick="mid")),
    ("friction at each pair's median pressure, mid-window pick", dict(friction="median", pick="mid")),
    ("pressed specimens at each pair's highest pressure, mid-window pick (conservative)",
     dict(friction="highest", shrink=False, pick="mid")),
    ("top of the range with no slip test at all", dict(friction="none")),
]


def main():
    print("method | right of 12 (seed %d) | smallest margin: torque, stress, clearance | seeds 7101-7120 with 12" % C.SEED)
    for name, kw in METHODS:
        f, _ = C.solve_route(seed=C.SEED, **kw)
        n, res, _ = C.grade(f)
        allseeds = sum(C.grade(C.solve_route(seed=s, **kw)[0])[0] == 12 for s in C.SEEDS)
        print("%-58s | %2d | %+.4f %+.4f %+.4f | %2d of 20" % (name, n, C.least(res, "slip"), C.least(res, "stress"), C.least(res, "clear"), allseeds))


if __name__ == "__main__":
    main()
