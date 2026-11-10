"""Pytest entry for crack-growth-life. A single test decides the reward: the submitted /app/output/intervals.json,
graded against the sealed definition, has all 16 re-inspection intervals within the required fraction
of the crack's remaining life. Per-crack results are written to /logs/verifier/metrics.json for the record only.
"""
import json
import os

import grade_intervals

RESULT = os.environ.get("INTERVALS_FILE", "/app/output/intervals.json")


def run():
    r = grade_intervals.score(RESULT)
    try:
        os.makedirs("/logs/verifier", exist_ok=True)
        with open("/logs/verifier/metrics.json", "w") as f:
            json.dump(r, f, indent=1)
    except OSError:
        pass
    return r


def test_intervals_meet_requirement():
    r = run()
    assert "error" not in r, r.get("error")
    assert r["accepted"], "%d of 16 intervals right (at least %d required)" % (r["npass"], r["gate"])
