"""Pytest entry for superheater-creep-life. A single test decides the reward: every element's consumed creep life fraction
/app/output/damage.json within 25 % of the sealed value. The per-element misses are written to
/logs/verifier/metrics.json for the record only. Nothing from the solution, the inspection results or the shipped data is read.
"""
import json
import os

import grade_superheater

PATH = os.environ.get("DAMAGE_PATH", "/app/output/damage.json")


def run():
    try:
        r = grade_superheater.score(PATH)
    except Exception as e:                           # absent, not JSON, wrong keys or values
        r = {"accepted": False, "elements": {}, "missing": [], "error": repr(e)}
    try:
        os.makedirs("/logs/verifier", exist_ok=True)
        with open("/logs/verifier/metrics.json", "w") as f:
            json.dump(dict(r, limit_relative=grade_superheater.LIMIT), f, indent=1)
    except OSError:
        pass
    return r


def test_all_ten_elements_within_limit():
    r = run()
    assert "error" not in r, r.get("error")
    assert not r["missing"], "missing elements: %s" % ", ".join(r["missing"])
    off = {u: v for u, v in r["elements"].items() if not v["accepted"]}
    assert not off, "; ".join("%s off by %+.1f %%" % (u, 100 * v["relative_miss"]) for u, v in sorted(off.items()))
