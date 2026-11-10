"""Shared helpers for the evidence scripts: write a program text to a scratch file and grade it with the verifier's own
grade_tool.score on the hidden record sets (run as the current user)."""
import os
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tests"))
sys.path.insert(0, os.path.join(ROOT, "authoring", "provenance"))
import grade_tool  # noqa: E402
import bugs        # noqa: E402

SOLUTION = os.path.join(ROOT, "solution", "gtperf.py")
HIDDEN = os.path.join(ROOT, "tests", "hidden")


def grade_text(text):
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(text)
        path = f.name
    try:
        return grade_tool.score(path, hidden=HIDDEN, as_nobody=False)
    finally:
        os.unlink(path)


def summary(r):
    bad = {k: v for k, v in r["sets"].items() if not v["accepted"]}
    worst = 0.0
    for v in r["sets"].values():
        if "output_miss" in v:
            worst = max(worst, abs(v["output_miss"]), abs(v["heat_rate_miss"]))
    parts = []
    for k, v in sorted(bad.items()):
        if v.get("error"):
            parts.append("%s fails to run (%s)" % (k, v["error"].splitlines()[-1][:60]))
        else:
            parts.append("%s %+.2f/%+.2f" % (k, 100 * v["output_miss"], 100 * v["heat_rate_miss"]))
    return len(bad), 100 * worst, "; ".join(parts)
