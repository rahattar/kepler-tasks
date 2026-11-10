"""Defective routes: each changes one thing in the reference method (the reverberation time of the hall as it is now,
the two configuration differences, the speed referral, the valid positions, the quarter space and the array radius,
the meter certificate) or takes a common shortcut, and is graded on the shipped seed and on the laboratory seeds
7101-7120. The last column counts the seeds on which the route gets everything right.

Every route that fails must fail at least one value by at least twice the grading tolerance, so that no single number
can be right under both answers to the choice the route makes. A route that passes is reported as passing: the choice
it makes does not decide the result, and it is listed so that the record says so.

    python3 authoring/evidence/route_study.py > authoring/evidence/route_study.txt
"""
import common as C

TOTAL = len(C.IDS) * len(C.KEYS)
BAR = 2.0 * C.S.TOL

ROUTES = [
    ("the environmental correction left out", dict(k2=False)),
    ("the environmental correction with 1 + S / A, the 4 dropped", dict(k2="nofour")),
    ("the acoustic report's reverberation time used", dict(absorption="report")),
    ("a reading spent on a reverberation measurement, so one difference is left", dict(absorption="rt")),
    ("the same, and one reverberation time for every band", dict(absorption="rt-mid")),
    ("the same, and the absorption area taken as 0.161 V T", dict(absorption="rt-inverse")),
    ("the speed referral left out, so C2, C5 and C6 stay as surveyed", dict(speed="none")),
    ("the speed referral taken as 20 lg instead of 50 lg", dict(speed="20")),
    ("the speed referral applied the wrong way", dict(speed="sign")),
    ("no configuration difference applied", dict(delta_mode="none")),
    ("the differences applied as one A-weighted figure", dict(delta_mode="dba")),
    ("the differences applied with the wrong sign", dict(delta_mode="sign")),
    ("only the two differences the September work orders name, C7's October one missed",
     dict(deltas=("C1", "C3"), certified=False)),
    ("C7 measured instead of taken from its certified insertion loss, so one difference is left",
     dict(deltas=("C7", "C1", "C3"), certified=False)),
    ("a reading spent on C8, whose cover was refitted before the survey, not after",
     dict(waste=("slm", "P70", "c8"))),
    ("a reading spent on a machine the speed rule settles", dict(waste=("slm", "P11", "c2"))),
    ("every position kept, no background subtracted", dict(drop="all", background="none")),
    ("every position kept, the first position's background for all", dict(drop="all", background="first")),
    ("every position kept, each position's own background subtracted", dict(drop="all")),
    ("the background rule applied but not the radius rule", dict(drop="background")),
    ("the machines against a wall taken to radiate into a half space", dict(surface="half")),
    ("the array radii taken from the register's nominal value", dict(surface="nominal")),
    ("the survey sheet's own machine column trusted", dict(labels="sheet")),
    ("no instrument certificate correction applied", dict(meter="none")),
    ("M-2's certificate applied to every row", dict(meter="m2")),
    ("M-9's certificate applied to every row", dict(meter="m9")),
    ("the levels averaged arithmetically, not in energy", dict(average="arith")),
    ("no readings at all: the report's reverberation time and no differences",
     dict(absorption="report", delta_mode="none")),
]


def main():
    print("route | right of %d (seed %d) | worst value | verdict | seeds with all right" % (TOTAL, C.SEED))
    matrix, thinroutes, passing = {}, [], []
    for name, kw in ROUTES:
        sheet, _ = C.solve_route(seed=C.SEED, **kw)
        n, err, (wm, wk, wv) = C.grade(sheet)
        allseeds = sum(C.grade(C.solve_route(seed=s, **kw)[0])[0] == TOTAL for s in C.SEEDS)
        matrix[name] = C.failed_items(err)
        if n == TOTAL:
            verdict, who = "passes", passing
        elif abs(wv) >= BAR:
            verdict, who = "fails, over the bar", None
        else:
            verdict, who = "fails, UNDER THE BAR", thinroutes
        if who is not None:
            who.append(name)
        print("%-66s | %2d | %s %-3s %+6.2f | %-19s | %2d of 20" % (name, n, wm, wk, wv, verdict, allseeds))
    print()
    print("%d of %d routes fail; each of them fails a value by at least the bar of %.1f dB%s" % (
        len(ROUTES) - len(passing), len(ROUTES), BAR,
        "" if not thinroutes else "; EXCEPT: %s" % ", ".join(thinroutes)))
    if passing:
        print("routes that pass, because the choice does not decide the result: %s" % ", ".join(passing))
    print()
    print("value: routes above that fail it")
    thin = []
    for m in C.IDS:
        row = []
        for k in C.KEYS:
            c = sum((m, k) in v for v in matrix.values())
            row.append("%s %d" % (k, c))
            if c < 3:
                thin.append("%s %s (%d)" % (m, k, c))
        print("%s: %s" % (m, "  ".join(row)))
    print()
    print("every value is failed by at least three routes" if not thin
          else "values failed by fewer than three routes: %s" % ", ".join(thin))


if __name__ == "__main__":
    main()
