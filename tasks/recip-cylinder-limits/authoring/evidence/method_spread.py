"""The spread of methods that are sound: each gets all twelve values right, on the shipped seed and on the twenty
laboratory seeds, and the file reports how far the worst of them lands from the sealed definition. That spread is
what the grading tolerance has to clear.

    python3 authoring/evidence/method_spread.py > authoring/evidence/method_spread.txt
"""
import common as C

VARIATIONS = [
    ("the reference", {}),
    ("the readings booked in the other order", dict(plan=("weigh 3B", "gc 2"))),
    ("the third stage's sample stream drawn instead of the second's", dict(plan=("gc 3", "weigh 3B"))),
    ("the crank swept every half degree", dict(nth=720)),
    ("the crank swept every two degrees", dict(nth=180)),
    ("the field pressure scanned in steps of 0.001 bar", dict(step=0.001)),
    ("the margins written as a difference, not a ratio", dict(margin="difference")),
    ("the bore taken at the largest of the liner record", dict(bore="largest")),
    ("the bore taken at the smallest of the liner record", dict(bore="smallest")),
    ("the third stage's temperature taken from the last month of the trend", dict(ts="trend")),
    ("the clearance pockets read from the maintenance log rather than the register", dict(clearance="log")),
    ("the discharge temperature iterated to a thousandth of its tolerance", dict(td_tol=1e-6)),
    ("the interstage balance taken through twice as many passes", dict(sweeps=32)),
    ("the range taken at the standard's floor as well, which the speed reaches first", dict(range_="floor")),
]


def main():
    print("Sound variations, on the shipped seed %d. All twelve values right is the gate.\n" % C.SEED)
    print("| variation | right of 12 | worst value | seeds right of 20 |")
    print("|---|---|---|---|")
    worst_all = 0.0
    bad = 0
    for name, sw in VARIATIONS:
        sheet, _ = C.route(**sw)
        n, err, (wc, wv) = C.grade(sheet)
        seeds = 0
        for s in C.SEEDS:
            sh, _ = C.route(seed=s, **sw)
            if C.grade(sh)[0] == len(C.ITEMS):
                seeds += 1
        worst_all = max(worst_all, abs(wv))
        bad += n < len(C.ITEMS) or seeds < len(C.SEEDS)
        print("| %s | %d | %s %+.3f %% | %d of %d |" % (name, n, wc, 100.0 * wv, seeds, len(C.SEEDS)))
    print()
    print("The worst value of any sound variation is %.3f per cent from the definition, against a tolerance of "
          "%.1f per cent: %.0f per cent of the band." % (
              100.0 * worst_all, 100.0 * C.S.TOL, 100.0 * worst_all / C.S.TOL))
    print("%s" % ("every variation gets all twelve, on the shipped seed and on all twenty"
                  if not bad else "SOME VARIATION FAILS"))
    return bad


if __name__ == "__main__":
    raise SystemExit(1 if main() else 0)
