"""Pytest entry for recip-cylinder-limits. A single test decides the reward: the submitted
/app/output/cylinder_limits.csv, graded against the sealed definition, has every one of the twelve values right.
Per-cylinder results are written to /logs/verifier/metrics.json for the record only.
"""
import json
import os

import grade_limits

RESULT = os.environ.get("SHEET_FILE", "/app/output/cylinder_limits.csv")


def run():
    r = grade_limits.score(RESULT)
    try:
        os.makedirs("/logs/verifier", exist_ok=True)
        with open("/logs/verifier/metrics.json", "w") as f:
            json.dump(r, f, indent=1)
    except OSError:
        pass
    return r


def test_limits_within_tolerance():
    r = run()
    assert "error" not in r, r.get("error")
    assert r["accepted"], "%d of %d values are right (tolerance %.1f per cent, all %d required)" % (
        r["npass"], r["gate"], 100.0 * r["tol"], r["gate"])
