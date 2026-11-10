"""Pytest entry for turbine-tool-repair. A single test decides the reward: the submitted program
/app/output/gtperf.py, run on each of the eight hidden GT-1 test record sets, gives the corrected output and corrected
heat rate within 0.3 % of the sealed values on every set. Per-set results are written to /logs/verifier/metrics.json
for the record only. The reference solution and the agent's environment are not used.
"""
import json
import os

import grade_tool

PROGRAM = os.environ.get("GTPERF_PROGRAM", "/app/output/gtperf.py")


def run():
    if not os.path.isfile(PROGRAM):
        r = {"accepted": False, "sets": {}, "error": "no program at %s" % PROGRAM}
    else:
        r = grade_tool.score(PROGRAM, as_nobody=os.geteuid() == 0)
    try:
        os.makedirs("/logs/verifier", exist_ok=True)
        with open("/logs/verifier/metrics.json", "w") as f:
            json.dump(dict(r, limit_relative=grade_tool.LIMIT), f, indent=1)
    except OSError:
        pass
    return r


def test_program_on_hidden_record_sets():
    r = run()
    assert "error" not in r, r.get("error")
    bad = {k: v for k, v in r["sets"].items() if not v["accepted"]}
    assert not bad, "; ".join("%s: %s" % (k, v.get("error") or "output %+.2f %%, heat rate %+.2f %%"
                                                % (100 * v["output_miss"], 100 * v["heat_rate_miss"])) for k, v in sorted(bad.items()))
