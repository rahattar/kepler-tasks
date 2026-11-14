"""The verifier's one test.

rope_bench.judge runs the delivered ropes.py on the six works and decides; this file asks it, keeps its notes
for whoever reads the logs (/logs/verifier/trials.json, which nothing reads back) and fails with the bench's
own account when the program is not accepted. ROPES_PROGRAM and ROPES_NOTES move the two paths for the studies
under authoring/evidence; the verifier sets neither.
"""
import json
import os

import rope_bench


def test_ropes_py_is_accepted_on_all_six_works():
    program = os.environ.get("ROPES_PROGRAM", "/app/output/ropes.py")
    verdict = rope_bench.judge(program)
    notes = os.environ.get("ROPES_NOTES", "/logs/verifier/trials.json")
    try:
        with open(notes, "w") as handle:
            json.dump(verdict, handle, indent=1, sort_keys=True)
    except OSError:
        pass
    if not verdict["accepted"]:
        raise AssertionError("ropes.py is not accepted\n" + rope_bench.account(verdict))
