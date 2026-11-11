"""The single test the reward hangs on: unit 400's flare load study, as submitted, stands against the sealed
definition in every one of its rows.

The per-contingency detail the grader produced is dropped into /logs/verifier/metrics.json on the way past, for
whoever reads the run afterwards. Nothing reads it back, and failing to write it changes nothing.
"""
import json
import os

import grade_flare

STUDY = os.environ.get("SHEET_FILE", "/app/output/flare_load.csv")
DETAIL = "/logs/verifier/metrics.json"


def keep(report):
    try:
        os.makedirs(os.path.dirname(DETAIL), exist_ok=True)
        with open(DETAIL, "w") as handle:
            json.dump({"taken": report.taken, "standing": report.standing, "total": report.total,
                       "fault": None if report.fault is None else report.fault._asdict(),
                       "contingencies": report.rows}, handle, indent=1)
    except OSError:
        pass


def test_every_contingency_row_stands():
    report = grade_flare.assess(STUDY)
    keep(report)
    assert report.taken, grade_flare.explain(report)
