"""Pytest entry for milling-chatter-limit. A single test decides the reward: the submitted program
/app/output/chatter.py, run on each of the seven hidden jobs, gives the job's stability limit within the tolerance,
with at most one job wrong. Per-job results are written to /logs/verifier/metrics.json for the record only.
"""
import json
import os

import grade

PROGRAM = os.environ.get("CHATTER_PROGRAM", "/app/output/chatter.py")


def run():
    if os.path.islink(PROGRAM) or not os.path.isfile(PROGRAM):
        r = {"accepted": False, "packages": {}, "error": "no program (a regular file, not a symlink) at %s" % PROGRAM}
    else:
        r = grade.score(PROGRAM, as_nobody=os.geteuid() == 0)
    try:
        os.makedirs("/logs/verifier", exist_ok=True)
        with open("/logs/verifier/metrics.json", "w") as f:
            json.dump(dict(r, max_wrong=grade.MAX_WRONG, tolerance=grade.TOL), f, indent=1)
    except OSError:
        pass
    return r


def test_program_on_hidden_jobs():
    r = run()
    assert "error" not in r, r.get("error")
    assert r["accepted"], "%d of %d hidden jobs wrong (at most %d allowed)" % (r["wrong"], r["jobs"], grade.MAX_WRONG)
