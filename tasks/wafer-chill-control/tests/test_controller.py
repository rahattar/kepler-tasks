"""Verifier for wafer-chill-control.

Grades /app/controller.py in closed loop on the hidden wafer set through the sealed plant
(see grade.py for what a wafer must satisfy and how the controller is sandboxed).

Exactly one test gates the reward: every wafer passes AND the total cycle time is within
the allowance of the total perfect-knowledge cycle. The other tests only record: the
per-wafer breakdown goes to /logs/verifier/metrics.json and grade_detail.json, so a
diagnostic can never zero an otherwise valid run, and a failing run still says why.

test.sh writes the reward from pytest's exit status, so a crash anywhere leaves 0.
"""
import json
import os

import pytest

import grade

CONTROLLER = os.environ.get("CHILL_CONTROLLER", "/app/controller.py")
DETAIL = "/logs/verifier/grade_detail.json"
METRICS = "/logs/verifier/metrics.json"


def _metrics(r):
    if r.get("error"):
        return {"error": r["error"]}
    ws = r["wafers"]
    released = [w for w in ws if w["T_release_C"] is not None]
    return {
        "wafers_passed": r["passed_wafers"],
        "wafers_total": len(ws),
        "cycle_ratio": r["cycle_ratio"],
        "cycle_limit_ratio": r["cycle_limit_ratio"],
        "zone_failures": sum(not w["meets_zone"] for w in ws),
        "release_failures": sum(not w["meets_release"] for w in ws),
        "controller_errors": sum(w["error"] is not None for w in ws),
        "worst_zone_dT_K": max(w["worst_zone_dT_K"] for w in ws),
        "hottest_release_C": max((w["T_release_C"] for w in released), default=None),
        "per_wafer": {w["id"]: {k: w.get(k) for k in (
            "passed", "cycle_s", "benchmark_s", "cycle_ratio", "worst_zone_dT_K",
            "T_release_C", "error")} for w in ws},
    }


def _why(w):
    if w["error"]:
        return "%s: %s" % (w["id"], w["error"])
    missed = []
    if not w["meets_zone"]:
        missed.append("zone difference reached %.3f K" % w["worst_zone_dT_K"])
    if not w["meets_release"]:
        missed.append("released at a mass mean of %.3f C" % w["T_release_C"])
    return "%s: %s" % (w["id"], "; ".join(missed))


@pytest.fixture(scope="session")
def result():
    """Grade once; every test reads the same result."""
    r = grade.grade(CONTROLLER)
    for path, payload in ((DETAIL, r), (METRICS, _metrics(r))):
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                json.dump(payload, f, indent=2)
        except OSError:
            pass
    return r


def test_controller_is_gradable(result):
    """Records whether a controller file was found at all."""
    if result.get("error"):
        print("not gradable: %s" % result["error"])


def test_controller_commissions_the_hidden_wafers(result):
    """THE GATE: every wafer within both limits and the total cycle within the allowance."""
    assert not result.get("error"), result.get("error")
    failed = [w for w in result["wafers"] if not w["passed"]]
    assert not failed, ("%d of %d wafers failed: %s"
                        % (len(failed), len(result["wafers"]),
                           "; ".join(_why(w) for w in failed[:6])))
    assert result["cycle_ratio"] <= result["cycle_limit_ratio"] + grade.EPS, (
        "total cycle time is %.4f times the total perfect-knowledge cycle; the limit is "
        "%.2f" % (result["cycle_ratio"], result["cycle_limit_ratio"]))


def test_diagnostics_recorded(result):
    """Records the per-wafer breakdown. Never fails on its own."""
    if result.get("error"):
        return
    for w in result["wafers"]:
        print("%s %-8s passed=%s cycle=%s bench=%s zone=%.3f release=%s %s"
              % (w["id"], w["film"], w["passed"], w["cycle_s"], w["benchmark_s"],
                 w["worst_zone_dT_K"], w["T_release_C"], w["error"] or ""))
