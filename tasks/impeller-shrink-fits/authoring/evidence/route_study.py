"""Defective routes: each changes one thing in the reference method (dilatometer tests of the rotor steel to 180 C,
FV520B to 375 C and Ti-6Al-4V to 285 C, 42CrMo4 from the balance drum certificate's mill value; each bore at the top
of its range less an allowance) or takes a common shortcut, and is graded on the shipped seed and on the laboratory
seeds 5301-5320. A route that names a pick replaces the reference's pick with it (mid: the middle of the window the
route computes).

    python3 authoring/evidence/route_study.py > authoring/evidence/route_study.txt
"""
import common as C

R = ("26NiCrMoV14-5", 190)
FV, FV_LOW, TI, CR = ("FV520B", 375), ("FV520B", 240), ("Ti-6Al-4V", 285), ("42CrMo4", 220)
HAND_CR = {"42CrMo4": (220, 12.6e-6)}
HAND_TI = {"Ti-6Al-4V": (285, 9.2e-6)}
ROTOR_AS_CR = {"26NiCrMoV14-5": (190, (11.40 + (12.40 - 11.90) / 150.0 * 90) * 1e-6)}   # the 42CrMo4 slope

ROUTES = [
    ("FV520B tested at S2's 240 C limit, extrapolated to S6", dict(plan=[FV_LOW, TI, R])),
    ("the same, mid-window pick", dict(plan=[FV_LOW, TI, R], pick="mid")),
    ("the same, FV520B tested second, mid-window pick", dict(plan=[TI, FV_LOW, R], pick="mid")),
    ("the same, FV520B tested last, mid-window pick", dict(plan=[TI, R, FV_LOW], pick="mid")),
    ("42CrMo4 tested at 220 C, the rotor steel from the 20-100 C table", dict(plan=[FV, TI, CR])),
    ("the same, mid-window pick", dict(plan=[FV, TI, CR], pick="mid")),
    ("the same, the rotor steel at the slope of 42CrMo4", dict(plan=[FV, TI, CR], assumed=ROTOR_AS_CR)),
    ("the mill value not used: 42CrMo4 from the table", dict(use_mill=False)),
    ("the mill value not used: a handbook 12.6 for 42CrMo4 to 220 C", dict(use_mill=False, assumed=HAND_CR)),
    ("the rotor steel and 42CrMo4 tested; Ti-6Al-4V from the table", dict(plan=[FV, R, CR])),
    ("the same with a handbook 9.2 for Ti-6Al-4V to 285 C", dict(plan=[FV, R, CR], assumed=HAND_TI)),
    ("the 375 C FV520B reading used flat (no interpolation)", dict(flat=True)),
    ("no tests: the 20-100 C table for every material", dict(plan=[], use_mill=False)),
    ("seats taken as at 20 C (bay temperature ignored)", dict(bay=False)),
    ("clearance checked against the seat at 20 C", dict(bay_clear=False)),
    ("trip at the OEM sheet's 105 %", dict(trip=1.05)),
    ("maintenance log not applied (S5 FV520B, trip 105 %)", dict(use_log=False)),
    ("the micrometer's calibration error not applied", dict(mic=False)),
    ("S4's spin test taken as at MCS (it was run at 10500 rpm)", dict(spin=False)),
    ("S2's heating limit from its certificate (260 C), not the log's recoating (240 C)", dict(recoat=False)),
    ("tests in part order, bore 1 sd of the stated repeatability (0.3 %) inside the clearance limit",
     dict(plan=C.PART_PLAN, allowance=0.003)),
    ("seat growth at speed not credited, mid-window pick", dict(seat_growth=False, pick="mid")),
]


def main():
    print("route | right of 8 (seed %d) | worst part, requirement, margin | seeds 5301-5320 with 8 | parts failed on the shipped seed" % C.SEED)
    matrix = {}
    for name, kw in ROUTES:
        sh, _ = C.solve_route(seed=C.SEED, **kw)
        n, res, (wk, wq, wv) = C.grade(sh)
        allseeds = sum(C.grade(C.solve_route(seed=s, **kw)[0])[0] == 8 for s in C.SEEDS)
        failed = [k for k in C.IDS if not res[k][0]]
        matrix[name] = failed
        print("%-72s | %d | %s %-6s %+.3f | %2d of 20 | %s" % (name, n, wk, wq, wv, allseeds, " ".join(failed)))
    print()
    print("part: routes above that fail it")
    for k in C.IDS:
        print("%s: %d" % (k, sum(k in v for v in matrix.values())))


if __name__ == "__main__":
    main()
