"""Shared helpers for the evidence scripts: write a program text to a scratch file and grade it with the verifier's
own grade_audits.score on the hidden audit packages (run as the current user)."""
import os
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import grade_audits  # noqa: E402

SOLUTION = os.path.join(ROOT, "solution", "audit.py")
HIDDEN = os.path.join(ROOT, "tests", "hidden")
SHORT = {"avg_demand_m3_min": "avg", "peak_demand_m3_min": "peak", "leak_m3_min": "leak",
         "specific_power_kw_per_m3_min": "sp"}


def grade_text(text):
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(text)
        path = f.name
    try:
        return grade_audits.score(path, hidden=HIDDEN, as_nobody=False)
    finally:
        os.unlink(path)


def misses(r):
    out = []
    for name, v in sorted(r["cases"].items()):
        if v["right"]:
            continue
        if v.get("error"):
            out.append("%s fails to run" % name)
            continue
        e = v["error_pct"]
        bad = ["%s %+.1f %%" % (SHORT[k], e[k]) for k in e if abs(e[k]) > 100 * grade_audits.TOL[k]]
        out.append("%s (%s)" % (name, ", ".join(bad)))
    return out
