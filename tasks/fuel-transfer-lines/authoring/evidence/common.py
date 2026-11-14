"""What every study here uses: the parts of the bundle, three sets of sites, and the checker run on a set.

    six      tests/sites: the six sites a delivered program is run on, with tests/results and tests/crew/books
    beside   the three packages a program is written beside: the two examples (their expected.csv is the
             result, the crew's book is in environment/rig/sealed) and the pending site (its sealed result and
             the crew's book for it are in authoring/provenance/as_it_stands)
    small    authoring/evidence/small: the nine names again at a fifth of the size, from the same generator

`run` hands a complete program to tests/rerun.judge, the function the verifier's one test calls, so a study
sees a program exactly as the verifier does: started as nobody when the study is root, timed on the clock and
in CPU, with the verifier's own `heatsurvey` on the PATH and the crew answering from the set's books.
"""
import atexit
import os
import shutil
import sys
import tempfile

sys.dont_write_bytecode = True
EVIDENCE = os.path.dirname(os.path.abspath(__file__))
BUNDLE = os.path.dirname(os.path.dirname(EVIDENCE))
TESTS = os.path.join(BUNDLE, "tests")
DATA = os.path.join(BUNDLE, "environment", "data")
FACTS = os.path.join(BUNDLE, "authoring", "provenance", "as_it_stands")
SMALL = os.path.join(EVIDENCE, "small")
REFERENCE = os.path.join(BUNDLE, "solution", "lines.py")
SECOND = os.path.join(EVIDENCE, "second_lines.py")
PLAIN = os.path.join(EVIDENCE, "plain_lines.py")
sys.path.insert(0, TESTS)
import rerun  # noqa: E402

LIMIT = rerun.LIMIT_S
_rooms = []
atexit.register(lambda: [shutil.rmtree(room, ignore_errors=True) for room in _rooms])


def room():
    """A scratch directory any user can enter, removed when the study ends."""
    path = tempfile.mkdtemp(prefix="study_")
    os.chmod(path, 0o755)
    _rooms.append(path)
    return path


def site_set(which):
    """(sites, results, books) of a set."""
    if which == "six":
        return os.path.join(TESTS, "sites"), os.path.join(TESTS, "results"), os.path.join(TESTS, "crew", "books")
    if which == "small":
        return tuple(os.path.join(SMALL, part) for part in ("sites", "results", "books"))
    if which != "beside":
        raise ValueError(which)
    base = room()
    sites, results, books = (os.path.join(base, part) for part in ("sites", "results", "books"))
    for part in (sites, results, books):
        os.mkdir(part)
    for name in sorted(os.listdir(os.path.join(DATA, "examples"))):
        package = os.path.join(DATA, "examples", name)
        shutil.copytree(package, os.path.join(sites, name), ignore=shutil.ignore_patterns("expected.csv"))
        shutil.copy(os.path.join(package, "expected.csv"), os.path.join(results, name + ".csv"))
        shutil.copy(os.path.join(BUNDLE, "environment", "rig", "sealed", name + ".json"), books)
    for name in sorted(os.listdir(os.path.join(DATA, "pending"))):
        shutil.copytree(os.path.join(DATA, "pending", name), os.path.join(sites, name))
        shutil.copy(os.path.join(FACTS, name + "_result.csv"), os.path.join(results, name + ".csv"))
        shutil.copy(os.path.join(FACTS, name + "_book.json"), os.path.join(books, name + ".json"))
    return sites, results, books


def run(program, which="six", limit=None, only=None):
    """rerun.judge's verdict for a program on a set (only: a list of site names of that set)."""
    sites, results, books = site_set(which)
    if only:
        chosen = room()
        for name in only:
            shutil.copytree(os.path.join(sites, name), os.path.join(chosen, name))
        sites = chosen
    tools = room()                                           # the verifier's heatsurvey, where any user can run it
    shutil.copy(os.path.join(TESTS, "crew", "heatsurvey"), os.path.join(tools, "heatsurvey"))
    os.chmod(os.path.join(tools, "heatsurvey"), 0o755)
    return rerun.judge(program, sites=sites, results=results, books=books, limit=LIMIT if limit is None else limit,
                       desk=os.path.join(room(), "desk"), path_first=tools)


def written(text, name="program.py"):
    """A program given as text, as a file a study can hand to `run`."""
    path = os.path.join(room(), name)
    with open(path, "w") as handle:
        handle.write(text)
    return path


def cpu_range(verdict):
    """(least, most) CPU seconds over the runs of a verdict."""
    used = [note["cpu_seconds"] for note in verdict["sites"].values()]
    return min(used), max(used)


def largest_error(verdict):
    return max(note.get("largest_error_over_band", float("inf")) for note in verdict["sites"].values())


class Sheet:
    """Lines printed and kept, then written to the study's .txt beside it."""

    def __init__(self, study_file):
        self.path = os.path.splitext(os.path.abspath(study_file))[0] + ".txt"
        self.lines = []

    def say(self, text=""):
        print(text, flush=True)
        self.lines.append(text)

    def account(self, title, verdict):
        self.say(title)
        for line in rerun.account(verdict).splitlines():
            self.say("  " + line)

    def close(self):
        with open(self.path, "w") as handle:
            handle.write("\n".join(self.lines) + "\n")
