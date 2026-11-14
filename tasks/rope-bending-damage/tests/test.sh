#!/bin/bash
# Writes the reward for the ropes.py at /app/output: the single character 0 or 1 in /logs/verifier/reward.txt.
#
# 0 is written before anything else happens. It becomes 1 only if three things are all true afterwards:
#   a) there is a file /app/output/ropes.py;
#   b) pytest, with the one test of test_ropes.py, came back with status 0. That test has rope_bench.py run
#      the program on each of the six works, every run inside the time limit; one run over the limit, one
#      wrong row or one unreadable sheet fails it;
#   c) the report pytest wrote says one test was run and that one passed (tally.py). A report that is missing,
#      broken or counts anything else leaves the 0.
# Nothing that the program writes while it runs can reach the reward: it runs as nobody, and the folder the
# reward is in is root's and closed.
umask 077
mkdir -p /logs/verifier
echo -n "0" > /logs/verifier/reward.txt

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
report=/logs/verifier/ctrf.json
rm -f "$report" /logs/verifier/trials.json

verdict=0
if [ ! -f /app/output/ropes.py ]; then
    echo "test.sh: no /app/output/ropes.py" >&2
elif ! (cd "$here" && python -m pytest test_ropes.py -p no:cacheprovider -q --ctrf=/logs/verifier/ctrf.json); then
    echo "test.sh: pytest did not end with status 0" >&2
elif ! python "$here/tally.py" "$report"; then
    echo "test.sh: the report is not one test, passed" >&2
else
    verdict=1
fi

chown root:root /logs/verifier
chmod 0700 /logs/verifier
rm -f /logs/verifier/reward.txt
if [ "$verdict" -eq 1 ]; then
echo -n "1" > /logs/verifier/reward.txt
fi
if [ "$verdict" -ne 1 ]; then
echo -n "0" > /logs/verifier/reward.txt
fi
echo "test.sh: reward $verdict" >&2
exit 0
