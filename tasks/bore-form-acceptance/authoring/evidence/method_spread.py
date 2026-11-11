"""Spread of sound methods: every booking that covers what the records cannot carry (either twin of each pair),
in every order the four scans could be ordered in, crossed with the choices a sound method could make about the
mating gauge. Figures: the worst error on a reported form error (um) and the features sentenced wrong.

    python3 method_spread.py > method_spread.txt
"""
import itertools

import common as C

PAIRS = [["CB-22"], ["CB-24", "CB-25"], ["RJ-42", "RJ-43"], ["RJ-45"]]


def main():
    rows = []
    for choice in itertools.product(*PAIRS):
        for order in itertools.permutations(choice):
            for mat in ("cyl", "sec"):
                w, where, wrong, _ = C.grade(C.sentence(plan=list(order), mat=mat))
                rows.append((w, where, len(wrong), order, mat))
    bad = [r for r in rows if r[2]]
    worst = max(rows)
    print("sound methods: %d runs (every covering booking x every order x the mating gauge taken over the feature\n"
          "or section by section)" % len(rows))
    print("worst error on a form error: %.2f um at %s, against the band of %.1f um" % (worst[0], worst[1], C.TOL_FORM))
    print("runs that sentence any feature wrong: %d" % len(bad))
    print("\nthe five widest:")
    for w, where, n, order, mat in sorted(rows, reverse=True)[:5]:
        print("  %.2f um at %-5s wrong %d | scans %s | mating %s" % (w, where, n, ",".join(order), mat))
    print("\nby feature, the largest error any sound run gives it:")
    big = {f: 0.0 for f in C.ORDER}
    for choice in itertools.product(*PAIRS):
        for mat in ("cyl", "sec"):
            _, _, _, det = C.grade(C.sentence(plan=list(choice), mat=mat))
            for f, (de, _v, _ok) in det.items():
                big[f] = max(big[f], abs(de))
    print("  " + "  ".join("%s %.2f" % (f, v) for f, v in big.items()))


if __name__ == "__main__":
    main()
