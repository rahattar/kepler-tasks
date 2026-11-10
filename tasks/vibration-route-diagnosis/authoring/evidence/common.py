"""Shared helpers for the evidence scripts: write a program text to a scratch file and grade it with the verifier's
own grade_routes.score on the hidden route packages (run as the current user)."""
import os
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import grade_routes  # noqa: E402

SOLUTION = os.path.join(ROOT, "solution", "diagnose.py")
HIDDEN = os.path.join(ROOT, "tests", "hidden")


def grade_text(text):
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(text)
        path = f.name
    try:
        return grade_routes.score(path, hidden=HIDDEN, as_nobody=False)
    finally:
        os.unlink(path)


def misses(r):
    out = []
    for name, v in sorted(r["routes"].items()):
        if v.get("error"):
            out.append("%s fails to run" % name)
        for m, d in sorted(v.get("misdiagnosed", {}).items()):
            out.append("%s %s/%s as %s/%s" % (m, d["expected"][0], d["expected"][1], d["got"][0] or "-", d["got"][1] or "-"))
    return out
