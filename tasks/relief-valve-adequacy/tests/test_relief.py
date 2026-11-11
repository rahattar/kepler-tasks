"""The verifier's one test. It carries the reward: unit 400's relief assessment, as submitted, has every valve's
finding standing against the sealed definition. The per-valve detail is written to /logs/verifier/metrics.json for
the record; nothing reads it back.
"""
import json
import os

from grade_relief import assess, explain

SHEET = os.environ.get("SHEET_FILE", "/app/output/relief.csv")
METRICS = "/logs/verifier/metrics.json"


def _record(report):
    try:
        os.makedirs(os.path.dirname(METRICS), exist_ok=True)
        with open(METRICS, "w") as handle:
            json.dump({"taken": report.taken, "standing": report.standing, "total": report.total,
                       "fault": None if report.fault is None else report.fault._asdict(),
                       "valves": report.findings}, handle, indent=1)
    except OSError:
        pass


def test_every_valve_finding_stands():
    report = assess(SHEET)
    _record(report)
    assert report.taken, explain(report)
