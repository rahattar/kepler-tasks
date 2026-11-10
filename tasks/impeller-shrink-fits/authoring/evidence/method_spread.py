"""Correct methods: variations of a sound method, graded on the shipped seed and on the laboratory seeds 5301-5320.

    python3 authoring/evidence/method_spread.py > authoring/evidence/method_spread.txt
"""
import common as C

METHODS = [
    ("reference (solution/solve.py)", {}),
    ("tests in another order (Ti-6Al-4V, FV520B, rotor steel)", dict(plan=list(reversed(C.REF_PLAN)))),
    ("tests in part order (FV520B, Ti-6Al-4V, rotor steel)", dict(plan=C.PART_PLAN)),
    ("the rotor steel tested to 200 C", dict(plan=[("26NiCrMoV14-5", 200), ("FV520B", 375), ("Ti-6Al-4V", 285)])),
    ("the rotor steel tested to 250 C", dict(plan=[("26NiCrMoV14-5", 250), ("FV520B", 375), ("Ti-6Al-4V", 285)])),
    ("FV520B tested to 400 C (above every FV520B limit)", dict(plan=[("26NiCrMoV14-5", 190), ("FV520B", 400), ("Ti-6Al-4V", 285)])),
    ("Ti-6Al-4V tested to 300 C", dict(plan=[("26NiCrMoV14-5", 190), ("FV520B", 375), ("Ti-6Al-4V", 300)])),
    ("every part heated to its limit", dict(oven="limit")),
    ("allowance 1 % of the oven expansion", dict(allowance=0.01)),
    ("allowance 2 % of the oven expansion", dict(allowance=0.02)),
    ("middle of the window", dict(pick="mid")),
    ("least of the window + 2 um", dict(pick="min+2")),
]


def main():
    print("method | right of 8 (seed %d) | smallest margin: retention, stress, clearance | seeds 5301-5320 with 8" % C.SEED)
    for name, kw in METHODS:
        sh, _ = C.solve_route(seed=C.SEED, **kw)
        n, res, _ = C.grade(sh)
        allseeds = sum(C.grade(C.solve_route(seed=s, **kw)[0])[0] == 8 for s in C.SEEDS)
        print("%-56s | %d | %+.4f %+.4f %+.4f | %2d of 20" % (name, n, C.least(res, "ret"), C.least(res, "stress"),
                                                            C.least(res, "clear"), allseeds))


if __name__ == "__main__":
    main()
