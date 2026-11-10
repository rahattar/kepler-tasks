"""Verifier for cooler-fouling-assessment.

Reads /app/output/fouling.csv (env FOULING_PATH overrides) and compares each unit's reported as-found fouling
resistance with the bank's sealed definition (hx.py) on the test day. Never runs the reference solution and never
reads the shipped files. One test gates the reward; the per-unit record goes to /logs/verifier/metrics.json and
never gates.
"""
import json
import os

import grade_hx

FOULING = os.environ.get("FOULING_PATH", "/app/output/fouling.csv")
METRICS = "/logs/verifier/metrics.json"
_RESULT = {}


def _result():
    if not _RESULT:
        try:
            _RESULT.update(grade_hx.grade(FOULING))
        except Exception as e:                      # missing, unreadable or malformed file
            _RESULT.update(passed=False, units={}, error=repr(e))
        try:
            os.makedirs(os.path.dirname(METRICS), exist_ok=True)
            with open(METRICS, "w") as f:
                json.dump(dict(_RESULT, tolerance_m2k_per_kw=grade_hx.TOL), f, indent=1)
        except OSError:
            pass
    return _RESULT


def test_every_unit_within_0_04_m2k_per_kw():
    r = _result()
    assert "error" not in r, r.get("error")
    assert not r["missing"], "no row for: " + ", ".join(r["missing"])
    bad = {k: v for k, v in r["units"].items() if not v["passed"]}
    assert not bad, "units outside the requirement: " + "; ".join(
        "%s %+.3f m2K/kW" % (k, v["error_m2k_per_kw"]) for k, v in sorted(bad.items()))
