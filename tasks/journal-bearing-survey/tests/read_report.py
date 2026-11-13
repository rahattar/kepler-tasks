"""The second opinion on a pytest run: is the report it left a report of one test that passed?

    python3 read_report.py /logs/verifier/ctrf.json        exit status 0 for yes, 1 for anything else

"Anything else" covers a report with a different tally, a file that is not a ctrf report, and no file. The
reward script runs this after pytest and needs both to say yes.
"""
import json
import sys

ONE_PASS = {"tests": 1, "passed": 1, "failed": 0, "skipped": 0, "pending": 0, "other": 0}


def tally(path):
    """The summary block of a ctrf report, as a dictionary of counts."""
    with open(path) as handle:
        report = json.load(handle)
    return report["results"]["summary"]


def main(arguments):
    if len(arguments) != 1:
        return 1
    try:
        found = tally(arguments[0])
        return 0 if all(int(found.get(kind, 0)) == count for kind, count in ONE_PASS.items()) else 1
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
