#!/usr/bin/env python3
"""Whether one answer can be right under two readings of a choice.

For each defective route and each valve, the route's answer is compared with the sealed one. A hedge exists for
that valve only if the route gives the same contingency name and the same finding, and the two area bands
overlap, so that a solver undecided between the two readings could write one number that satisfies both. The gate
is all nine valves, so a hedge on one valve is never enough on its own; the table is here to show that no choice
in the assessment can be dodged.

    python3 hedge_study.py
"""
import sys

import common
import route_study
import solve


def main():
    mod, tru = common.truth()
    d = solve.load(common.DATA)
    tol = mod.TOL
    print("Hedges between a defective reading and the sealed answer. Area tolerance %.3f relative.\n" % tol)
    print("| Route | Valves it changes | Hedge possible on |")
    print("|---|---|---|")
    any_hedge = []
    for name, sw in route_study.ROUTES:
        rows = common.run(d, **sw)
        changed, hedges = [], []
        for vid, case, need, verd in rows:
            t = tru[vid]
            if case == t["case"] and verd == t["verdict"] and abs(need - t["area"]) <= 2.0 * tol * t["area"]:
                if abs((need - t["area"]) / t["area"]) > tol:
                    changed.append(vid)
                    hedges.append(vid)
                continue
            if case != t["case"] or verd != t["verdict"] or abs((need - t["area"]) / t["area"]) > tol:
                changed.append(vid)
        print("| %s | %s | %s |" % (name, ", ".join(changed) or "none",
                                    ", ".join(hedges) or "none"))
        any_hedge += hedges
    print("\nvalves on which any hedge exists at all: %s" %
          (", ".join(sorted(set(any_hedge))) if any_hedge else "none"))
    print("A hedge needs the same contingency name, the same finding, and two area bands that overlap. Where the")
    print("name or the finding differs, no single row can satisfy both readings.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
