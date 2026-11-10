"""Pytest entry for superheater-tube-life. A single test decides the reward: every element's consumed creep life
fraction in /app/output/creep_life.csv within 25 % of the sealed value. The per-element misses are written to
/logs/verifier/metrics.json for the record only. Nothing from the solution or the shipped data is read.
"""
import json
import os

import grade_tubes

PATH = os.environ.get("CREEP_LIFE_PATH", "/app/output/creep_life.csv")


def run():
    try:
        r = grade_tubes.score(PATH)
    except Exception as e:                           # absent, not CSV, wrong columns or values
        r = {"accepted": False, "elements": {}, "missing": [], "error": repr(e)}
    try:
        os.makedirs("/logs/verifier", exist_ok=True)
        with open("/logs/verifier/metrics.json", "w") as f:
            json.dump(dict(r, limit_relative=grade_tubes.LIMIT), f, indent=1)
    except OSError:
        pass
    return r


def test_all_ten_elements_within_limit():
    r = run()
    assert "error" not in r, r.get("error")
    assert not r["missing"], "missing elements: %s" % ", ".join(r["missing"])
    off = {e: v for e, v in r["elements"].items() if not v["accepted"]}
    assert not off, "; ".join("%s off by %+.1f %%" % (e, 100 * v["relative_miss"]) for e, v in sorted(off.items()))
