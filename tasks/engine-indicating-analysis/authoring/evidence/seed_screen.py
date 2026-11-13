"""The reference on the six cells made again with other draws of everything random.

    python3 seed_screen.py > seed_screen.txt

The generator draws each session's operating points, each cycle's burn, each cycle's level and every sample's
noise from one seed for the cell. Here the six cells are made again on 20 other seeds, and the reference is run
on each set by the verifier's checker. The engines, index errors and gains are the shipped ones. Each point is
given 40 cycles in place of 300, which keeps the screen short and makes it the harder case: with fewer cycles
the mean cycles that settle index and gain are noisier, and so is every mean result. The reference must be
accepted on every seed.
"""
import sys

import common

SEEDS = range(5301, 5321)
CYCLES = 40


def main():
    worst, accepted = 0.0, 0
    for seed in SEEDS:
        cells_dir, results_dir = common.cut_down(CYCLES, seed_shift=seed)
        report = common.assess(common.SOLUTION, cells_dir=cells_dir, results_dir=results_dir)
        wide = common.widest(report)
        worst = max(worst, wide)
        accepted += report["accepted"]
        print("seed %d: %s, widest departure %.2f of a band" % (seed, "accepted" if report["accepted"] else "NOT ACCEPTED", wide))
    print("\n%d seeds, %d accepted; widest departure on any seed %.2f of a band" % (len(SEEDS), accepted, worst))
    if accepted != len(SEEDS):
        print("PROBLEM: the reference is not accepted on every seed")
    return 0 if accepted == len(SEEDS) else 1


if __name__ == "__main__":
    sys.exit(main())
