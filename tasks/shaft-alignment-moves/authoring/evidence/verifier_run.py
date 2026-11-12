#!/usr/bin/env python3
"""The whole verifier, as pytest runs it, on complete sheets.

    python3 verifier_run.py

The other studies call the grading module. This one runs `python -m pytest tests/test_moves.py` in a fresh
process for each sheet, with the sheet where the test looks for it, and reads pytest's exit status: the
reference, the second solution, every sound variation, every defective route and the best of the null sheets.
"""
import os
import shutil
import subprocess
import sys
import tempfile

import common
import independent


def verdict(sheet, box):
    path = os.path.join(box, "moves.csv")
    common.solve.write_sheet(path, sheet)
    done = subprocess.run([sys.executable, "-B", "-m", "pytest", "test_moves.py", "-p", "no:cacheprovider", "-q"],
                          cwd=os.path.join(common.ROOT, "tests"), capture_output=True, text=True,
                          env=dict(os.environ, MOVES_FILE=path, PYTHONDONTWRITEBYTECODE="1"))
    return done.returncode == 0


def main():
    recs = common.records()
    sheets = []
    for name, switches in common.SOUND:
        sheets.append((name, common.run(recs=recs, **switches)[0], True))
    sheets.append(("the second solution, authoring/evidence/independent.py",
                   independent.second_sheet(common.DATA, common.SHIPPED)[0], True))
    for name, switches, plan in common.DEFECTIVE:
        sheets.append((name, common.run(plan=plan, recs=recs, **switches)[0], False))
    trains = common.unit3.build(common.SHIPPED)
    sheets.append(("no move anywhere", {tag: (0.0, 0.0, 0.0, 0.0) for tag in trains}, False))
    first = sorted(trains)[0]
    sheets.append(("one train's sealed moves written for every train",
                   {tag: common.unit3.true_moves(trains[first]) for tag in trains}, False))
    print("`python -m pytest tests/test_moves.py` run in a fresh process on each complete sheet.\n")
    wrong = 0
    box = tempfile.mkdtemp(prefix="sam_vr_")
    try:
        for name, sheet, should_pass in sheets:
            passed = verdict(sheet, box)
            good = passed == should_pass
            wrong += 0 if good else 1
            print("%-10s %-6s %s" % ("ok" if good else "UNEXPECTED", "passes" if passed else "fails", name))
    finally:
        shutil.rmtree(box, ignore_errors=True)
    for stray in ("alignment.json",):
        try:
            os.remove(os.path.join("/logs/verifier", stray))
        except OSError:
            pass
    print("\n%d sheets: %d sound, all pass; %d defective or null, all fail; %d UNEXPECTED"
          % (len(sheets), sum(1 for s in sheets if s[2]), sum(1 for s in sheets if not s[2]), wrong))
    return 1 if wrong else 0


if __name__ == "__main__":
    sys.exit(main())
