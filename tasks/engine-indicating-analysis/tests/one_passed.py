"""Says whether a ctrf report is the report of exactly one test, and that test passed.

    python3 one_passed.py /logs/verifier/ctrf.json      exit status 0 when it is, 1 when it is not

test.sh asks this after pytest has ended, and gives the reward only when pytest and this agree. A missing
file, a file that is not such a report, and any other count of tests all come out as 1.
"""
import json
import sys


def exactly_one_passed(path):
    try:
        with open(path) as handle:
            summary = json.load(handle)["results"]["summary"]
        counts = {key: int(summary.get(key, 0)) for key in ("tests", "passed", "failed", "skipped", "pending", "other")}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return False
    return counts == {"tests": 1, "passed": 1, "failed": 0, "skipped": 0, "pending": 0, "other": 0}


if __name__ == "__main__":
    sys.exit(0 if len(sys.argv) == 2 and exactly_one_passed(sys.argv[1]) else 1)
