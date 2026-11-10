"""Pytest entry for turbine-performance-test. A single test decides the reward: GT-1's corrected output and corrected heat
rate, as found and as left, in /app/output/gt1_corrected_results.csv, each within 0.5 % of the sealed value. The misses are
written to /logs/verifier/metrics.json for the record only. Nothing from the solution or the shipped data is read.
"""
import json
import os

import grade_results

PATH = os.environ.get("GT1_RESULTS_PATH", "/app/output/gt1_corrected_results.csv")


def run():
    try:
        r = grade_results.score(PATH)
    except Exception as e:                           # absent, not CSV, wrong columns or values
        r = {"accepted": False, "conditions": {}, "missing": [], "error": repr(e)}
    try:
        os.makedirs("/logs/verifier", exist_ok=True)
        with open("/logs/verifier/metrics.json", "w") as f:
            json.dump(dict(r, limit_relative=grade_results.LIMIT), f, indent=1)
    except OSError:
        pass
    return r


def test_both_conditions_within_limit():
    r = run()
    assert "error" not in r, r.get("error")
    assert not r["missing"], "missing conditions: %s" % ", ".join(r["missing"])
    off = {c: v for c, v in r["conditions"].items() if not v["accepted"]}
    assert not off, "; ".join("%s output %+.2f %%, heat rate %+.2f %%" % (c, 100 * v["output_miss"], 100 * v["heat_rate_miss"])
                              for c, v in sorted(off.items()))
