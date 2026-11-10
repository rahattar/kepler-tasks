"""Can a sheet be right whichever way a choice goes? For a value graded inside a relative band, one number is right
under both answers to a choice exactly when the two answers lie within two tolerances of each other; for the
governing requirement, which is graded as a name, one entry is right under both only when both answers name the same
requirement. This file takes every choice that decides the result and reports the value that closes it.

    python3 authoring/evidence/hedge_study.py > authoring/evidence/hedge_study.txt
"""
import common as C

S = C.S

CHOICES = [
    ("the speed: the drive's or the data sheet's", {}, dict(speed="sheet")),
    ("the rated rod load: the bulletin's or the nameplate's", {}, dict(rod_load="plate")),
    ("the de-rating of the repaired throw: applied or not", {}, dict(derate=False)),
    ("the bore of the re-bored liner: as bored or nominal", {}, dict(bore="nominal")),
    ("the piston rods: each throw's own or one for all", {}, dict(rod="common")),
    ("the clearance: the open pockets or the data sheet", {}, dict(clearance="sheet")),
    ("the open pocket: over the head end's swept volume or both", {}, dict(clearance="both_ends")),
    ("the suction temperatures: the readings or the design values", {}, dict(ts="design")),
    ("the bottle-mounted element: corrected or not", {}, dict(bottle=False)),
    ("the gas: each stage's analysis or the data sheet's", {}, dict(gas="sheet")),
    ("the gas: each stage's analysis or the feed for all", {}, dict(gas="feed")),
    ("the weights: the records' or the data sheet's", {}, dict(weight="sheet")),
    ("the valve losses: applied or not", {}, dict(valve=False)),
    ("the inertia load: counted or not", {}, dict(inertia="none")),
    ("the secondary inertia term: counted or not", {}, dict(inertia="primary")),
    ("the gas load's limit: the cylinder's or the frame's", {}, dict(glim="frame")),
    ("the crank end area: less the rod or not", {}, dict(crank_area="norod")),
    ("the isentropic exponent: at the mean temperature or at suction", {}, dict(kappa="suction")),
    ("the range: the standard's rule or the first acceptable pressure", {}, dict(scan="up")),
    ("the allowance: on the analysis and the weighing, or on both analyses", {}, dict(plan=("gc 2", "gc 3"))),
    ("pin reversal: checked or not", {}, dict(reversal=False)),
]


def main():
    print("Hedging, choice by choice. A value can be hedged when one entry is inside the band under both answers:\n"
          "for a pressure, when the two answers are within two tolerances (%.1f per cent) of each other; for a\n"
          "requirement, when both answers name the same one.\n" % (200.0 * S.TOL))
    print("| choice | the value that closes it | apart by | hedgeable |")
    print("|---|---|---|---|")
    open_ = []
    for name, a, b in CHOICES:
        sa, _ = C.route(**a)
        sb, _ = C.route(**b)
        best = None
        for cid in C.IDS:
            pa, qa = sa[cid]
            pb, qb = sb[cid]
            if qa != qb:
                best = ("%s governing requirement" % cid, "%s against %s" % (qa, qb), False)
                break
            if pa is None or pb is None:
                best = ("%s pressure" % cid, "no answer under one of them", False)
                break
            apart = abs(pa - pb) / min(pa, pb)
            if best is None or apart > best[2]:
                best = ("%s pressure" % cid, "%.2f per cent" % (100.0 * apart), apart)
        if best[2] is False:
            print("| %s | %s | %s | no |" % (name, best[0], best[1]))
            continue
        hedge = best[2] < 2.0 * S.TOL
        if hedge:
            open_.append(name)
        print("| %s | %s | %s | %s |" % (name, best[0], best[1], "YES" if hedge else "no"))
    print()
    if open_:
        print("Choices a whole sheet can hedge: %s." % "; ".join(open_))
        print("Nothing in the answer turns on them, which is why they can be.")
    print("Every other choice moves a value past the band under one answer or the other, so no single sheet is\n"
          "right whichever way it goes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
