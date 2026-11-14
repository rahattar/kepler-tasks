#!/bin/bash
# Decides what a delivered /app/output/lines.py is worth and writes it to /logs/verifier/reward.txt.
#
# The file reads 0 from the first line on. It becomes 1 at the very end, and only if all three hold:
#   - /app/output/lines.py is there;
#   - pytest ran test_lines.py and exited with status 0, which is rerun.py finding every one of the six
#     runs inside the limit and every value in band;
#   - the report pytest left counts one test, and that one passed (tally.py).
# Nothing here can turn a 0 into a 1 except that last step, and any step that cannot be carried out leaves
# the 0 where it is.
set -u
umask 077
mkdir -p /logs/verifier
echo -n "0" > /logs/verifier/reward.txt

say() { echo "test.sh: $*" >&2; }
where="$(cd "$(dirname "$0")" && pwd)"
rm -f /logs/verifier/ctrf.json /logs/verifier/sites.json
steps=0

if [ -f /app/output/lines.py ]; then
    steps=$((steps + 1))
else
    say "no /app/output/lines.py was delivered"
fi

if [ "$steps" -eq 1 ] && cd "$where"; then
    say "running lines.py on the six sites"
    if python -m pytest test_lines.py -q -p no:cacheprovider --ctrf=/logs/verifier/ctrf.json; then
        steps=$((steps + 1))
    else
        say "pytest did not exit with status 0"
    fi
fi

if [ "$steps" -eq 2 ]; then
    if python "$where/tally.py" /logs/verifier/ctrf.json; then
        steps=$((steps + 1))
    else
        say "the report is not one test, passed"
    fi
fi

say "steps taken: $steps of 3"
if [ "$steps" -eq 3 ]; then
echo -n "1" > /logs/verifier/reward.txt
fi
exit 0
