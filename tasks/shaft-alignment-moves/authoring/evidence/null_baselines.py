#!/usr/bin/env python3
"""Sheets made without doing the job, graded by the verifier's module.

    python3 null_baselines.py

A train is judged on its own four moves, so a sheet made with no work could still leave a train aligned by
luck. This lists how many each such sheet gets. The constant sheets are swept across the whole range the
sealed moves cover, in steps of a tenth of the acceptance, and the best of each sweep is reported.
"""
import sys

import common


def main():
    trains = common.unit3.build(common.SHIPPED)
    tags = sorted(trains)
    sealed = {tag: common.unit3.true_moves(trains[tag]) for tag in tags}
    tol = common.unit3.TOL
    low = min(min(v) for v in sealed.values())
    high = max(max(v) for v in sealed.values())
    print("Null sheets on the shipped records, graded by tests/grade_moves.py. The sealed moves run from "
          "%.3f to %.3f mm.\n" % (low, high))
    print("| null sheet | sheets tried | most trains aligned of %d |" % len(tags))
    print("|---|---|---|")
    best_overall = 0

    def report(name, sheets):
        nonlocal best_overall
        best = max(common.grade(sheet).aligned for sheet in sheets)
        best_overall = max(best_overall, best)
        print("| %s | %d | %d |" % (name, len(sheets), best))

    step = tol / 10.0
    grid = [round(low - tol + i * step, 4) for i in range(int((high - low + 2 * tol) / step) + 1)]
    report("no move anywhere", [{tag: (0.0, 0.0, 0.0, 0.0) for tag in tags}])
    report("one figure for all four moves of every train, swept", [{tag: (c, c, c, c) for tag in tags} for c in grid])
    report("one shim figure for every train and no lateral move, swept", [{tag: (c, c, 0.0, 0.0) for tag in tags} for c in grid])
    report("one lateral figure for every train and no shim, swept", [{tag: (0.0, 0.0, c, c) for tag in tags} for c in grid])
    report("one train's sealed moves written for every train, each train in turn",
           [{tag: sealed[source] for tag in tags} for source in tags])
    recs = common.records()
    plain, _ = common.run(plan=[], recs=recs, sag="none", thermal="none", unmeasured="rescale", turbine="hot_check")
    constants = best_overall
    report("the dial sheets alone: no sag, no running position, no visit", [plain])
    surveyed, _ = common.run(plan=[], recs=recs, pumps="survey", unmeasured="rescale", turbine="hot_check")
    report("the unit as the 2019 survey and the 2023 hot checks describe it, no visit", [surveyed])
    print("\nmost trains a sheet of constants aligns: %d" % constants)
    print("most trains any null sheet aligns: %d" % best_overall)
    return 0


if __name__ == "__main__":
    sys.exit(main())
