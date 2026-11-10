"""Pytest entry for skid-noise-guarantee. A single test decides the reward: the submitted
/app/output/sound_power.csv, graded against the sealed definition, has every one of the 27 values within the
tolerance. Per-machine results are written to /logs/verifier/metrics.json for the record only.
"""
import json
import os

import grade_power

RESULT = os.environ.get("SHEET_FILE", "/app/output/sound_power.csv")


def run():
    r = grade_power.score(RESULT)
    try:
        os.makedirs("/logs/verifier", exist_ok=True)
        with open("/logs/verifier/metrics.json", "w") as f:
            json.dump(r, f, indent=1)
    except OSError:
        pass
    return r


def test_levels_within_tolerance():
    r = run()
    assert "error" not in r, r.get("error")
    assert r["accepted"], "%d of %d values are within %.1f dB (all %d required)" % (
        r["npass"], r["gate"], r["tol"], r["gate"])
