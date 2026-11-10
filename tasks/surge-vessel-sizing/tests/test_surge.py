"""Pytest entry for surge-vessel-sizing. A single test decides the reward: the submitted program /app/output/surge.py,
run on each of the six hidden mains, gives a design that meets MS-SV on the main as installed within the size limit,
with at most one main wrong. Per-main results are written to /logs/verifier/metrics.json for the record only.
"""
import json
import os

import grade

PROGRAM = os.environ.get("SURGE_PROGRAM", "/app/output/surge.py")


def run():
    if os.path.islink(PROGRAM) or not os.path.isfile(PROGRAM):
        r = {"accepted": False, "packages": {}, "error": "no program (a regular file, not a symlink) at %s" % PROGRAM}
    else:
        r = grade.score(PROGRAM, as_nobody=os.geteuid() == 0)
    try:
        os.makedirs("/logs/verifier", exist_ok=True)
        with open("/logs/verifier/metrics.json", "w") as f:
            json.dump(dict(r, max_wrong=grade.MAX_WRONG), f, indent=1)
    except OSError:
        pass
    return r


def test_program_on_hidden_mains():
    r = run()
    assert "error" not in r, r.get("error")
    assert r["accepted"], "%d of %d hidden mains wrong (at most %d allowed)" % (
        r["wrong"], r["mains"], grade.MAX_WRONG)
