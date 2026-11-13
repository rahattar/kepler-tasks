"""The reference, solution/indicate.py, run by the verifier's checker on the six cells, as the verifier runs it.

    python3 reference_run.py > reference_run.txt

Also on the two example packages against their expected.csv, and on the two pending packages for what it
finds there.
"""
import os
import subprocess
import sys
import tempfile

import common


def main():
    print("solution/indicate.py through tests/check_program.py, limit %d s a run\n" % common.LIMIT)
    report = common.assess(common.SOLUTION)
    print(common.check_program.account(report))
    seconds = [finding["seconds"] for finding in report["cells"].values()]
    rows = sum(finding.get("rows", 0) for finding in report["cells"].values())
    print("\nrows in all: %d" % rows)
    print("widest departure at any row of any cell: %.2f of its band" % common.widest(report))
    print("runs take %.1f to %.1f s; the limit of %d s is %.1f times the slowest" % (
        min(seconds), max(seconds), common.LIMIT, common.LIMIT / max(seconds)))

    print("\nthe two example packages, against their expected.csv")
    cells_dir, results_dir = common.examples_as_cells()
    examples = common.assess(common.SOLUTION, cells_dir=cells_dir, results_dir=results_dir)
    print(common.check_program.account(examples))

    print("\nwhat it finds in the packages (written by the program to stderr)")
    for group, book in (("examples", common.EXAMPLES), ("pending", common.PENDING)):
        for c in book:
            package = os.path.join(common.VISIBLE, group, c["cell"])
            with tempfile.TemporaryDirectory() as box:
                ran = subprocess.run([sys.executable, "-B", common.SOLUTION, package, os.path.join(box, "out.csv")],
                                     capture_output=True, text=True)
            print("%s %s: %s" % (group, c["cell"], ran.stderr.strip()))
    return 0 if report["accepted"] and examples["accepted"] else 1


if __name__ == "__main__":
    sys.exit(main())
