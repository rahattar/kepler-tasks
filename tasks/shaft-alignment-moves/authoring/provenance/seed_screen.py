#!/usr/bin/env python3
"""Seeds screened on what the task needs of one.

    python3 seed_screen.py

The seed drives the trains' dimensions, their as-found positions and the scatter of the records; the physics is
fixed in the sealed definition. A seed is acceptable when, on the records it makes: the reference's programme
is the six measurements and the reference leaves every train aligned; every sound variation does too; every
defective route misses a train; and no sound variation leaves any train beyond half the acceptance. Every
sheet is graded by the verifier's module.
"""
import os
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "evidence"))
import common  # noqa: E402


def main():
    seeds = [common.SHIPPED] + common.LAB_SEEDS
    tol = common.unit3.TOL
    print("| seed | reference aligned | sound variations with every train | defective routes with every train | "
          "worst left by a sound variation, mm | acceptable |")
    print("|---|---|---|---|---|---|")
    good = 0
    for seed in seeds:
        recs = common.records(seed)
        ref_sheet, programme = common.run(seed, recs=recs)
        ref = common.grade(ref_sheet, seed)
        sound, far = 0, 0.0
        for _, switches in common.SOUND:
            outcome = common.grade(common.run(seed, recs=recs, **switches)[0], seed)
            sound += outcome.accepted
            far = max(far, max(abs(row["worst_mm"]) for row in outcome.detail.values()))
        slipped = sum(common.grade(common.run(seed, plan=plan, recs=recs, **switches)[0], seed).accepted
                      for _, switches, plan in common.DEFECTIVE)
        ok = (ref.accepted and len(programme) == common.unit3.BUDGET and sound == len(common.SOUND)
              and slipped == 0 and far <= tol / 2)
        good += ok
        print("| %d%s | %d of %d | %d of %d | %d of %d | %.4f | %s |"
              % (seed, " (shipped)" if seed == common.SHIPPED else "", ref.aligned, ref.trains, sound,
                 len(common.SOUND), slipped, len(common.DEFECTIVE), far, "yes" if ok else "no"))
    print("\nacceptable seeds: %d of %d, the shipped one among them: %s"
          % (good, len(seeds), "yes" if good and seeds[0] == common.SHIPPED else "no"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
