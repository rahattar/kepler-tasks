"""AP-12 section 7 put to the sheet that was handed in.

There is one test. It asks the grader which trains the submitted moves leave in line at their running
condition, keeps the grader's train-by-train findings beside the pytest report for whoever opens the run
afterwards, and stands only if no train is left out of line. The findings file is a convenience: it is never
read back, and being unable to write it changes nothing.
"""
import json
import os
from pathlib import Path

import grade_moves

FINDINGS = Path("/logs/verifier/alignment.json")


def sheet_path():
    return os.environ.get("MOVES_FILE") or "/app/output/moves.csv"


def test_all_trains_left_aligned():
    outcome = grade_moves.assess(sheet_path())
    try:
        FINDINGS.parent.mkdir(parents=True, exist_ok=True)
        FINDINGS.write_text(json.dumps(vars(outcome), indent=1))
    except OSError:
        pass
    if not outcome.accepted:
        raise AssertionError(grade_moves.explain(outcome))
