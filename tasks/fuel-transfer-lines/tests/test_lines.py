"""The verifier's one test: the delivered lines.py, run on the six sites of tests/sites by rerun.py."""
import json
import os

import rerun

DELIVERED = "/app/output/lines.py"
NOTES = "/logs/verifier/sites.json"


def test_lines_on_the_six_sites():
    verdict = rerun.judge(DELIVERED)
    words = rerun.account(verdict)
    print(words)
    if os.path.isdir(os.path.dirname(NOTES)):
        with open(NOTES, "w") as handle:
            json.dump(verdict, handle, indent=1)
    assert verdict["accepted"], "\n" + words
