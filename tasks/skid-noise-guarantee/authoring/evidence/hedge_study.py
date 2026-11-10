"""Hedging. A solver who cannot settle a choice has one number to submit for each value, so the question is whether
one number can be right whichever answer to the choice is the true one. For a value graded inside a band of +/- TOL
that happens exactly when the two answers lie within 2 TOL of each other: the midpoint is then inside the band of
both. The design bar of 2 TOL on every route is what closes it.

The table gives, for each choice: the values the choice moves at all, the values where the wrong answer is still
inside the band on its own, and the values where the midpoint of the two answers is inside the band. The gate is all
27 values, so a sheet can only be hedged if every value it moves can be.

    python3 authoring/evidence/hedge_study.py > authoring/evidence/hedge_study.txt
"""
import common as C
import route_study as R

S = C.S
TOTAL = len(C.IDS) * len(C.KEYS)


def main():
    ref, _ = C.solve_route(seed=C.SEED)
    truth = S.truth()
    print("the reference's own worst error on the shipped seed is %+.2f dB, inside the band of +/- %.1f dB" % (
        max((ref[m][k] - truth[m][k] for m in C.IDS for k in C.KEYS), key=abs), S.TOL))
    print()
    print("choice | values moved | wrong answer still inside | midpoint inside | whole sheet hedged")
    hedgeable = []
    for name, kw in R.ROUTES:
        bad, _ = C.solve_route(seed=C.SEED, **kw)
        moved = [(m, k) for m in C.IDS for k in C.KEYS if abs(bad[m][k] - ref[m][k]) > 1e-9]
        inside = [x for x in moved if abs(bad[x[0]][x[1]] - truth[x[0]][x[1]]) <= S.TOL]
        mid = [x for x in moved
               if abs(0.5 * (bad[x[0]][x[1]] + ref[x[0]][x[1]]) - truth[x[0]][x[1]]) <= S.TOL]
        whole = len(mid) == len(moved) and len(moved) > 0
        idle = len(inside) == len(moved)        # the wrong answer is inside the band on its own: the choice is idle
        if whole and not idle:
            hedgeable.append(name)
        print("%-66s | %2d | %2d | %2d | %s" % (name, len(moved), len(inside), len(mid),
                                                "idle" if idle else ("YES" if whole else "no")))
    print()
    if hedgeable:
        print("choices a whole sheet can hedge: %s" % ", ".join(hedgeable))
    else:
        print("No choice that decides the result can be hedged across a whole sheet. Every such choice moves at "
              "least one value by more than 2 x %.1f dB, and there no single number is inside the band under both "
              "answers. The choices marked idle are those whose wrong answer is inside the band on every value it "
              "moves, so nothing turns on them: route_study.txt shows them passing." % S.TOL)


if __name__ == "__main__":
    main()
