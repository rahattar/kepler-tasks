#!/bin/bash
# The reward is settled after grading, from pytest's own exit status together with the counts in its report, so
# that nothing written while grading ran can stand in for it. A crash, a timeout or a missing report all leave 0.
set -u

LOGS=/logs/verifier
CTRF=$LOGS/ctrf.json
PRIZE=$LOGS/reward.txt

seal() {                       # the log directory is root's alone, before grading and again after it
    mkdir -p "$LOGS"
    chown root:root "$LOGS" 2>/dev/null
    chmod 700 "$LOGS" 2>/dev/null
}

seal
rm -f "$PRIZE"
printf '0' > "$PRIZE"

cd "$(dirname "${BASH_SOURCE[0]}")" || exit 0
python -m pytest test_relief.py -p no:cacheprovider --ctrf="$CTRF" -v
graded=$?

# The run counts only if the report holds the one test that was expected and that test passed: one test, one
# passed, and nothing failed, skipped, pending or otherwise accounted for.
python - "$CTRF" <<'TALLY'
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

seal
rm -f "$PRIZE"
if [ "$graded" -eq 0 ] && [ "$counted" -eq 0 ]; then
    printf '1' > "$PRIZE"
else
    printf '0' > "$PRIZE"
fi
exit 0
