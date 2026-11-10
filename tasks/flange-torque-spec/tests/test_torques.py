"""Pytest entry for flange-torque-spec. A single test decides the reward: the submitted /app/output/torques.json,
graded against the sealed definition, has at least 15 of the 16 joints assembled correctly. Per-joint results are
written to /logs/verifier/metrics.json for the record only.
"""
import json
import os

import grade_torques

RESULT = os.environ.get("TORQUES_FILE", "/app/output/torques.json")


def run():
    r = grade_torques.score(RESULT)
    try:
        os.makedirs("/logs/verifier", exist_ok=True)
        with open("/logs/verifier/metrics.json", "w") as f:
            json.dump(r, f, indent=1)
    except OSError:
        pass
    return r


def test_bolt_up_meets_requirement():
    r = run()
    assert "error" not in r, r.get("error")
    assert r["accepted"], "%d of 16 joints right (at least %d required)" % (r["npass"], r["gate"])
