"""The evidence for the band and the limit, through the verifier's bench.

    python3 second_run.py > second_run.txt

plain_ropes.py and quick_ropes.py were written apart from the reference. They settle a rope by another
statistic and count the bendings in two other ways: plain_ropes.py movement by movement in plain loops,
quick_ropes.py by sorted running sums. brute_ropes.py is the reference's own method with the bendings counted
by brute force, every movement against every station in numpy arrays.

  1. quick_ropes.py on the six works at the limit: an independent, complete program accepted at full size.
     Its widest departure from the sealed results is what the band is held against.
  2. plain_ropes.py on the six works made again with a fiftieth of the lifts, the limit set aside: the plain
     calculation is correct. Its time for a movement gives what the shipped works would take.
  3. plain_ropes.py on the six works at the limit: a correct program in plain loops is stopped.
  4. brute_ropes.py on the six works, the limit set aside: correct, and how long it takes.
  5. brute_ropes.py on the six works at the limit: a correct, vectorised program that does not avoid the work
     is stopped.
"""
import os
import sys

import common

SHARE = 0.02


def movements(works_dir):
    return {name: sum(1 for _ in open(os.path.join(works_dir, name, "movements.csv"))) - 1 for name in sorted(os.listdir(works_dir))}


def main():
    quick = os.path.join(common.EVIDENCE, "quick_ropes.py")
    plain = os.path.join(common.EVIDENCE, "plain_ropes.py")
    problems = 0

    print("1. quick_ropes.py on the six works, limit %d s\n" % common.LIMIT)
    full = common.judge(quick)
    print(common.rope_bench.account(full))
    wide = common.widest(full)
    slowest = max(note["seconds"] for note in full["trials"])
    print("\nwidest departure from the sealed results %.2f of the band: the band is %.1f times the widest departure of a separately written program"
          % (wide, 1.0 / wide))
    print("slowest run %.1f s against the limit of %d s" % (slowest, common.LIMIT))
    problems += not full["accepted"] or wide > 0.5

    print("\n2. plain_ropes.py on the six works made again with %g of the lifts, the limit set aside\n" % SHARE)
    small = common.made_again(SHARE)
    slow = common.judge(plain, small, limit=common.NO_LIMIT)
    print(common.rope_bench.account(slow))
    count = movements(small[0])
    spent = sum(note["cpu_seconds"] for note in slow["trials"])
    rate = spent / sum(count.values())
    shipped = movements(os.path.join(common.TESTS, "works"))
    low, high = rate * min(shipped.values()), rate * max(shipped.values())
    print("\n%d movements in %.1f s of CPU: %.2g s a movement" % (sum(count.values()), spent, rate))
    print("the shipped works, of %d to %d movements, would take %.0f to %.0f s a run, %.1f to %.1f times the limit"
          % (min(shipped.values()), max(shipped.values()), low, high, low / common.LIMIT, high / common.LIMIT))
    problems += not slow["accepted"] or low < 1.5 * common.LIMIT

    print("\n3. plain_ropes.py on the six works, limit %d s\n" % common.LIMIT)
    stopped = common.judge(plain)
    print(common.rope_bench.account(stopped))
    print("works tried: %d of 6" % len(stopped["trials"]))
    problems += stopped["accepted"] or "nothing after it was tried" not in stopped["halted"] or len(stopped["trials"]) != 1

    brute = os.path.join(common.EVIDENCE, "brute_ropes.py")
    print("\n4. brute_ropes.py on the six works, the limit set aside\n")
    unbounded = common.judge(brute, limit=common.NO_LIMIT)
    print(common.rope_bench.account(unbounded))
    took = [max(note["seconds"], note["cpu_seconds"]) for note in unbounded["trials"]]
    print("\nruns of %.1f to %.1f s, %.1f to %.1f times the limit of %d s" % (min(took), max(took), min(took) / common.LIMIT, max(took) / common.LIMIT, common.LIMIT))
    problems += not unbounded["accepted"] or min(took) < 1.5 * common.LIMIT

    print("\n5. brute_ropes.py on the six works, limit %d s\n" % common.LIMIT)
    cut = common.judge(brute)
    print(common.rope_bench.account(cut))
    print("works tried: %d of 6" % len(cut["trials"]))
    problems += cut["accepted"] or "nothing after it was tried" not in cut["halted"] or len(cut["trials"]) != 1
    if problems:
        print("\nPROBLEM")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
