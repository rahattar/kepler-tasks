"""Shared by the studies in this folder: the bundle's paths, the verifier's bench, and works laid out for it.

A study never compares numbers itself. It writes a complete program file and hands it to tests/rope_bench.py,
which runs it the way the verifier does (alone in a directory, as nobody when the study is root, one thread to
a library, the limit on the clock and on CPU) and reads and judges its sheets with the verifier's own reader.
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
REFERENCE = os.path.join(BUNDLE, "solution", "ropes.py")
for folder in (TESTS, os.path.join(BUNDLE, "authoring", "provenance")):
    if folder not in sys.path:
        sys.path.insert(0, folder)
import rope_bench  # noqa: E402
import works  # noqa: E402

LIMIT = rope_bench.LIMIT_S
NO_LIMIT = 100000
HIDDEN = [w for w in works.WORKS if w["role"] == "hidden"]


def temporary(prefix):
    folder = tempfile.mkdtemp(prefix=prefix)
    os.chmod(folder, 0o755)
    atexit.register(shutil.rmtree, folder, True)
    return folder


def as_file(text, name="ropes.py"):
    """A program file with this text, in a folder of its own."""
    path = os.path.join(temporary("program-"), name)
    with open(path, "w") as handle:
        handle.write(text)
    os.chmod(path, 0o644)
    return path


def visible_as_works(which=("examples", "pending")):
    """The visible works laid out the way tests/ lays out the hidden ones: (works dir, sealed dir). The
    examples' sealed results are their expected.csv; the pending works' are authoring/provenance/pending_results."""
    root = temporary("visible-")
    works_dir, sealed_dir = os.path.join(root, "works"), os.path.join(root, "sealed")
    os.makedirs(sealed_dir)
    os.makedirs(works_dir)
    for kind in which:
        for name in sorted(os.listdir(os.path.join(DATA, kind))):
            source = os.path.join(DATA, kind, name)
            shutil.copytree(source, os.path.join(works_dir, name), ignore=shutil.ignore_patterns("expected.csv"))
            result = (os.path.join(source, "expected.csv") if kind == "examples"
                      else os.path.join(BUNDLE, "authoring", "provenance", "pending_results", name + ".csv"))
            shutil.copyfile(result, os.path.join(sealed_dir, name + ".csv"))
    return works_dir, sealed_dir


def made_again(busy, seed_shift=0, which=None):
    """The hidden works made again by the generator, with `busy` times the shipped number of lifts a day and
    another draw of everything random when seed_shift is not 0: (works dir, sealed dir). The table of what
    each works is, with its turned ropes and its ropes surveyed from the dead end, is the shipped one."""
    root = temporary("again-")
    for spec in HIDDEN:
        if which is None or spec["works"] in which:
            works.build(spec, root=root, seed_shift=seed_shift, busy=busy, place="works", sealed="sealed")
    return os.path.join(root, "works"), os.path.join(root, "sealed")


def judge(program, where=None, limit=LIMIT):
    if where is None:
        return rope_bench.judge(program, limit=limit)
    return rope_bench.judge(program, works_dir=where[0], sealed_dir=where[1], limit=limit)


def widest(verdict):
    found = [note["widest"] for note in verdict["trials"] if "widest" in note]
    return max(found) if found else None


def ropes_out(verdict):
    """The ropes with rows out, as 'works rope rows_out/rows' strings."""
    return ["%s %d/%d" % (rope, facts["rows_out"], facts["rows"])
            for note in verdict["trials"] for rope, facts in note.get("ropes", {}).items() if facts["rows_out"]]


def works_out(verdict):
    return [note["works"] for note in verdict["trials"] if note.get("rows_out", 1) != 0]


def indent(text, by="    "):
    return "\n".join(by + line for line in text.splitlines())
