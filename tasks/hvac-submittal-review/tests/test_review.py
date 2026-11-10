"""Verifier for hvac-submittal-review.

Grades /app/review.json (env REVIEW_PATH overrides) against the District's own review of the submittal,
computed by project.truth() from the sealed as-built definition (never from the shipped files and
never from the reference solution). One test gates the reward; the full record goes to
/logs/verifier/metrics.json and never gates.
"""
import json
import os

import grade

REVIEW = os.environ.get("REVIEW_PATH", "/app/review.json")
METRICS = "/logs/verifier/metrics.json"
_RESULT = {}


def _result():
    if not _RESULT:
        _RESULT.update(grade.grade(REVIEW))
        try:
            os.makedirs(os.path.dirname(METRICS), exist_ok=True)
            with open(METRICS, "w") as f:
                json.dump(dict(_RESULT, tolerances=grade.TOL, units_allowed_wrong=grade.ALLOW_WRONG), f, indent=1)
        except OSError:
            pass
    return _RESULT


def test_review_matches_the_districts_review():
    r = _result()
    assert r["error"] is None, r["error"]
    assert r["submittal_ok"], f"submittal decision {r['submittal']!r}, review says {r['expected_submittal']!r}"
    assert not r["wrong"], "units not matching the District's review: " + "; ".join(
        f"{u}: " + "; ".join(r["units"][u]["reasons"]) for u in r["wrong"])
