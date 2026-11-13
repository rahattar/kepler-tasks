"""The second solution, slow_indicate.py: right, and far too slow.

    python3 slow_run.py > slow_run.txt

slow_indicate.py was written apart from the reference and shares no code with it or with the sealed
definition. It works through the cycles one at a time in plain loops, and finds the index error and the gain
by simulating the compression stroke with an ODE solver and fitting it to the records in pressure.

1. Is it right? It is run on the six cells made again by the generator with 75 cycles at each point in place
   of 300 (the engines, index errors and gains are the shipped ones), with the limit set aside.
2. How slow is it? From the time of those runs, the time the shipped cells would take.
3. At the limit, on the shipped cells, through the checker as the verifier runs it.
"""
import sys
import time

import common

CUT = 75


def main():
    slow = common.SOLUTION.replace("solution/indicate.py", "authoring/evidence/slow_indicate.py")
    cells_dir, results_dir = common.cut_down(CUT)
    began = time.time()
    report = common.assess(slow, cells_dir=cells_dir, results_dir=results_dir, limit=3600)
    took = time.time() - began
    cycles = sum(c["cyl"] * c["points"] * CUT for c in common.HIDDEN)
    print("1. on the six cells with %d cycles a point, the limit set aside\n" % CUT)
    print(common.check_program.account(report))
    wide = common.widest(report)
    print("\nwidest departure from the sealed results: %.2f of a band, so every band is at least %.1f times the widest"
          " departure of a separately written, correct program" % (wide, 1 / wide))
    rate = took / cycles
    print("\n2. %d cycles in %.0f s: %.4f s a cycle" % (cycles, took, rate))
    full = [c["cyl"] * c["points"] * common.cellbook.CYCLES["hidden"] for c in common.HIDDEN]
    print("the shipped cells, of %d to %d cycles, would take %.0f to %.0f s a run, %.0f to %.0f times the limit of %d s" % (
        min(full), max(full), rate * min(full), rate * max(full), rate * min(full) / common.LIMIT,
        rate * max(full) / common.LIMIT, common.LIMIT))
    print("\n3. on the shipped cells at the limit\n")
    at_limit = common.assess(slow)
    print(common.check_program.account(at_limit))
    print("cells run: %d of %d" % (len(at_limit["cells"]), len(common.HIDDEN)))
    return 0 if report["accepted"] and not at_limit["accepted"] and at_limit["stopped"] else 1


if __name__ == "__main__":
    sys.exit(main())
