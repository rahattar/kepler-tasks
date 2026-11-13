"""Was the pytest run a run of exactly one test, and did it pass?

    python3 one_passed.py /logs/verifier/ctrf.json      exits 0 for yes and 1 for no

No is also the answer for a missing file, a file that is not a ctrf report, and any other tally. test.sh asks
this after pytest has ended and gives the reward only when both agree.
"""
import json
import sys


def counts(path):
    with open(path) as handle:
        return json.load(handle)["results"]["summary"]


def yes(summary):
    wanted = dict(tests=1, passed=1, failed=0, skipped=0, pending=0, other=0)
    return all(int(summary.get(kind, 0)) == number for kind, number in wanted.items())


if __name__ == "__main__":
    try:
        sys.exit(0 if len(sys.argv) == 2 and yes(counts(sys.argv[1])) else 1)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        sys.exit(1)
