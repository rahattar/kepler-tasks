"""Pytest entry for screen-fatigue-assessment. A single test decides the reward: every screen's Miner sum in
/app/output/damage.json within 20 % of the sealed value. The per-screen misses are written to
/logs/verifier/metrics.json for the record only. Nothing from the solution, the field work or the shipped data is read.
"""
import json
import os

import grade_screens

PATH = os.environ.get("DAMAGE_PATH", "/app/output/damage.json")


def run():
    try:
        r = grade_screens.score(PATH)
    except Exception as e:                           # absent, not JSON, wrong keys or values
        r = {"accepted": False, "screens": {}, "missing": [], "error": repr(e)}
    try:
        os.makedirs("/logs/verifier", exist_ok=True)
        with open("/logs/verifier/metrics.json", "w") as f:
            json.dump(dict(r, limit_relative=grade_screens.LIMIT), f, indent=1)
    except OSError:
        pass
    return r


def test_all_ten_screens_within_limit():
    r = run()
    assert "error" not in r, r.get("error")
    assert not r["missing"], "missing screens: %s" % ", ".join(r["missing"])
    off = {u: v for u, v in r["screens"].items() if not v["accepted"]}
    assert not off, "; ".join("%s off by %+.1f %%" % (u, 100 * v["relative_miss"]) for u, v in sorted(off.items()))
