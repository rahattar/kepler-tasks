#!/usr/bin/env python3
"""Sound variations: ways of doing the job that differ from the reference and are all correct. Each is carried
through to a complete sheet and graded by the verifier's module, on the shipped records and on the laboratory
seeds 5301 to 5320.

    python3 method_spread.py
"""
import sys

import common


def main():
    recs = {seed: common.records(seed) for seed in [common.SHIPPED] + common.LAB_SEEDS}
    total = len(common.unit3.build(common.SHIPPED))
    tol = common.unit3.TOL
    print("Sound variations, graded by tests/grade_moves.py. The acceptance is %.2f mm.\n" % tol)
    print("| variation | laser programme | aligned of %d | worst left, mm | seeds of %d with every train | worst left on any seed, mm |"
          % (total, len(common.LAB_SEEDS)))
    print("|---|---|---|---|---|---|")
    missing, worst_all = [], 0.0
    for name, switches in common.SOUND:
        sheet, programme = common.run(common.SHIPPED, recs=recs[common.SHIPPED], **switches)
        outcome = common.grade(sheet)
        worst = max(abs(row["worst_mm"]) for row in outcome.detail.values())
        clean, far = 0, worst
        for seed in common.LAB_SEEDS:
            other, _ = common.run(seed, recs=recs[seed], **switches)
            graded = common.grade(other, seed)
            clean += graded.accepted
            far = max(far, max(abs(row["worst_mm"]) for row in graded.detail.values()))
        if not outcome.accepted or clean != len(common.LAB_SEEDS):
            missing.append(name)
        worst_all = max(worst_all, far)
        print("| %s | %s | %d | %.4f | %d | %.4f |" % (name, " ".join(programme), outcome.aligned, worst, clean, far))
    print("\nReadings AP-12 does not sanction, whose effect the acceptance absorbs on the shipped records:\n")
    print("| reading | aligned of %d | worst left, mm | seeds of %d with every train | worst left on any seed, mm |"
          % (total, len(common.LAB_SEEDS)))
    print("|---|---|---|---|---|")
    for name, switches in common.ABSORBED:
        sheet, _ = common.run(common.SHIPPED, recs=recs[common.SHIPPED], **switches)
        outcome = common.grade(sheet)
        worst = max(abs(row["worst_mm"]) for row in outcome.detail.values())
        clean, far = 0, worst
        for seed in common.LAB_SEEDS:
            other, _ = common.run(seed, recs=recs[seed], **switches)
            graded = common.grade(other, seed)
            clean += graded.accepted
            far = max(far, max(abs(row["worst_mm"]) for row in graded.detail.values()))
        print("| %s | %d | %.4f | %d | %.4f |" % (name, outcome.aligned, worst, clean, far))
    print("\nvariations: %d" % len(common.SOUND))
    print("variations that miss a train: %s" % (", ".join(missing) or "none"))
    print("worst left by any sound variation on any seed: %.4f mm against %.2f" % (worst_all, tol))
    return 0


if __name__ == "__main__":
    sys.exit(main())
