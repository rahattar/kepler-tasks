"""Answers made without doing the work. Each of the twelve values is graded on its own, so an answer like these can
be right on a value here and there; the file lists every such free pass. The gate is all twelve, so none of them is
accepted.

    python3 authoring/evidence/null_baselines.py > authoring/evidence/null_baselines.txt
"""
import common as C

S = C.S


def flat(p, q):
    return {cid: (p, q) for cid in C.IDS}


def main():
    truth = S.truth()
    cases = [("the machine as the data sheet describes it, no readings drawn",
              C.route(plan=(), bypass=False, speed="sheet", rod_load="plate", derate=False, bore="nominal",
                      clearance="sheet", ts="design", bottle=False, gas="sheet", weight="sheet")[0]),
             ("the pressure each stage runs at today, as the limit",
              {cid: (S.PS_NOW[S.CYL[cid]["stage"]], "rod_load_compression") for cid in C.IDS}),
             ("the bottom of the standard's range, with the temperature as the limit",
              {cid: (S.band(cid)[1], "discharge_temperature") for cid in C.IDS}),
             ("half the discharge pressure, with the rod load as the limit",
              {cid: (round(S.CYL[cid]["pd"] / 2.0, 2), "rod_load_compression") for cid in C.IDS}),
             ("a flat 50 bar and the commonest requirement everywhere", flat(50.0, "rod_load_compression")),
             ("the right pressures with one requirement named for all six",
              {cid: (truth[cid][0], "rod_load_compression") for cid in C.IDS}),
             ("the right requirements with the data sheet's machine behind the pressures",
              {cid: (C.route(plan=(), bypass=False, speed="sheet", rod_load="plate", derate=False, bore="nominal",
                            clearance="sheet", ts="design", bottle=False, gas="sheet",
                            weight="sheet")[0][cid][0], truth[cid][1]) for cid in C.IDS}),
             ("the requirement guessed as the one with the least margin at today's pressure",
              {cid: (truth[cid][0], min(S.margins(cid, S.PS_NOW[S.CYL[cid]["stage"]]),
                                        key=S.margins(cid, S.PS_NOW[S.CYL[cid]["stage"]]).get))
               for cid in C.IDS})]
    print("Null answers, graded value by value. The gate is all %d.\n" % len(C.ITEMS))
    print("| answer | right of 12 | which |")
    print("|---|---|---|")
    worst = 0
    for name, sheet in cases:
        n, err, _ = C.grade(sheet)
        got = [k for k in C.ITEMS if k not in C.failed_items(err)]
        worst = max(worst, n)
        print("| %s | %d | %s |" % (name, n, ", ".join("%s %s" % k for k in got) or "none"))
    print()
    print("The best of them gets %d of %d, and the gate is %d: none is accepted." % (worst, len(C.ITEMS),
                                                                                    len(C.ITEMS)))
    return worst >= len(C.ITEMS)


if __name__ == "__main__":
    raise SystemExit(1 if main() else 0)
