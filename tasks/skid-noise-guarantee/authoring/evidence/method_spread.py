"""Correct methods: variations of a sound method, graded on the shipped seed and on the laboratory seeds 7101-7120.

    python3 authoring/evidence/method_spread.py > authoring/evidence/method_spread.txt
"""
import common as C

METHODS = [
    ("reference (solution/solve.py)", {}),
    ("the three differences measured in another order", dict(deltas=("C7", "C3", "C1"))),
    ("the differences at other positions of their arrays",
     dict(delta_pos={"C1": "P5", "C3": "P23", "C7": "P63"})),
    ("the louvred-wall positions kept and corrected by subtraction", dict(drop="radius")),
    ("one more position dropped from each array",
     dict(drop_extra=("P8", "P18", "P27", "P39", "P49", "P58", "P67", "P79"))),
    ("the mean background of the valid positions subtracted", dict(background="average")),
    ("the background left out where the standard's margin is met", dict(background="none")),
    ("the room check against the background of P40 instead of P1", dict(rss_bg="P40")),
    ("the room check against the mean background of the quiet positions", dict(rss_bg="mean")),
]


def main():
    print("method | right of %d (seed %d) | worst error dB | seeds 7101-7120 all right" % (len(C.IDS) * len(C.KEYS), C.SEED))
    for name, kw in METHODS:
        sheet, _ = C.solve_route(seed=C.SEED, **kw)
        n, err, (wm, wk, wv) = C.grade(sheet)
        allseeds = sum(C.grade(C.solve_route(seed=s, **kw)[0])[0] == len(C.IDS) * len(C.KEYS) for s in C.SEEDS)
        print("%-58s | %2d | %s %-3s %+5.2f | %2d of 20" % (name, n, wm, wk, wv, allseeds))


if __name__ == "__main__":
    main()
