"""Verifier for cz-silicon-control.

Grades the submitted supervisor (env PULLER_SUPERVISOR, default /app/supervisor.py) in closed loop on the eight
graded HZ-B bodies of the sealed definition (see grade.py for the protocol, the sandbox and what a valid command is).

Exactly one test gates the reward: every body completes without a controller error; on every body from 50 mm to
1500 mm the true growth rate, averaged over each 5 mm of crystal, stays within +-1 % of the PS-R07 program and the
true diameter never falls below 301.0 mm; and the true diameter averaged from 50 mm to 1500 mm over all bodies is at
most 303.0 mm. The other tests only record: the full record goes to /logs/verifier/grade_detail.json and a summary
to /logs/verifier/metrics.json, so a diagnostic can never zero an otherwise valid run, and a failing run still says
why.

test.sh writes the reward from pytest's exit status, so a crash anywhere leaves 0.
"""
import json
import os

import pytest

import grade

CONTROLLER = os.environ.get("PULLER_SUPERVISOR", "/app/supervisor.py")
DETAIL = "/logs/verifier/grade_detail.json"
METRICS = "/logs/verifier/metrics.json"


def _metrics(r):
    m = {"reward": r["reward"], "error": r.get("error"), "limits": r.get("limits"),
         "d_mean_all_mm": r.get("d_mean_all"), "fails": r.get("fails")}
    m["bodies"] = [{k: b.get(k) for k in ("seed", "error", "steps", "vg_max", "vg_out_mm", "d_min", "d_mean", "done",
                                          "minutes", "init_s", "step_max_s", "controller_wall_s")}
                   for b in r.get("bodies", [])]
    return m


def _write(path, payload):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(payload, f, indent=2)
    except OSError as e:
        print("could not write %s: %s" % (path, e))


@pytest.fixture(scope="session")
def result():
    """Grade once; every test reads the same result."""
    return grade.grade(CONTROLLER)


def test_grade_detail_recorded(result):
    """Records the full grading record. Never fails on its own."""
    _write(DETAIL, result)
    grade.report(result)


def test_metrics_recorded(result):
    """Records the summary metrics. Never fails on its own."""
    _write(METRICS, _metrics(result))


def test_supervisor_meets_vg_and_diameter(result):
    """THE GATE: no controller error; V/G within +-1 %, true diameter >= 301.0 mm on every body; mean <= 303.0 mm."""
    assert not result.get("error"), result["error"]
    assert not result["fails"], "; ".join(result["fails"])
    assert result["reward"] == 1
