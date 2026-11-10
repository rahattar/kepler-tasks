"""Pytest entry for tempering-hardness-window. A single test decides the reward: the submitted
/app/output/tempering.json, graded against the sealed definition, puts every one of the 13 batches within its drawing's
hardness range at a setpoint the procedure permits. Per-batch results are written to /logs/verifier/metrics.json for
the record only.
"""
import json
import os

import grade_tempering

RESULT = os.environ.get("TEMPERING_FILE", "/app/output/tempering.json")


def run():
    r = grade_tempering.score(RESULT)
    try:
        os.makedirs("/logs/verifier", exist_ok=True)
        with open("/logs/verifier/metrics.json", "w") as f:
            json.dump(r, f, indent=1)
    except OSError:
        pass
    return r


def test_batches_within_hardness_range():
    r = run()
    assert "error" not in r, r.get("error")
    assert r["accepted"], "%d of 13 batches within their hardness range (all %d required)" % (r["npass"], r["gate"])
