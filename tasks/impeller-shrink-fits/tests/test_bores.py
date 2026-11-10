"""Pytest entry for impeller-shrink-fits. A single test decides the reward: the submitted
/app/output/bore_sheet.csv, graded against the sealed definition, makes every one of the 8 parts meet plant standard
RS-3. Per-part results are written to /logs/verifier/metrics.json for the record only.
"""
import json
import os

import grade_bores

RESULT = os.environ.get("SHEET_FILE", "/app/output/bore_sheet.csv")


def run():
    r = grade_bores.score(RESULT)
    try:
        os.makedirs("/logs/verifier", exist_ok=True)
        with open("/logs/verifier/metrics.json", "w") as f:
            json.dump(r, f, indent=1)
    except OSError:
        pass
    return r


def test_parts_meet_standard():
    r = run()
    assert "error" not in r, r.get("error")
    assert r["accepted"], "%d of 8 parts meet RS-3 (all %d required)" % (r["npass"], r["gate"])
