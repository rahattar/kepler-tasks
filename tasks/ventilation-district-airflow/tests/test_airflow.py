"""The one test: the delivered airflow.py is accepted by the checker on the six districts.

judge_airflow.judge runs the program and compares; what it found at each district is left in
/logs/verifier/districts.json for a person to read. Nothing reads that file back.
"""
import json
import os

import judge_airflow

DELIVERED = os.environ.get("AIRFLOW_PROGRAM") or "/app/output/airflow.py"
NOTES = "/logs/verifier/districts.json"


def test_airflow_on_the_six_districts():
    verdict = judge_airflow.judge(DELIVERED)
    try:
        os.makedirs(os.path.dirname(NOTES), exist_ok=True)
        with open(NOTES, "w") as handle:
            json.dump(verdict, handle, indent=1)
    except OSError:
        pass
    assert verdict["accepted"], judge_airflow.account(verdict)
