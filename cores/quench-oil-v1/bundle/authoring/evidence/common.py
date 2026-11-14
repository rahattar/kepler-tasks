"""What the evidence scripts share: where the bundle is, the checker, and cut-down copies of the sites.

Every script here judges a program with tests/grade_program.py itself, the way the verifier does: the program
is run on the site packages as the user nobody (when the script is root, as it is in the verifier's image),
with one thread to a numerical library, the laboratory answering through tests/lab/labsample.
"""
import atexit
import csv
import os
import shutil
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
BUNDLE = os.path.dirname(os.path.dirname(HERE))
TESTS = os.path.join(BUNDLE, "tests")
SITES = os.path.join(TESTS, "sites")
TRUTHS = os.path.join(TESTS, "sealed", "truth")
BOOKS = os.path.join(TESTS, "lab", "sealed")
VISIBLE = os.path.join(BUNDLE, "environment", "data")
VISIBLE_BOOKS = os.path.join(BUNDLE, "environment", "rig", "sealed")          # the two examples only
PENDING_BOOKS = os.path.join(BUNDLE, "authoring", "provenance", "pending_lab")   # not installed anywhere
REFERENCE = os.path.join(BUNDLE, "solution", "quench.py")
sys.path.insert(0, TESTS)
import grade_program  # noqa: E402

HIDDEN = sorted(os.listdir(SITES))
EXAMPLES = ("north_works", "east_works")
PENDING = "west_quarry"


def _tools():
    """A directory any user can enter holding tests/lab/labsample, as /usr/local/bin does in the verifier's
    image. The bundle itself may sit where the user nobody cannot reach."""
    place = tempfile.mkdtemp(prefix="tools_")
    os.chmod(place, 0o755)
    shutil.copy(os.path.join(TESTS, "lab", "labsample"), os.path.join(place, "labsample"))
    os.chmod(os.path.join(place, "labsample"), 0o755)
    atexit.register(shutil.rmtree, place, True)
    return place


TOOLS = _tools()


def assess(program, **where):
    """grade_program.assess with the laboratory's wrapper on the PATH."""
    where.setdefault("tools", TOOLS)
    return grade_program.assess(program, **where)


def rows_of(path):
    with open(path, newline="") as handle:
        return list(csv.DictReader(handle))


def staged(names, every=1, keep=None):
    """A temporary directory laid out as tests/ is (sites/, truth/) holding the named hidden sites, with every
    `every`-th load kept, or only the loads `keep` accepts. Returns (root, sites dir, truth dir)."""
    root = tempfile.mkdtemp(prefix="staged_")
    os.chmod(root, 0o755)
    sites, truths = os.path.join(root, "sites"), os.path.join(root, "truth")
    os.makedirs(truths)
    for name in names:
        shutil.copytree(os.path.join(SITES, name), os.path.join(sites, name))
        loads = rows_of(os.path.join(SITES, name, "loads.csv"))
        if keep is not None:
            kept = [p for p in loads if keep(p)]
        else:
            kept = loads[::every]
        with open(os.path.join(sites, name, "loads.csv"), "w", newline="") as handle:
            out = csv.DictWriter(handle, list(loads[0]))
            out.writeheader()
            out.writerows(kept)
        wanted = {p["load"] for p in kept}
        truth = rows_of(os.path.join(TRUTHS, name + ".csv"))
        with open(os.path.join(truths, name + ".csv"), "w", newline="") as handle:
            out = csv.DictWriter(handle, list(truth[0]))
            out.writeheader()
            out.writerows(r for r in truth if r["load"] in wanted)
    return root, sites, truths


def visible_as_sites():
    """The two example packages laid out as tests/ is, with expected.csv as their truth, so the checker can run
    a program on them. Returns (root, sites dir, truth dir, books dir)."""
    root = tempfile.mkdtemp(prefix="visible_")
    os.chmod(root, 0o755)
    sites, truths = os.path.join(root, "sites"), os.path.join(root, "truth")
    os.makedirs(truths)
    for name in EXAMPLES:
        source = os.path.join(VISIBLE, "examples", name)
        os.makedirs(os.path.join(sites, name))
        for part in grade_program.PACKAGE:
            shutil.copy(os.path.join(source, part), os.path.join(sites, name, part))
        shutil.copy(os.path.join(source, "expected.csv"), os.path.join(truths, name + ".csv"))
    return root, sites, truths, VISIBLE_BOOKS


def line(name, entry):
    """One site of an Outcome as a line of text."""
    if entry["run"] != "finished":
        return "%-12s %s" % (name, entry["run"])
    if "refused" in entry:
        return "%-12s refused: %s" % (name, entry["refused"])
    worst = max(entry["largest_error_over_band"].values())
    return "%-12s %5.1f s  %4d of %4d loads out of band  largest error %.2f of its band  order: %s" % (
        name, entry["seconds"], entry["loads_out_of_band"], entry["loads"], worst,
        " ".join(entry["laboratory_order"] or ["none"]))
