#!/usr/bin/env python3
"""What each of the crew's six tests is worth, and what every way of spending the booking gets.

The booking is isim.BUDGET tests, ordered before any result is known, so the study turns on working out which
of the six can reach a graded value at all. The first table takes each test on its own: the study is worked
with that test in hand and the other five missing, and the rows that then stand are counted. The second takes
every way the booking could be spent and counts the rows that stand.

A test is worth ordering only if the study cannot be made right without it. Four of the six cannot reach any
row, and the file shows that by getting the same count with and without them.

    python3 booking_study.py
"""
import itertools
import sys

import common
import solve

REACHES = {
    "tip-backpressure": "the coefficient of the tip as installed, which enters every pressure",
    "pump-shutoff": "P-401's shutoff head, which decides whether its blocked discharge is credible",
    "reboiler-E406": "E-406's coefficient-area, used only for a cause SIF-4061 sets aside",
    "valve-PV4031": "PV-4031's coefficient, when no device admits a cause it could create",
    "condenser-E404": "E-404's duty, when a loss of cooling is total however capable the condenser",
    "popcheck-PSV404": "PSV-404's set pressure, which the shop record already gives",
}


def worked(sealed, d, ordered):
    """The study as it comes out with exactly these tests ordered."""
    reports = common.crew_reports(sealed, tests=tuple(t for t in ordered if t in common.NEEDED))
    sw = {}
    if "tip-backpressure" not in ordered:
        sw["tip"] = "old"          # the only figure left for the tip is the one the 2019 study gives
    if "pump-shutoff" not in ordered:
        sw["pump"] = "record"      # and the only curve left is the one taken before the renewal
    return common.run(d, reports, **sw)


def main():
    sealed, tru = common.truth()
    d = solve.load(common.DATA)
    budget, total = sealed.BUDGET, len(tru)

    combos = {}
    for combo in itertools.combinations(sealed.TESTS, budget):
        n, notes = common.compare(worked(sealed, d, combo), sealed, tru)
        combos[combo] = (n, common.worst(notes))
    n_none, notes_none = common.compare(worked(sealed, d, ()), sealed, tru)

    print("The crew's six tests against a booking of %d, ordered before any result is known. Tolerance %.3f\n"
          "relative. A test is worth ordering only where no booking without it does as well.\n"
          % (budget, sealed.TOL))
    print("| Test | What it reaches | Best booking with it | Best booking without it | Worth ordering |")
    print("|---|---|---|---|---|")
    needed = []
    for test in sealed.TESTS:
        with_it = max(n for combo, (n, _) in combos.items() if test in combo)
        without = max(n for combo, (n, _) in combos.items() if test not in combo)
        if with_it > without:
            needed.append(test)
        print("| `%s` | %s | %d of %d | %d of %d | %s |"
              % (test, REACHES[test], with_it, total, without, total,
                 "yes" if with_it > without else "no"))

    print("\nEvery way the booking could be spent:\n")
    print("| Tests ordered | Rows right of %d | Worst contingency |" % total)
    print("|---|---|---|")
    for combo in sorted(combos, key=lambda c: (-combos[c][0], c)):
        n, bad = combos[combo]
        print("| %s | %d | %s |" % (", ".join("`%s`" % t for t in combo), n, bad or "-"))
    print("| nothing ordered | %d | %s |" % (n_none, common.worst(notes_none) or "-"))

    winners = [c for c, (n, _) in combos.items() if n == total]
    runner_up = max([n for c, (n, _) in combos.items() if n < total] or [0])
    print("\ntests worth ordering: %s" % ", ".join("`%s`" % t for t in needed))
    print("bookings that get all %d: %s" % (total, "; ".join(", ".join(c) for c in winners) or "none"))
    print("best any other booking does: %d of %d" % (runner_up, total))
    print("nothing ordered: %d of %d" % (n_none, total))
    return 0


if __name__ == "__main__":
    sys.exit(main())
