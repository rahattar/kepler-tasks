"""pytest's view of the assessment: one test, which holds when grade_program accepts the submitted program.

grade_program.assess does the work (six sites, each run under the limit, every point against its band). Its
findings for each site are also left in /logs/verifier/sites.json for a person reading the run; nothing reads
that file back.
"""
import json
import os

import grade_program

PROGRAM = os.environ.get("BEARING_PROGRAM") or "/app/output/bearing.py"
FINDINGS = "/logs/verifier/sites.json"


def keep(outcome):
    try:
        os.makedirs(os.path.dirname(FINDINGS), exist_ok=True)
        with open(FINDINGS, "w") as handle:
            json.dump({"accepted": outcome.accepted, "stopped": outcome.stopped, "sites": outcome.sites}, handle, indent=1)
    except OSError:
        pass


def test_bearing_program_on_the_six_sites():
    outcome = grade_program.assess(PROGRAM)
    keep(outcome)
    if not outcome.accepted:
        raise AssertionError(grade_program.explain(outcome))
