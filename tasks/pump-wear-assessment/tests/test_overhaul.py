"""Pytest entry for pump-wear-assessment. A single test decides the reward: every pump's deficit in
/app/output/overhaul.json within 0.3 m of the sealed bank. The per-pump misses are written to
/logs/verifier/metrics.json for the record only. Nothing from the solution or the shipped data is read.
"""
import json
import os

import grade_pumps

PATH = os.environ.get("OVERHAUL_PATH", "/app/output/overhaul.json")


def run():
    try:
        r = grade_pumps.score(PATH)
    except Exception as e:                           # absent, not JSON, wrong keys or values
        r = {"accepted": False, "pumps": {}, "missing": [], "error": repr(e)}
    try:
        os.makedirs("/logs/verifier", exist_ok=True)
        with open("/logs/verifier/metrics.json", "w") as f:
            json.dump(dict(r, limit_m=grade_pumps.LIMIT), f, indent=1)
    except OSError:
        pass
    return r


def test_all_ten_pumps_within_limit():
    r = run()
    assert "error" not in r, r.get("error")
    assert not r["missing"], "missing pumps: %s" % ", ".join(r["missing"])
    off = {p: v for p, v in r["pumps"].items() if not v["accepted"]}
    assert not off, "; ".join("%s off by %+.3f m" % (p, v["miss_m"]) for p, v in sorted(off.items()))
