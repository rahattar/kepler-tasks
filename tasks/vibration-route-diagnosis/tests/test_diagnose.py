"""Pytest entry for vibration-route-diagnosis. A single test decides the reward: the submitted program
/app/output/diagnose.py, run on each of the six hidden route packages, diagnoses at least 58 of their 60 machines
correctly (condition code and component). Per-route results are written to /logs/verifier/metrics.json for the
record only. The reference solution is not used.
"""
import json
import os

import grade_routes

PROGRAM = os.environ.get("DIAGNOSE_PROGRAM", "/app/output/diagnose.py")


def run():
    if not os.path.isfile(PROGRAM):
        r = {"accepted": False, "routes": {}, "error": "no program at %s" % PROGRAM}
    else:
        r = grade_routes.score(PROGRAM, as_nobody=os.geteuid() == 0)
    try:
        os.makedirs("/logs/verifier", exist_ok=True)
        with open("/logs/verifier/metrics.json", "w") as f:
            json.dump(dict(r, max_wrong=grade_routes.MAX_WRONG), f, indent=1)
    except OSError:
        pass
    return r


def test_program_on_hidden_routes():
    r = run()
    assert "error" not in r, r.get("error")
    assert r["accepted"], "%d of %d hidden machines misdiagnosed (at most %d allowed)" % (
        r["wrong"], r["machines"], grade_routes.MAX_WRONG)
