"""Pytest entry for shrink-fit-hubs. A single test decides the reward: the submitted /app/output/fits.json, graded
against the sealed definition, makes every one of the 12 joints meet plant standard ST-9. Per-joint results are
written to /logs/verifier/metrics.json for the record only.
"""
import json
import os

import grade_fits

RESULT = os.environ.get("FITS_FILE", "/app/output/fits.json")


def run():
    r = grade_fits.score(RESULT)
    try:
        os.makedirs("/logs/verifier", exist_ok=True)
        with open("/logs/verifier/metrics.json", "w") as f:
            json.dump(r, f, indent=1)
    except OSError:
        pass
    return r


def test_joints_meet_standard():
    r = run()
    assert "error" not in r, r.get("error")
    assert r["accepted"], "%d of 12 joints meet ST-9 (all %d required)" % (r["npass"], r["gate"])
