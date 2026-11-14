"""tally.py REPORT: exit status 0 if the ctrf report at REPORT counts exactly one test and that test passed.

What is read is the report's summary: tests 1, passed 1, and none failed, skipped, pending or other. Where the
report also lists its tests, the list has to hold that one test and no other.
"""
import json
import sys


def one_passed(path):
    try:
        with open(path) as handle:
            results = json.load(handle)["results"]
        summary = results["summary"]
        counts = [summary.get(key, 0) for key in ("tests", "passed", "failed", "skipped", "pending", "other")]
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return False
    listed = results.get("tests")
    if listed is not None and not (isinstance(listed, list) and len(listed) == 1):
        return False
    return counts == [1, 1, 0, 0, 0, 0]


if __name__ == "__main__":
    sys.exit(0 if len(sys.argv) == 2 and one_passed(sys.argv[1]) else 1)
