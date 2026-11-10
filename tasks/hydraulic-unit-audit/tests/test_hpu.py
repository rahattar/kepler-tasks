"""Pytest entry for hydraulic-unit-audit. A single test decides the reward: the submitted program /app/output/hpu.py,
run on each of the eight hidden press packages, gives every result within its tolerance on at least
seven of them. Per-press results are written to /logs/verifier/metrics.json for the record only.
"""
import json
import os

import grade_hpu

PROGRAM = os.environ.get("HPU_PROGRAM", "/app/output/hpu.py")


def run():
    if os.path.islink(PROGRAM) or not os.path.isfile(PROGRAM):
        r = {"accepted": False, "cases": {}, "error": "no program (a regular file, not a symlink) at %s" % PROGRAM}
    else:
        r = grade_hpu.score(PROGRAM, as_nobody=os.geteuid() == 0)
    try:
        os.makedirs("/logs/verifier", exist_ok=True)
        with open("/logs/verifier/metrics.json", "w") as f:
            json.dump(dict(r, max_wrong=grade_hpu.MAX_WRONG), f, indent=1)
    except OSError:
        pass
    return r


def test_program_on_hidden_presses():
    r = run()
    assert "error" not in r, r.get("error")
    assert r["accepted"], "%d of %d hidden presses wrong (at most %d allowed)" % (
        r["wrong"], len(r["cases"]), grade_hpu.MAX_WRONG)
