"""Answers made without the laboratory, and the joints each gets right (free passes).

    python3 authoring/evidence/null_baselines.py > authoring/evidence/null_baselines.txt
"""
import common as C

S = C.S
HB = {"dry": 0.15, "oiled": 0.10, "paste": 0.08}


def ratio_answer(r):
    """mean interference r x d (um per mm), every hub at its heating limit"""
    return {k: (int(round(r * S.JOINTS[k]["d"])), int(S.JOINTS[k]["Tlim"])) for k in C.IDS}


def line(name, fits):
    n, res, _ = C.grade(fits)
    print("%-72s %2d of 12  right: %s" % (name, n, " ".join(k for k in C.IDS if res[k][0]) or "-"))
    return n


def main():
    line("rule of thumb 1.0 um per mm of diameter, oven at the heating limit", ratio_answer(1.0))
    best = max((C.grade(ratio_answer(r / 100.0))[0], r / 100.0) for r in range(30, 400))
    line("best single um per mm (%.2f, chosen with the truth), oven at the heating limit" % best[1], ratio_answer(best[1]))
    line("top of the range, steel expansion from the 20-100 C table, no tests", C.solve_route(cte="table", friction="none")[0])
    line("handbook friction 0.15 / 0.10 / 0.08, table expansion, mid-window pick",
         C.solve_route(cte="table", friction="handbook", handbook=HB, pick="mid")[0])
    line("handbook friction, table expansion, maintenance log not applied, mid-window pick",
         C.solve_route(cte="table", friction="handbook", handbook=HB, pick="mid", log=())[0])
    # the best per-joint constant with the truth in hand, for the record of which joints any ratio can pass
    print()
    print("joints that some single um-per-mm ratio (oven at the limit) gets right, with the ratios that do:")
    for k in C.IDS:
        rs = [r / 100.0 for r in range(30, 400) if S.joint_ok(k, int(round(r / 100.0 * S.JOINTS[k]["d"])), S.JOINTS[k]["Tlim"])[0]]
        print("%s %s" % (k, ("%.2f-%.2f" % (rs[0], rs[-1])) if rs else "none"))


if __name__ == "__main__":
    main()
