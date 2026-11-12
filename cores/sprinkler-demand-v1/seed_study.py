"""The reference (or any program) on fresh draws of the gauges' scatter: every package of specs.py rebuilt for
each seed in a scratch directory and graded. Usage: python3 seed_study.py PROGRAM SEED [SEED ...] [TAG ...]"""
import os
import shutil
import sys
import tempfile

import gen
import grade
import specs


def main(program, seeds, only=None):
    worst = 0.0
    for seed in seeds:
        root = tempfile.mkdtemp(prefix="sprk-seed-")
        line = "seed %-3d" % seed
        for spec in specs.EXAMPLES + specs.HIDDEN_SPECS:
            if only and spec["tag"] not in only:
                continue
            system, truth, rows, actual, res = gen.make(spec, seed)
            d = os.path.join(root, spec["tag"])
            gen.write(d, system, rows, {})
            r = grade.run(program, d)
            if r["status"] != "done":
                line += " %s %s" % (spec["tag"], r["status"])
                worst = 99.0
                continue
            dp = 100 * (r["result"]["pressure_psi"] / res["pressure_psi"] - 1)
            dq = 100 * (r["result"]["flow_gpm"] / res["flow_gpm"] - 1)
            worst = max(worst, abs(dp), abs(dq))
            line += " %s %+.2f" % (spec["tag"][-4:], dp) + ("!" if max(abs(dp), abs(dq)) > 3 else "")
        print(line, flush=True)
        shutil.rmtree(root, ignore_errors=True)
    print("worst %.2f per cent" % worst)


if __name__ == "__main__":
    main(os.path.abspath(sys.argv[1]), [int(s) for s in sys.argv[2:] if s.isdigit()],
         [s for s in sys.argv[2:] if not s.isdigit()])
