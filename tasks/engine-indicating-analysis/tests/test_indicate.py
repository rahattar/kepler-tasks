"""The one pytest test: the submitted indicate.py is accepted by check_program on every cell.

check_program does the running and the comparing. What it found for each cell is also written, for a person
reading the logs afterwards, to /logs/verifier/cells.json; nothing reads that file back.
"""
import json
import os

import check_program

SUBMITTED = os.environ.get("INDICATE_PROGRAM", "/app/output/indicate.py")
NOTES = os.environ.get("INDICATE_NOTES", "/logs/verifier/cells.json")


def test_indicate_program_is_accepted_on_every_cell():
    report = check_program.assess(SUBMITTED)
    try:
        with open(NOTES, "w") as handle:
            json.dump(report, handle, indent=1)
    except OSError:
        pass
    assert report["accepted"], "\n" + check_program.account(report)
