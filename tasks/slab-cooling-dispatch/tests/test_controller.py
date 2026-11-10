"""Verifier for slab-cooling-dispatch.

Grades the submitted controller (env TABS_CONTROLLER, default /app/controller.py) in closed loop
over the eight hidden weeks through the sealed two-zone TABS plant and chiller (see grade.py for
the protocol, the sandbox and what a valid command is).

Exactly one test gates the reward: the run finishes without a controller error, at most one of
the 16 zone-weeks exceeds 0.5 K h of occupied operative-temperature deviation from 21-26 C, and
the total cooling cost is at most 1.15 x the benchmark's. The other tests only record: the full
record goes to /logs/verifier/grade_detail.json and a summary to /logs/verifier/metrics.json, so
a diagnostic can never zero an otherwise valid run, and a failing run still says why.

test.sh writes the reward from pytest's exit status, so a crash anywhere leaves 0.
"""
import json
import os

import pytest

import grade

CONTROLLER = os.environ.get("TABS_CONTROLLER", "/app/controller.py")
DETAIL = "/logs/verifier/grade_detail.json"
METRICS = "/logs/verifier/metrics.json"


def _metrics(r):
    m = {
        "reward": r["reward"],
        "error": r.get("error"),
        "error_at": r.get("error_at"),
        "steps_completed": r.get("steps_completed"),
        "steps_total": r.get("steps_total"),
        "init_s": r.get("init_s"),
        "step_max_s": r.get("step_max_s"),
        "controller_wall_s": r.get("controller_wall_s"),
    }
    if r.get("error"):
        return m
    m.update({
        "total_cost": r["total_cost"],
        "bench_total_cost": r["bench_total_cost"],
        "ratio_total": r["ratio_total"],
        "ratio_limit": grade.ALLOW,
        "zone_week_fails": r["zone_week_fails"],
        "zone_week_fails_ok": grade.FAILS_OK,
        "dev_max_kh": grade.DEV_MAX,
        "worst_zone_week_dev_kh": max(max(r["dev"][z]) for z in r["dev"]),
        "per_week": [{"week": i + 1, "cost": r["cost"][i], "bench_cost": r["bench_cost"][i],
                      "ratio": r["ratio_week"][i],
                      **{"dev_%s" % z: r["dev"][z][i] for z in r["dev"]}}
                     for i in range(len(r["cost"]))],
    })
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


def test_controller_meets_comfort_and_cost(result):
    """THE GATE: no controller error, at most 1 of 16 zone-weeks over 0.5 K h, cost <= 1.15 x benchmark."""
    assert not result.get("error"), "%s%s (after %s of %s steps)" % (
        result["error"], " at %s" % result["error_at"] if result.get("error_at") else "",
        result.get("steps_completed"), result.get("steps_total"))
    over = ["week %d %s %.3f K h" % (i + 1, z, v) for z in result["dev"]
            for i, v in enumerate(result["dev"][z]) if v > grade.DEV_MAX]
    assert result["zone_week_fails"] <= grade.FAILS_OK, (
        "%d of %d zone-weeks exceed %.1f K h of occupied operative deviation (at most %d may): %s"
        % (result["zone_week_fails"], result["zone_weeks"], grade.DEV_MAX, grade.FAILS_OK,
           "; ".join(over[:8])))
    assert result["ratio_total"] <= grade.ALLOW, (
        "total cooling cost $%.3f is %.4f x the benchmark's $%.3f; the limit is %.2f"
        % (result["total_cost"], result["ratio_total"], result["bench_total_cost"], grade.ALLOW))
    assert result["reward"] == 1
