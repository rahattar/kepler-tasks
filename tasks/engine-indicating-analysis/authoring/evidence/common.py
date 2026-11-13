"""What the evidence scripts share: where the bundle's parts are, the verifier's own checker, cut-down cells.

Every study here judges a complete program with tests/check_program.py, as the verifier does: the program is
copied alone into a scratch directory, run on a copy of each cell's package as the user nobody (when the
script is root, as it is in the verifier's image) on one CPU, and its table read and held to the bands by the
checker's own reader. No study compares numbers of its own.
"""
import atexit
import os
import shutil
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
BUNDLE = os.path.dirname(os.path.dirname(HERE))
TESTS = os.path.join(BUNDLE, "tests")
CELLS = os.path.join(TESTS, "cells")
RESULTS = os.path.join(TESTS, "sealed", "results")
VISIBLE = os.path.join(BUNDLE, "environment", "data")
SOLUTION = os.path.join(BUNDLE, "solution", "indicate.py")
sys.path.insert(0, TESTS)
sys.path.insert(0, os.path.join(BUNDLE, "authoring", "provenance"))
import check_program  # noqa: E402
import cells as cellbook  # noqa: E402

LIMIT = check_program.RUN_LIMIT_S
HIDDEN = [c for c in cellbook.CELLS if c["role"] == "hidden"]
EXAMPLES = [c for c in cellbook.CELLS if c["role"] == "example"]
PENDING = [c for c in cellbook.CELLS if c["role"] == "pending"]


def scratch(prefix):
    place = tempfile.mkdtemp(prefix=prefix)
    atexit.register(shutil.rmtree, place, True)
    return place


def program(text, name="indicate.py"):
    """A program file holding `text`, in a directory of its own."""
    path = os.path.join(scratch("program_"), name)
    with open(path, "w") as handle:
        handle.write(text)
    return path


def assess(path, **where):
    return check_program.assess(path, **where)


def examples_as_cells():
    """The two example packages laid out as tests/ lays out the hidden ones: (cells dir, results dir)."""
    root = scratch("examples_")
    cells_dir, results_dir = os.path.join(root, "cells"), os.path.join(root, "results")
    os.makedirs(results_dir)
    for c in EXAMPLES:
        source = os.path.join(VISIBLE, "examples", c["cell"])
        shutil.copytree(source, os.path.join(cells_dir, c["cell"]), ignore=shutil.ignore_patterns("expected.csv"))
        shutil.copy(os.path.join(source, "expected.csv"), os.path.join(results_dir, c["cell"] + ".csv"))
    return cells_dir, results_dir


def cut_down(cycles, which=None, seed_shift=0):
    """The hidden cells made again by the generator with `cycles` cycles at each point in place of 300, with
    their own sealed results: (cells dir, results dir). The engines, their index errors and gains are the
    shipped ones; only the number of cycles (and with it the draw of each cycle) differs."""
    root = scratch("cutdown_")
    for c in HIDDEN:
        if which is None or c["cell"] in which:
            cellbook.build(c, root, cycles=cycles, seed_shift=seed_shift, place="cells", sealed="results")
    return os.path.join(root, "cells"), os.path.join(root, "results")


def widest(report):
    """The widest departure of any quantity at any cell of a report, in bands; None when no table was judged."""
    found = [value for finding in report["cells"].values() for value in finding.get("widest", {}).values()]
    return max(found) if found else None


def line_for(report):
    """One line on what happened at each cell."""
    parts = []
    for name, finding in report["cells"].items():
        if "rows_out" in finding:
            parts.append("%s %d/%d" % (name, finding["rows_out"], finding["rows"]))
        else:
            parts.append("%s: %s" % (name, finding["finding"]))
    return ", ".join(parts)
