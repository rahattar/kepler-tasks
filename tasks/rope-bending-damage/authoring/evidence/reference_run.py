"""The reference through the verifier's bench: on the six works, and on the three visible ones.

    python3 reference_run.py > reference_run.txt
"""
import sys

import common


def main():
    print("solution/ropes.py on the six works, limit %d s\n" % common.LIMIT)
    hidden = common.judge(common.REFERENCE)
    print(common.rope_bench.account(hidden))
    slowest = max(max(note["seconds"], note["cpu_seconds"]) for note in hidden["trials"])
    print("\nslowest run %.1f s; the limit of %d s is %.1f times that" % (slowest, common.LIMIT, common.LIMIT / slowest))
    print("\non the visible works (the examples against expected.csv, the pending works against its sealed result)\n")
    visible = common.judge(common.REFERENCE, common.visible_as_works())
    print(common.rope_bench.account(visible))
    good = hidden["accepted"] and visible["accepted"]
    if not good:
        print("\nPROBLEM: the reference is not accepted everywhere")
    return 0 if good else 1


if __name__ == "__main__":
    sys.exit(main())
