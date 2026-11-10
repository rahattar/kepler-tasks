"""Shared helpers for the evidence scripts: write a program text to a scratch file and grade it with the verifier's
own grade_cases.score on the hidden case packages (run as the current user)."""
import os
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import grade_cases  # noqa: E402

SOLUTION = os.path.join(ROOT, "solution", "design.py")
HIDDEN = os.path.join(ROOT, "tests", "hidden")


def grade_text(text):
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(text)
        path = f.name
    try:
        return grade_cases.score(path, hidden=HIDDEN, as_nobody=False)
    finally:
        os.unlink(path)


def misses(r):
    out = []
    for name, v in sorted(r["cases"].items()):
        if v["right"]:
            continue
        if v.get("error"):
            out.append("%s fails to run" % name)
        else:
            i = v["rating"]
            out.append("%s %.3fx oil %.2f C" % (name, i["price_ratio"], i["oil_out_c"]) if isinstance(i, dict) else
                       "%s %s" % (name, i))
    return out
