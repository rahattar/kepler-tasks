#!/bin/bash
# The reward is settled after grading, from pytest's own exit status together with the counts in its report, so
# that nothing written while grading ran can stand in for it. A crash, a timeout or a missing report all leave 0.
set -u

seal() {                       # the log directory is root's alone, before grading and again after it
    mkdir -p /logs/verifier
    chown root:root /logs/verifier 2>/dev/null
    chmod 700 /logs/verifier 2>/dev/null
}

# A zero goes down before anything else runs, so that a crash between here and the end cannot leave the file
# absent or holding something another process wrote.
seal
rm -f /logs/verifier/reward.txt
echo -n "0" > /logs/verifier/reward.txt

cd "$(dirname "${BASH_SOURCE[0]}")" || exit 0
python -m pytest test_relief.py -p no:cacheprovider --ctrf=/logs/verifier/ctrf.json -v
graded=$?

# The run counts only if the report holds the one test that was expected and that test passed: one test, one
# passed, and nothing failed, skipped, pending or otherwise accounted for.
python - /logs/verifier/ctrf.json <<'TALLY'
import json
import sys

try:
    summary = json.load(open(sys.argv[1]))["results"]["summary"]
except Exception:
    raise SystemExit(1)
expected = {"tests": 1, "passed": 1, "failed": 0, "skipped": 0, "pending": 0, "other": 0}
raise SystemExit(0 if all(summary.get(k, 0) == v for k, v in expected.items()) else 1)
TALLY
counted=$?

# The directory is locked again before the reward is written, and the old file removed rather than overwritten,
# so the final byte cannot be something grading left behind.
seal
rm -f /logs/verifier/reward.txt
if [ "$graded" -eq 0 ] && [ "$counted" -eq 0 ]; then
    echo -n "1" > /logs/verifier/reward.txt
else
    echo -n "0" > /logs/verifier/reward.txt
fi
exit 0
