"""Pytest entry for air-system-audit. A single test decides the reward: the submitted program /app/output/audit.py,
run on each of the eight hidden compressed air audit packages, gives every result within its tolerance on at least
seven of them. Per-site results are written to /logs/verifier/metrics.json for the record only.
"""
import json
import os

import grade_audits

PROGRAM = os.environ.get("AUDIT_PROGRAM", "/app/output/audit.py")


def run():
    if os.path.islink(PROGRAM) or not os.path.isfile(PROGRAM):
        r = {"accepted": False, "cases": {}, "error": "no program (a regular file, not a symlink) at %s" % PROGRAM}
    else:
        r = grade_audits.score(PROGRAM, as_nobody=os.geteuid() == 0)
    try:
        os.makedirs("/logs/verifier", exist_ok=True)
        with open("/logs/verifier/metrics.json", "w") as f:
            json.dump(dict(r, max_wrong=grade_audits.MAX_WRONG), f, indent=1)
    except OSError:
        pass
    return r


def test_program_on_hidden_audits():
    r = run()
    assert "error" not in r, r.get("error")
    assert r["accepted"], "%d of %d hidden sites wrong (at most %d allowed)" % (
        r["wrong"], len(r["cases"]), grade_audits.MAX_WRONG)
