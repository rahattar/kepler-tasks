#!/bin/bash
# The reward is written at the end, from pytest's exit status and the test counts in the ctrf report, so it cannot be
# left at a value anything else wrote while grading ran. A crash, a timeout or a missing program all leave 0.
set -u

mkdir -p /logs/verifier
chown root:root /logs/verifier 2>/dev/null
chmod 700 /logs/verifier
rm -f /logs/verifier/reward.txt
echo -n "0" > /logs/verifier/reward.txt

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE" || exit 0

python -m pytest test_burn.py \
    -p no:cacheprovider \
    --ctrf=/logs/verifier/ctrf.json \
    -v
RC=$?

# The run counts only if the report holds exactly the one expected test, passed: 1 test, 1 passed, none failed,
# skipped, pending or other.
COUNTS_OK=$(python - <<'PY' 2>/dev/null
import json
try:
    s = json.load(open("/logs/verifier/ctrf.json"))["results"]["summary"]
    ok = s.get("tests") == 1 and s.get("passed") == 1 and all(
        s.get(k, 0) == 0 for k in ("failed", "skipped", "pending", "other"))
except Exception:
    ok = False
print("yes" if ok else "no")
PY
)

# the program's processes are gone (grade.py kills them after each run); lock the directory down again before
# the reward is written
chown root:root /logs/verifier 2>/dev/null
chmod 700 /logs/verifier
rm -f /logs/verifier/reward.txt

if [ "$RC" -eq 0 ] && [ "$COUNTS_OK" = "yes" ]; then
    echo -n "1" > /logs/verifier/reward.txt
else
    echo -n "0" > /logs/verifier/reward.txt
fi

exit 0
