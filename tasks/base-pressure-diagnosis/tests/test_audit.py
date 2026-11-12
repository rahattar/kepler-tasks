"""Pytest entry for base-pressure-diagnosis. A single test decides the reward: the submitted
/app/output/diagnosis.csv, graded against the sealed fleet, gets at least the gate number of chambers right in all
three of cause, gas load and speed. Per-chamber results go to /logs/verifier/metrics.json for the record only.
"""
import json
import os

import grade_audit

RESULT = os.environ.get("SHEET_FILE", "/app/output/diagnosis.csv")


def run():
    r = grade_audit.score(RESULT)
    try:
        os.makedirs("/logs/verifier", exist_ok=True)
        with open("/logs/verifier/metrics.json", "w") as f:
            json.dump(r, f, indent=1)
    except OSError:
        pass
    return r


def test_audit_sheet_is_right():
    r = run()
    assert "error" not in r, r.get("error")
    assert r["accepted"], "%d of %d chambers right in cause, gas load and speed (%d required)" % (
        r["npass"], len(grade_audit.IDS), r["gate"])
