#!/usr/bin/env python3
"""Defective routes: each is one thing an engineer might get wrong, carried through to a complete sheet and
graded by the verifier's module.

    python3 route_study.py

For every route: the trains it leaves aligned on the shipped records, the train it misses worst, and the
number of laboratory seeds (5301 to 5320) on which it nevertheless gets every train. Then, for every train,
the number of routes that miss it.
"""
import sys

import common


def main():
    recs = {seed: common.records(seed) for seed in [common.SHIPPED] + common.LAB_SEEDS}
    total = len(common.unit3.build(common.SHIPPED))
    print("Defective routes on the shipped records (seed %d), graded by tests/grade_moves.py.\n" % common.SHIPPED)
    print("| route | laser programme | aligned of %d | worst miss | seeds of %d with every train |"
          % (total, len(common.LAB_SEEDS)))
    print("|---|---|---|---|---|")
    passing, misses = [], {}
    for name, switches, plan in common.DEFECTIVE:
        sheet, programme = common.run(common.SHIPPED, plan=plan, recs=recs[common.SHIPPED], **switches)
        outcome = common.grade(sheet)
        if outcome.accepted:
            passing.append(name)
        for tag in common.missed(outcome):
            misses[tag] = misses.get(tag, 0) + 1
        worst = max(outcome.detail.items(), key=lambda item: abs(item[1]["worst_mm"]))
        clean = 0
        for seed in common.LAB_SEEDS:
            other, _ = common.run(seed, plan=plan, recs=recs[seed], **switches)
            clean += common.grade(other, seed).accepted
        print("| %s | %s | %d | %s %+.3f mm | %d |" % (name, " ".join(programme) or "none", outcome.aligned,
                                                      worst[0], worst[1]["worst_mm"], clean))
    print("\nroutes: %d" % len(common.DEFECTIVE))
    print("routes that pass on the shipped records: %s" % (", ".join(passing) or "none"))
    tags = sorted(common.unit3.build(common.SHIPPED))
    few = [tag for tag in tags if misses.get(tag, 0) < 3]
    print("trains missed by fewer than 3 routes: %s" % (", ".join(few) or "none"))
    print("\nRoutes that miss each train:\n")
    print("| train | routes |")
    print("|---|---|")
    for tag in tags:
        print("| %s | %d |" % (tag, misses.get(tag, 0)))
    print("\nfewest routes missing any one train: %d (%s)"
          % (min(misses.get(tag, 0) for tag in tags), min(tags, key=lambda tag: misses.get(tag, 0))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
