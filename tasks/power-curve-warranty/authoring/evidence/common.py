"""Shared helpers of the evidence scripts. Every number the evidence reports on the hidden packages comes from running
a complete program through tests/grade.py exactly as the verifier runs it (score(): a scratch copy of the program
alone, `python3 -I pp12.py PACKAGE OUT_CSV` as nobody when run as root, the CSV read and judged by grade.py), never
from calling a program's functions directly."""
import importlib.util, json, os, sys, tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
HIDDEN = os.path.join(ROOT, "tests", "hidden")
EXAMPLE = os.path.join(ROOT, "environment", "data", "examples", "ridgeback-2026h1")
REFERENCE = os.path.join(ROOT, "solution", "pp12.py")
INDEPENDENT = os.path.join(ROOT, "authoring", "evidence", "independent.py")
TAIL = 'if __name__ == "__main__":\n    main(sys.argv[1], sys.argv[2])\n'


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


G = load(os.path.join(ROOT, "tests", "grade.py"), "grade")
TOL, MAX_WRONG = G.TOL, G.MAX_WRONG
AS_NOBODY = os.geteuid() == 0


def truth():
    return json.load(open(os.path.join(HIDDEN, "truth.json")))


def write_program(src):
    """A complete program file (mode 644) for the verifier to copy and run."""
    d = tempfile.mkdtemp(prefix="evidence_"); os.chmod(d, 0o755)
    p = os.path.join(d, "pp12.py")
    with open(p, "w") as f:
        f.write(src)
    os.chmod(p, 0o644)
    return p


def reference_program(skip=(), replace=None):
    """The reference program with one source fragment replaced and/or some record checks left out (its assess()
    takes the names of the checks to leave out); a complete CLI program like the submission."""
    src = open(REFERENCE).read()
    assert src.endswith(TAIL)
    if replace:
        old, new = replace
        assert src.count(old) == 1, old
        src = src.replace(old, new)
    if skip:
        old = "def main(pkg, out):\n    res = assess(pkg)\n"
        assert src.count(old) == 1
        src = src.replace(old, "def main(pkg, out):\n    res = assess(pkg, frozenset(%r))\n" % sorted(skip))
    return write_program(src)


def verify(program):
    """grade.score() on the hidden packages, as the verifier runs it."""
    return G.score(program, hidden=HIDDEN, as_nobody=AS_NOBODY)


def summary(r, T):
    """Per package: (wrong, worst |error|, [(turbine, error, claim, true claim) of the wrong turbines], error text)."""
    out = {}
    for p in sorted(T):
        v = r["packages"][p]
        if "error" in v:
            out[p] = (v["wrong"], float("nan"), [], v["error"]); continue
        worst, bad = 0.0, []
        for t in sorted(T[p]):
            x = v["turbines"][t]; e = x["aep_ratio"] - T[p][t]["aep_ratio"]
            worst = max(worst, abs(e))
            if not x["right"]:
                bad.append((t, e, x["warranty_claim"], T[p][t]["warranty_claim"]))
        out[p] = (v["wrong"], worst, bad, "")
    return out
