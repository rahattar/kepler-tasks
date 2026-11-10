"""Verifier for furnace-tc-calibration.

Loads each zone's corrections from /app/output/corrections.csv (env CORRECTIONS_PATH overrides) into the bay's
sealed definition (tc.py) and computes the wafer temperature when the controller holds 850 C and 1050 C. Never
runs the reference solution and never reads the shipped files. One test gates the reward; the per-zone record goes
to /logs/verifier/metrics.json and never gates.
"""
import json
import os

import grade_tc

CORRECTIONS = os.environ.get("CORRECTIONS_PATH", "/app/output/corrections.csv")
METRICS = "/logs/verifier/metrics.json"
_RESULT = {}


def _result():
    if not _RESULT:
        try:
            _RESULT.update(grade_tc.grade(CORRECTIONS))
        except Exception as e:                      # missing, unreadable or malformed file
            _RESULT.update(passed=False, zones={}, error=repr(e))
        try:
            os.makedirs(os.path.dirname(METRICS), exist_ok=True)
            with open(METRICS, "w") as f:
                json.dump(dict(_RESULT, tolerance_k=grade_tc.TOL), f, indent=1)
        except OSError:
            pass
    return _RESULT


def test_every_zone_holds_the_wafer_within_2_k_at_850_and_1050_c():
    r = _result()
    assert "error" not in r, r.get("error")
    assert not r["missing"], "no row for: " + ", ".join(r["missing"])
    bad = {k: v for k, v in r["zones"].items() if not v["passed"]}
    assert not bad, "zones outside acceptance: " + "; ".join(
        "%s 850 C %+.2f K, 1050 C %+.2f K" % (k, v["wafer_minus_setpoint_850_k"], v["wafer_minus_setpoint_1050_k"])
        for k, v in sorted(bad.items()))
