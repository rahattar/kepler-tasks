"""Pytest entry for hoist-brake-sizing. A single test decides the reward: the submitted /app/output/brakes.json,
graded against the sealed definition, gives every one of the 12 hoists a brake that meets all five requirements of
plant standard MS-14. Per-hoist results are written to /logs/verifier/metrics.json for the record only.
"""
import json
import os

import grade_brakes

RESULT = os.environ.get("BRAKES_FILE", "/app/output/brakes.json")


def run():
    r = grade_brakes.score(RESULT)
    try:
        os.makedirs("/logs/verifier", exist_ok=True)
        with open("/logs/verifier/metrics.json", "w") as f:
            json.dump(r, f, indent=1)
    except OSError:
        pass
    return r


def test_brakes_meet_standard():
    r = run()
    assert "error" not in r, r.get("error")
    assert r["accepted"], "%d of 12 brakes meet every requirement (all %d required)" % (r["npass"], r["gate"])
