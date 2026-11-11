#!/bin/bash
# Two independent facts decide the reward: the status pytest exits with, and the counts in the report it
# writes. Both are read after grading has finished, so nothing produced while grading ran can stand in for
# either. Any other outcome - a crash, a timeout, a report that never appears - leaves the reward at zero.
set -u

lock_logs() {                  # /logs/verifier belongs to root alone, before grading and again afterwards
    mkdir -p /logs/verifier
    chown root:root /logs/verifier 2>/dev/null
    chmod 700 /logs/verifier 2>/dev/null
}

# Zero goes down before anything else happens. If this script dies anywhere below, the file is already there
# and already says zero, rather than being absent or holding whatever another process left.
lock_logs
rm -f /logs/verifier/reward.txt
echo -n "0" > /logs/verifier/reward.txt

cd "$(dirname "${BASH_SOURCE[0]}")" || exit 0
python -m pytest test_flare.py -p no:cacheprovider --ctrf=/logs/verifier/ctrf.json -v
exit_status=$?

# The report has to describe the one test this verifier has: one test, that test passed, and nothing failed,
# skipped, pending or otherwise accounted for. A report describing anything else is not this run's.
python - /logs/verifier/ctrf.json <<'COUNTS'
import json
import sys

try:
    summary = json.load(open(sys.argv[1]))["results"]["summary"]
except Exception:
    raise SystemExit(1)
wanted = {"tests": 1, "passed": 1, "failed": 0, "skipped": 0, "pending": 0, "other": 0}
raise SystemExit(0 if all(summary.get(key, 0) == value for key, value in wanted.items()) else 1)
COUNTS
report_status=$?

# The directory is closed again before the reward is settled, and the earlier file is removed rather than
# overwritten, so the byte left behind cannot be something grading wrote.
lock_logs
rm -f /logs/verifier/reward.txt
if [ "$exit_status" -eq 0 ] && [ "$report_status" -eq 0 ]; then
    echo -n "1" > /logs/verifier/reward.txt
else
    echo -n "0" > /logs/verifier/reward.txt
fi
exit 0
