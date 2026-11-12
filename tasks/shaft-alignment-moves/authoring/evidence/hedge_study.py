#!/usr/bin/env python3
"""Whether one sheet can be right under two readings at once.

    python3 hedge_study.py

The sheet carries one figure for each move, so the only hedge open to an engineer torn between two readings is
to write the figure midway between them. For every defective route, this builds the sheet midway between the
reference and that route and grades it with the verifier's module. A midway sheet is accepted only where the
route's own miss is under twice the acceptance on every train, that is, where the two readings were close to
begin with.
"""
import sys

import common


def main():
    recs = common.records()
    reference, _ = common.run(recs=recs)
    total = len(reference)
    print("Sheets midway between the reference and each defective route, graded by tests/grade_moves.py.\n")
    print("| route | the route aligned of %d | the midway sheet aligned of %d |" % (total, total))
    print("|---|---|---|")
    accepted = []
    for name, switches, plan in common.DEFECTIVE:
        sheet, _ = common.run(plan=plan, recs=recs, **switches)
        midway = {tag: tuple((a + b) / 2.0 for a, b in zip(reference[tag], sheet[tag])) for tag in reference}
        route, half = common.grade(sheet), common.grade(midway)
        if half.accepted:
            accepted.append(name)
        print("| %s | %d | %d |" % (name, route.aligned, half.aligned))
    print("\nroutes: %d" % len(common.DEFECTIVE))
    print("midway sheets accepted: %d (%s)" % (len(accepted), "; ".join(accepted) or "none"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
