"""Pytest entry for oil-cooler-selection. A single test decides the reward: the submitted program
/app/output/design.py, run on each of the eight hidden cooler case packages, selects a design that meets the case's
requirements at its sealed design case within 6 % of the cheapest compliant price on at least seven of them.
Per-case results are written to /logs/verifier/metrics.json for the record only.
"""
import json
import os

import grade_cases

PROGRAM = os.environ.get("DESIGN_PROGRAM", "/app/output/design.py")


def run():
    if not os.path.isfile(PROGRAM):
        r = {"accepted": False, "cases": {}, "error": "no program at %s" % PROGRAM}
    else:
        r = grade_cases.score(PROGRAM, as_nobody=os.geteuid() == 0)
    try:
        os.makedirs("/logs/verifier", exist_ok=True)
        with open("/logs/verifier/metrics.json", "w") as f:
            json.dump(dict(r, max_wrong=grade_cases.MAX_WRONG), f, indent=1)
    except OSError:
        pass
    return r


def test_program_on_hidden_cases():
    r = run()
    assert "error" not in r, r.get("error")
    assert r["accepted"], "%d of %d hidden cases wrong (at most %d allowed)" % (
        r["wrong"], len(r["cases"]), grade_cases.MAX_WRONG)
