"""Shared helpers of the evidence scripts. Every number the evidence reports on the hidden jobs comes from running a
complete program through tests/grade.py exactly as the verifier runs it (score(): a scratch copy of the program
alone, `python3 -I pumpdown.py JOB_DIR OUT_JSON` as nobody when run as root, the JSON read and judged by grade.py against
the truth), never from calling a program's functions directly."""
import importlib.util, json, os, sys, tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
HIDDEN = os.path.join(ROOT, "tests", "hidden")
EXAMPLE = os.path.join(ROOT, "environment", "data", "examples", "chamber-ex")
REFERENCE = os.path.join(ROOT, "solution", "pumpdown.py")
INDEPENDENT = os.path.join(ROOT, "authoring", "evidence", "independent.py")


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


G = load(os.path.join(ROOT, "tests", "grade.py"), "grade")
MAX_WRONG = G.MAX_WRONG
AS_NOBODY = os.geteuid() == 0


def truth():
    return json.load(open(os.path.join(HIDDEN, "truth.json")))


def write_program(src):
    d = tempfile.mkdtemp(prefix="evidence_"); os.chmod(d, 0o755)
    p = os.path.join(d, "pumpdown.py")
    with open(p, "w") as f:
        f.write(src)
    os.chmod(p, 0o644)
    return p


def program(path=REFERENCE, skip=(), replace=()):
    """A complete program: the reference (or another program) with source fragments replaced and/or some record checks
    left out (the reference's assess() takes the names of the checks to leave out)."""
    src = open(path).read()
    for old, new in replace:
        assert src.count(old) == 1, old
        src = src.replace(old, new)
    if skip:
        old = "        json.dump(assess(pkg), f)\n"
        assert src.count(old) == 1
        src = src.replace(old, "        json.dump(assess(pkg, frozenset(%r)), f)\n" % sorted(skip))
    return write_program(src)


def verify(prog):
    return G.score(prog, hidden=HIDDEN, as_nobody=AS_NOBODY)


def dev(v):
    """A chamber's signed relative deviation from the truth (or None when the chamber has no result)."""
    return v["ratio"] - 1 if "ratio" in v else None
