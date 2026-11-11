"""Every way of spending the booking: all ways to choose 4 of the 14 features to scan, each given the best it can
do with what it leaves behind (carrying a scanned feature's shape to the other feature of its boring setup, or
falling back on the records as they stand). An allocation passes only if every one of the 14 features comes out
right.

    python3 campaign_study.py > campaign_study.txt
"""
import itertools

import common as C


def main():
    allocs = list(itertools.combinations(C.ORDER, C.BUDGET))
    passed, best_fail = [], (99, None)
    for plan in allocs:
        n = 99
        for transfer in (True, False):
            w, _, wrong, _ = C.grade(C.sentence(plan=list(plan), transfer=transfer))
            n = min(n, len(wrong))
        if n == 0:
            passed.append(plan)
        elif n < best_fail[0]:
            best_fail = (n, plan)
    print("ways to spend the booking of %d over %d features: %d" % (C.BUDGET, len(C.ORDER), len(allocs)))
    print("allocations that get all %d features right: %d" % (len(C.ORDER), len(passed)))
    for p in passed:
        print("  %s" % " ".join(p))
    print("the best any other allocation does: %d feature(s) wrong (%s)"
          % (best_fail[0], " ".join(best_fail[1]) if best_fail[1] else "-"))
    print("\nwhat the records cannot carry: %s" % " ".join(C.NEED))
    print("of those, grouped by the boring setup they were finished in:")
    groups = {}
    for f in C.NEED:
        groups.setdefault(C.SETUP_OF.get(f, f), []).append(f)
    for s, fs in groups.items():
        print("  %-4s %s" % (s, " ".join(fs)))
    print("so %d groups for a booking of %d: one scan per group covers them, one scan per feature does not."
          % (len(groups), C.BUDGET))


if __name__ == "__main__":
    main()
