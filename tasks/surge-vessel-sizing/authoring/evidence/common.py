"""Shared helpers of the evidence scripts. Every number the evidence reports on the hidden mains comes from running a
complete program through tests/grade.py exactly as the verifier runs it (score(): a scratch copy of the program
alone, `python3 -I surge.py MAIN_DIR OUT_JSON` as nobody when run as root, the JSON read and judged by grade.py with
the sealed check), never from calling a program's functions directly."""
import importlib.util, json, os, sys, tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
HIDDEN = os.path.join(ROOT, "tests", "hidden")
EXAMPLE = os.path.join(ROOT, "environment", "data", "examples", "kestrel-lane")
REFERENCE = os.path.join(ROOT, "solution", "surge.py")
INDEPENDENT = os.path.join(ROOT, "authoring", "evidence", "independent.py")


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


sys.path.insert(0, os.path.join(ROOT, "tests"))
G = load(os.path.join(ROOT, "tests", "grade.py"), "grade")
MAX_WRONG = G.MAX_WRONG
AS_NOBODY = os.geteuid() == 0


def truth():
    return json.load(open(os.path.join(HIDDEN, "truth.json")))


def write_program(src):
    d = tempfile.mkdtemp(prefix="evidence_"); os.chmod(d, 0o755)
    p = os.path.join(d, "surge.py")
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


# the reference's margins, and their removal (the method's own smallest vessel)
REF_NO_MARGIN = [("    Vg = hi * 1.02\n", "    Vg = hi\n"), ("    V = run(Vg)[1] / GASMAX * 1.03\n", "    V = run(Vg)[1] / GASMAX\n")]
IND_NO_MARGIN = [("    gas = 1.03 * b\n", "    gas = b\n"), ('round(1.04 * vmax / 0.85, 2)', 'round(vmax / 0.85, 4)')]


def verify(prog):
    return G.score(prog, hidden=HIDDEN, as_nobody=AS_NOBODY)


def ratios(r):
    return {p: (v.get("ratio_to_smallest"), v["right"], v.get("error", "")) for p, v in r["packages"].items()}
