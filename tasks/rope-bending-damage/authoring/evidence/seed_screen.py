"""The reference on the six works drawn again, twenty times over.

    python3 seed_screen.py > seed_screen.txt

Everything random in a works comes from its seed: the cranes, their logs, which ropes were turned or surveyed
from the dead end and when, how each rope thins, every caliper reading. Here the six works are made again on
seeds 5301 to 5320, with a tenth of the shipped lifts a day so that the screen stays short (a rope's surveys
look the same: the generator scales how a rope thins to the rope's own greatest damage). The table of what
each works holds is the shipped one. The reference must be accepted on every seed, and its widest departure
over the screen is the floor under the band.
"""
import sys

import common

SEEDS = range(5301, 5321)
SHARE = 0.1


def main():
    worst, accepted = 0.0, 0
    for seed in SEEDS:
        verdict = common.judge(common.REFERENCE, common.made_again(SHARE, seed_shift=seed))
        wide = common.widest(verdict) or 99.0
        worst = max(worst, wide)
        accepted += verdict["accepted"]
        print("seed %d: %s, widest departure %.2f of the band%s" % (seed, "accepted" if verdict["accepted"] else "NOT ACCEPTED", wide,
              "" if verdict["accepted"] else " (" + ", ".join(common.ropes_out(verdict)) + ")"))
        sys.stdout.flush()
    print("\n%d seeds, %d accepted; widest departure on any seed %.2f of the band" % (len(SEEDS), accepted, worst))
    if accepted != len(SEEDS):
        print("PROBLEM: the reference is not accepted on every seed")
    return 0 if accepted == len(SEEDS) else 1


if __name__ == "__main__":
    sys.exit(main())
