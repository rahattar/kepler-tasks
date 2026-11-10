"""Answers made without the laboratory, and the parts each gets right (free passes).

    python3 authoring/evidence/null_baselines.py > authoring/evidence/null_baselines.txt
"""
import common as C

S = C.S


def ratio_sheet(r, oven_limit=True):
    """mean interference r um per mm of seat diameter on the seat as read; every part at its heating limit"""
    sh = {}
    for k, j in S.PARTS.items():
        seat_read = round(S.seat_bay(j), 3)
        sh[k] = (round(seat_read - r * j["d"] * 1e-3, 3), int(j["Tlim"]))
    return sh


def line(name, sheet):
    n, res, _ = C.grade(sheet)
    print("%-78s %d of 8  right: %s" % (name, n, " ".join(k for k in C.IDS if res[k][0]) or "-"))


def main():
    line("1.0 um per mm of the seat as read, every part at its heating limit", ratio_sheet(1.0))
    line("1.5 um per mm of the seat as read, every part at its heating limit", ratio_sheet(1.5))
    best = max((C.grade(ratio_sheet(r / 100.0))[0], r / 100.0) for r in range(30, 400))
    line("best single um per mm (%.2f, chosen with the truth), at the heating limits" % best[1], ratio_sheet(best[1]))
    line("the reference model with no tests (the 20-100 C table, and the mill value for 42CrMo4)", C.solve_route(plan=[])[0])
    line("the reference model with the 20-100 C table for every material", C.solve_route(plan=[], use_mill=False)[0])
    line("no tests, the maintenance log not applied, seats taken as at 20 C",
         C.solve_route(plan=[], use_log=False, bay=False, use_mill=False)[0])
    print()
    print("parts that some single um-per-mm ratio (heating limit) gets right, with the ratios that do:")
    for k in C.IDS:
        j = S.PARTS[k]
        rs = [r / 100.0 for r in range(30, 400) if S.part_ok(k, *ratio_sheet(r / 100.0)[k])[0]]
        print("%s %s" % (k, ("%.2f-%.2f" % (rs[0], rs[-1])) if rs else "none"))


if __name__ == "__main__":
    main()
