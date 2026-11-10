"""Verifier for vav-airflow-calibration.

Loads each box's K and offset from /app/output/calibration.csv (env CALIBRATION_PATH overrides) into the floor's
sealed definition (vav.py) and computes the airflow each box delivers when it controls to design minimum and to
design maximum. Never runs the reference solution and never reads the shipped files. One test gates the reward;
the per-box record goes to /logs/verifier/metrics.json and never gates.
"""
import json
import os

import grade_vav

CALIBRATION = os.environ.get("CALIBRATION_PATH", "/app/output/calibration.csv")
METRICS = "/logs/verifier/metrics.json"
_RESULT = {}


def _result():
    if not _RESULT:
        try:
            _RESULT.update(grade_vav.grade(CALIBRATION))
        except Exception as e:                      # missing, unreadable or malformed file
            _RESULT.update(passed=False, boxes={}, error=repr(e))
        try:
            os.makedirs(os.path.dirname(METRICS), exist_ok=True)
            with open(METRICS, "w") as f:
                json.dump(dict(_RESULT, tolerance=grade_vav.TOL), f, indent=1)
        except OSError:
            pass
    return _RESULT


def test_every_box_delivers_its_design_minimum_and_maximum_within_ten_percent():
    r = _result()
    assert "error" not in r, r.get("error")
    assert not r["missing"], "no row for: " + ", ".join(r["missing"])
    bad = {t: v for t, v in r["boxes"].items() if not v["passed"]}
    assert not bad, "boxes outside acceptance: " + "; ".join(
        "%s min %+.1f%% max %+.1f%%" % (t, 100 * v["design_min_error"], 100 * v["design_max_error"])
        for t, v in sorted(bad.items()))
