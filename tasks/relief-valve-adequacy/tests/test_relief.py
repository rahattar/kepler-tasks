"""Pytest entry for relief-valve-adequacy. A single test decides the reward: the submitted
/app/output/relief.csv, graded against the sealed definition, is right on all nine valves. Per-valve results are
written to /logs/verifier/metrics.json for the record only.
"""
import json
import os

import grade_relief

RESULT = os.environ.get("SHEET_FILE", "/app/output/relief.csv")


def run():
    r = grade_relief.score(RESULT)
    try:
        os.makedirs("/logs/verifier", exist_ok=True)
        with open("/logs/verifier/metrics.json", "w") as f:
            json.dump(r, f, indent=1)
    except OSError:
        pass
    return r


def test_valves_assessed_correctly():
    r = run()
    assert "error" not in r, r.get("error")
    assert r["accepted"], "%d of 9 valves right (all %d required)" % (r["npass"], r["gate"])
