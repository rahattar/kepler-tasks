"""Reads the report pytest left and answers one question: was exactly one test run, and did it pass?

    python tally.py /logs/verifier/ctrf.json        exit status 0 for yes, 3 for anything else

test.sh gives the reward only on a yes. "Anything else" includes no file, a file that is not JSON, a report
without a summary, more or fewer tests than one, and a test that failed, was skipped or is pending.
"""
import json
import sys

ONE_PASSED = {"tests": 1, "passed": 1, "failed": 0, "skipped": 0, "pending": 0, "other": 0}


def summary_of(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)["results"]["summary"]


def one_test_passed(path):
    try:
        summary = summary_of(path)
        return all(int(summary.get(key, 0)) == count for key, count in ONE_PASSED.items())
    except Exception:
        return False


if __name__ == "__main__":
    raise SystemExit(0 if len(sys.argv) == 2 and one_test_passed(sys.argv[1]) else 3)
