"""The routes a solver can take that are not sound, what each of them costs, and the design bar: every one of them
has to fail at least one of the twelve values by at least twice the grading tolerance, or name a different governing
requirement, which is categorical. The last column counts the laboratory seeds on which the route gets everything
right.

    python3 authoring/evidence/route_study.py > authoring/evidence/route_study.txt
"""
import common as C

ROUTES = [
    ("the speed taken from the data sheet, not the drive", dict(speed="sheet")),
    ("the rated rod load taken from the nameplate, not the bulletin", dict(rod_load="plate")),
    ("the de-rating of the repaired throw not applied", dict(derate=False)),
    ("the nameplate bore used where the liner is at the repair size", dict(bore="nominal")),
    ("the first liner entry used instead of the latest", dict(bore="earliest")),
    ("the common piston rod used for every throw", dict(rod="common")),
    ("the clearance taken from the data sheet, the open pockets missed", dict(clearance="sheet")),
    ("the open pocket taken over the swept volume of both ends", dict(clearance="both_ends")),
    ("the head end's clearance used for both ends", dict(clearance="one_clearance")),
    ("the design suction temperatures used, the fouling missed", dict(ts="design")),
    ("the bottle-mounted element not corrected to the valve flange", dict(bottle=False)),
    ("the data sheet's gas analysis used", dict(gas="sheet")),
    ("the feed analysis used for every stage", dict(gas="feed")),
    ("the weights taken from the data sheet, the overhaul missed", dict(weight="sheet")),
    ("the shop ticket's piston as fitted read as the difference", dict(weight="as_fitted")),
    ("the valve losses left out of the ratio", dict(valve=False)),
    ("the inertia load left out of the rod load", dict(inertia="none")),
    ("the secondary inertia term left out", dict(inertia="primary")),
    ("the gas load checked against the frame's rated rod load", dict(glim="frame")),
    ("the piston rod area ignored at the crank end", dict(crank_area="norod")),
    ("the isentropic exponent taken at the suction temperature, not iterated", dict(kappa="suction")),
    ("the isentropic exponent taken at the discharge temperature", dict(kappa="discharge")),
    ("the isentropic exponent taken as 1.30", dict(kappa=1.30)),
    ("the range scanned upward to the first acceptable pressure", dict(scan="up")),
    ("the second stage's analysis not drawn, the feed carried forward", dict(plan=("weigh 2B", "weigh 3B"))),
    ("the spare assembly not weighed, the data sheet's weight used", dict(plan=("gc 2", "gc 3"))),
    ("the bypassed separator missed, the feed used for the third stage", dict(plan=("gc 2",), bypass=False)),
    ("pin reversal not checked", dict(reversal=False)),
]


def main():
    print("Defective routes on the shipped seed %d. The bar is two tolerances (%.1f per cent) on a pressure, or a\n"
          "different governing requirement.\n" % (C.SEED, 200.0 * C.S.TOL))
    print("| route | right of 12 | worst value | over the bar | seeds right of 20 |")
    print("|---|---|---|---|---|")
    fails = {k: 0 for k in C.ITEMS}
    under = []
    passes = []
    for name, sw in ROUTES:
        sheet, _ = C.route(**sw)
        n, err, (wc, wv) = C.grade(sheet)
        bad = C.failed_items(err)
        bar = C.over_bar(err)
        seeds = sum(1 for s in C.SEEDS if C.grade(C.route(seed=s, **sw)[0])[0] == len(C.ITEMS))
        for k in bar:
            fails[k] += 1
        if not bad:
            passes.append(name)
            verdict = "passes"
        elif not bar:
            under.append(name)
            verdict = "FAILS UNDER THE BAR"
        else:
            verdict = "yes"
        worst = "%s %+.2f %%" % (wc, 100.0 * wv) if abs(wv) < 90 else "%s no answer" % wc
        print("| %s | %d | %s | %s | %d of %d |" % (name, n, worst, verdict, seeds, len(C.SEEDS)))
    print()
    print("| value | routes that fail it over the bar |")
    print("|---|---|")
    for cid in C.IDS:
        print("| %s pressure | %d |" % (cid, fails[(cid, "pressure")]))
        print("| %s governing requirement | %d |" % (cid, fails[(cid, "limit")]))
    least = min(fails.values())
    print()
    if passes:
        print("These routes pass, and the record says so rather than leaving them out: %s." % "; ".join(passes))
        print("Nothing in the answer turns on them.")
    print("Every value is failed over the bar by at least %d routes." % least)
    if under:
        print("ROUTES THAT FAIL UNDER THE BAR: %s" % "; ".join(under))
    return bool(under) or least < 3


if __name__ == "__main__":
    raise SystemExit(1 if main() else 0)
