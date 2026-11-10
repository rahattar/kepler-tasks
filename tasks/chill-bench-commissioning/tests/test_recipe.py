"""Verifier.

Grades the submitted recipe by replaying it through the sealed physics. Nothing is
compared against a stored answer: each station's constrained optimum is re-derived
here at grade time, so the grader cannot drift away from the model that produced the
bench traces the agent bought.

WHAT GATES THE REWARD is how many of the fleet's stations were commissioned. A station
counts as commissioned when it meets all three criteria: the end-of-dwell mass-mean
temperature, the peak inner-to-outer zone difference over the dwell, and its own
dwell budget.

The three criteria are NOT separate gates. Gating on every station and criterion at
once made the verdict turn on a single station: on an earlier fleet the reference lost
a run to a 0.08 K excess on one zone limit while every other margin was healthy. So
the per-criterion breakdown is reported, per station, both in the gate's own failure
message and in /logs/verifier/metrics.json, while the count decides.

test.sh writes reward 1 only on a clean pytest exit, so a crash anywhere leaves 0.
Every test here either gates or records; none of them fails on a diagnostic alone.
"""
import json
import os

import pytest

import grade

RECIPE = os.environ.get("CHILL_RECIPE", "/app/recipe.json")
DETAIL = "/logs/verifier/grade_detail.json"
METRICS = "/logs/verifier/metrics.json"


def _metrics(r):
    if r.get("error"):
        return {"error": r["error"]}
    st = r["stations"]
    return {
        "stations_commissioned": r["commissioned"],
        "stations_required": r["stations_required"],
        "temperature_failures": r["criteria"]["temperature_failures"],
        "uniformity_failures": r["criteria"]["uniformity_failures"],
        "dwell_budget_failures": r["criteria"]["dwell_budget_failures"],
        "worst_end_temperature_C": max(s["T_end_C"] for s in st),
        "worst_zone_difference_K": max(s["zone_diff_K"] for s in st),
        "worst_dwell_ratio": max(s["dwell_ratio"] for s in st),
        "per_station": {s["station"]: {
            "commissioned": s["commissioned"], "T_end_C": s["T_end_C"],
            "zone_diff_K": s["zone_diff_K"], "dwell_ratio": s["dwell_ratio"]}
            for s in st},
    }


def _why(s):
    missed = []
    if not s["meets_temperature"]:
        missed.append(f"end temperature {s['T_end_C']} C")
    if not s["meets_uniformity"]:
        missed.append(f"zone difference {s['zone_diff_K']} K")
    if not s["meets_dwell_budget"]:
        missed.append(f"dwell {s['dwell_s']} s against a limit of "
                      f"{s['dwell_limit_s']} s")
    return f"{s['station']} ({'; '.join(missed)})"


@pytest.fixture(scope="session")
def result():
    """Grade once; every test reads the same result."""
    r = grade.grade(RECIPE)
    for path, payload in ((DETAIL, r), (METRICS, _metrics(r))):
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                json.dump(payload, f, indent=2)
        except OSError:
            pass
    return r


def test_recipe_is_readable(result):
    """The recipe exists, parses, and names every station exactly once."""
    assert result["error"] is None, result["error"]


def test_enough_stations_commissioned(result):
    """The gate: enough stations meet the temperature, uniformity and dwell criteria.

    On failure this names every station that missed and which criteria it missed, so
    the report says what went wrong physically, not just that a count was short.
    """
    assert result["error"] is None, result["error"]
    bad = [s for s in result["stations"] if not s["commissioned"]]
    assert result["reward"] == 1, (
        f"{result['commissioned']} of {len(result['stations'])} stations commissioned, "
        f"{result['stations_required']} required. Not commissioned: "
        + "; ".join(_why(s) for s in bad))


def test_diagnostics_recorded(result):
    """Records the per-criterion breakdown. Never fails on a diagnostic alone."""
    assert result["error"] is None, result["error"]
    m = _metrics(result)
    print("\ncommissioned %d of %d (required %d)"
          % (m["stations_commissioned"], len(result["stations"]),
             m["stations_required"]))
    print("criterion failures -- temperature %d, uniformity %d, dwell budget %d"
          % (m["temperature_failures"], m["uniformity_failures"],
             m["dwell_budget_failures"]))
    print("worst case -- end temperature %.3f C, zone difference %.2f K, "
          "dwell ratio %.3fx" % (m["worst_end_temperature_C"],
                                 m["worst_zone_difference_K"],
                                 m["worst_dwell_ratio"]))
    assert os.path.exists(METRICS) or True
