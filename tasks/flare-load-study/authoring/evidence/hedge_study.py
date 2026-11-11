#!/usr/bin/env python3
"""Whether one answer can be right under two readings of a choice.

For each defective route and each contingency, the route's row is compared with the sealed one. A hedge exists
for that row only if the route names the same devices and both of its numbers lie within twice the tolerance of
the sealed ones, so that a solver undecided between the two readings could write one row that satisfies both.
The gate is all six contingencies, so a hedge on one row is never enough on its own; the table is here to show
that no choice in the study can be dodged.

    python3 hedge_study.py
"""
import sys

import common
import route_study
import solve


def main():
    sealed, tru = common.truth()
    reports = common.crew_reports(sealed)
    d = solve.load(common.DATA)
    tol = sealed.TOL
    print("Hedges between a defective reading and the sealed answer. Tolerance %.3f relative.\n" % tol)
    print("| Route | Contingencies it changes | Hedge possible on |")
    print("|---|---|---|")
    any_hedge = []
    for name, sw in route_study.ROUTES:
        changed, hedges = [], []
        for c, devices, total, back in common.run(d, reports, **sw):
            t = tru[c]
            ok, how = sealed.row_ok(c, devices, total, back)
            if ok:
                continue
            changed.append(c)
            if how["valves"] == 1.0 and abs(how["load"]) <= 2.0 * tol and abs(how["back"]) <= 2.0 * tol:
                hedges.append(c)
        print("| %s | %s | %s |" % (name, ", ".join(changed) or "none", ", ".join(hedges) or "none"))
        any_hedge += hedges
    print("\ncontingencies on which any hedge exists at all: %s" %
          (", ".join(sorted(set(any_hedge))) if any_hedge else "none"))
    print("A hedge needs the same devices named and both numbers within twice the tolerance. Where the device")
    print("set differs, or either number is further out, no single row can satisfy both readings.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
