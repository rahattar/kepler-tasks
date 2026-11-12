"""Says whether a ctrf report describes this verifier's one test, and that test passing.

    python count_report.py /logs/verifier/ctrf.json

Exit status 0 when the report's summary counts exactly one test, that test passed, and nothing is counted as
failed, skipped, pending or other. Any other summary, a report that cannot be read, or no report at all gives
exit status 1. test.sh asks this after pytest has finished, and needs both answers to be good.
"""
import json
import sys


def describes_one_pass(path):
    try:
        with open(path) as handle:
            summary = json.load(handle)["results"]["summary"]
        elsewhere = sum(int(summary.get(column, 0)) for column in ("failed", "skipped", "pending", "other"))
        return summary["tests"] == 1 and summary["passed"] == 1 and elsewhere == 0
    except (OSError, ValueError, KeyError, TypeError):
        return False


if __name__ == "__main__":
    sys.exit(0 if len(sys.argv) == 2 and describes_one_pass(sys.argv[1]) else 1)
