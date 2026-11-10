"""Shared helpers for the evidence scripts: write a program text to a scratch file and grade it with the verifier's
own grade_hpu.score on the hidden packages (run as the current user)."""
import os
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import grade_hpu  # noqa: E402

SOLUTION = os.path.join(ROOT, "solution", "hpu.py")
HIDDEN = os.path.join(ROOT, "tests", "hidden")
SHORT = {"oil_delivered_l": "oil", "peak_flow_l_min": "peak", "hydraulic_energy_kj": "hyd", "electrical_energy_kj": "el",
         "unit_efficiency": "eff"}


def grade_text(text):
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(text)
        path = f.name
    try:
        return grade_hpu.score(path, hidden=HIDDEN, as_nobody=False)
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
        bad = []
        for k in e:
            if k in grade_hpu.ABSOLUTE:
                if abs(e[k]) > grade_hpu.TOL[k]:
                    bad.append("%s %+.3f" % (SHORT[k], e[k]))
            elif abs(e[k]) > 100 * grade_hpu.TOL[k]:
                bad.append("%s %+.1f %%" % (SHORT[k], e[k]))
        out.append("%s (%s)" % (name, ", ".join(bad)))
    return out


def worst(r):
    w = {k: 0.0 for k in grade_hpu.TOL}
    for v in r["cases"].values():
        for k, e in v.get("error_pct", {}).items():
            w[k] = max(w[k], abs(e))
    return w
