"""Pytest entry for bore-form-acceptance. A single test decides the reward: the submitted /app/output/form.csv,
graded against the sealed definition, gets the form error and the sentence of every one of the 14 features right.
Per-feature results are written to /logs/verifier/metrics.json for the record only.
"""
import json
import os

import grade_form

RESULT = os.environ.get("FORM_FILE", "/app/output/form.csv")


def run():
    r = grade_form.score(RESULT)
    try:
        os.makedirs("/logs/verifier", exist_ok=True)
        with open("/logs/verifier/metrics.json", "w") as f:
            json.dump(r, f, indent=1)
    except OSError:
        pass
    return r


def test_features_sentenced_correctly():
    r = run()
    assert "error" not in r, r.get("error")
    assert r["accepted"], "%d of 14 features right (all %d required)" % (r["npass"], r["gate"])
