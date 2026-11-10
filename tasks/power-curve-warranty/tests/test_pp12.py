"""Pytest entry for power-curve-warranty. A single test decides the reward: the submitted program /app/output/pp12.py,
run on each of the six hidden farm-period packages, gives every turbine's claim and annual energy ratio, with at most
one turbine wrong over all of them. Per-package results are written to /logs/verifier/metrics.json for the record
only.
"""
import json
import os

import grade

PROGRAM = os.environ.get("PP12_PROGRAM", "/app/output/pp12.py")


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


def test_program_on_hidden_packages():
    r = run()
    assert "error" not in r, r.get("error")
    assert r["accepted"], "%d of %d hidden turbines wrong (at most %d allowed)" % (
        r["wrong"], r["turbines"], grade.MAX_WRONG)
