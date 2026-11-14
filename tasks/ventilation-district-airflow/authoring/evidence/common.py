"""What the studies share: where the bundle's parts are, and the checker run on one of three sets of districts.

    six       tests/districts, the districts a delivered program is run on (results in tests/results)
    beside    the three packages in the agent's image (the examples' own results; the pending district's sealed
              result and the crew's book for it are in authoring/provenance/as_it_is)
    small     authoring/evidence/small: seven districts a tenth of the size, built by the same generator

Every study runs complete programs through tests/judge_airflow.judge, the function the verifier's one test
calls, with the survey crew answering through the verifier's own `pqsurvey`.
"""
import atexit
import os
import shutil
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
TESTS = os.path.join(ROOT, "tests")
DATA = os.path.join(ROOT, "environment", "data")
AS_IT_IS = os.path.join(ROOT, "authoring", "provenance", "as_it_is")
SMALL = os.path.join(HERE, "small")
REFERENCE = os.path.join(ROOT, "solution", "airflow.py")
SECOND = os.path.join(HERE, "naive_airflow.py")
FAST = os.path.join(HERE, "fast_airflow.py")
sys.path.insert(0, TESTS)
import judge_airflow  # noqa: E402

_made = []


def _room():
    room = tempfile.mkdtemp(prefix="study_")
    os.chmod(room, 0o755)
    _made.append(room)
    return room


atexit.register(lambda: [shutil.rmtree(room, ignore_errors=True) for room in _made])


def sets(which):
    """(districts, results, books) directories for a set."""
    if which == "six":
        return os.path.join(TESTS, "districts"), os.path.join(TESTS, "results"), os.path.join(TESTS, "crew", "books")
    if which == "small":
        return os.path.join(SMALL, "districts"), os.path.join(SMALL, "results"), os.path.join(SMALL, "books")
    room = _room()
    districts, results, books = (os.path.join(room, part) for part in ("districts", "results", "books"))
    for part in (districts, results, books):
        os.mkdir(part)
    for kind in ("examples", "pending"):
        for name in sorted(os.listdir(os.path.join(DATA, kind))):
            package = os.path.join(DATA, kind, name)
            shutil.copytree(package, os.path.join(districts, name), ignore=shutil.ignore_patterns("expected.csv"))
            if kind == "examples":
                shutil.copy(os.path.join(package, "expected.csv"), os.path.join(results, name + ".csv"))
                shutil.copy(os.path.join(ROOT, "environment", "rig", "sealed", name + ".json"), books)
            else:
                shutil.copy(os.path.join(AS_IT_IS, name + "_result.csv"), os.path.join(results, name + ".csv"))
                shutil.copy(os.path.join(AS_IT_IS, name + "_book.json"), os.path.join(books, name + ".json"))
    return districts, results, books


def run(program, which="six", limit=None, only=None):
    """The checker's verdict for a program on a set of districts (only: a list of district names)."""
    districts, results, books = sets(which)
    if only:
        room = _room()
        for name in only:
            shutil.copytree(os.path.join(districts, name), os.path.join(room, name))
        districts = room
    # the verifier's pqsurvey, put where the user the program runs as can reach it whatever directory the
    # bundle was unpacked under
    tools = _room()
    shutil.copy(os.path.join(TESTS, "crew", "pqsurvey"), os.path.join(tools, "pqsurvey"))
    os.chmod(os.path.join(tools, "pqsurvey"), 0o755)
    return judge_airflow.judge(program, districts=districts, results=results, books=books,
                               limit=judge_airflow.LIMIT_S if limit is None else limit,
                               window=os.path.join(_room(), "window"), path_first=tools)


def lines(verdict, indent="  "):
    out = []
    for name, note in verdict["districts"].items():
        order = " ".join(note["survey_order"]) if note["survey_order"] else "none"
        if note["run"] != "in time":
            out.append("%s%-13s %s (%.1f s)" % (indent, name, note["run"], note["seconds"]))
        elif "not_the_table" in note:
            out.append("%s%-13s %s" % (indent, name, note["not_the_table"]))
        else:
            out.append("%s%-13s %5.1f s %5.1f s CPU  %4d of %4d points out of band  largest error %.2f of the band  order: %s" % (
                indent, name, note["seconds"], note["cpu_seconds"], note["points_out_of_band"], note["points"],
                note["largest_error_over_band"], order))
    if verdict["stopped"]:
        out.append(indent + "stopped: " + verdict["stopped"])
    out.append(indent + ("accepted" if verdict["accepted"] else "not accepted"))
    return "\n".join(out)
