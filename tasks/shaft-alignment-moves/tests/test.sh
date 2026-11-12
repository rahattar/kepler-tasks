#!/bin/bash
# Leaves one character in /logs/verifier/reward.txt.
#
#   1  the moves handed in leave every train of Unit 3 in line, running
#   0  anything else, including a run in which nothing could be judged
#
# Order of events: write 0; clear out any report from before; run the one pytest test; ask count_report.py
# whether the report pytest wrote is a report of one test passing; write 1 if pytest and the report agree
# that it did.
set -u
umask 077
tests_dir="$(cd "$(dirname "$0")" && pwd)"

close_logs() {
    mkdir -p /logs/verifier
    chown 0:0 /logs/verifier 2>/dev/null
    chmod u=rwx,go= /logs/verifier 2>/dev/null
}

close_logs
echo -n "0" > /logs/verifier/reward.txt
rm -f /logs/verifier/ctrf.json

cd "$tests_dir" || exit 0
python -m pytest test_moves.py -q -p no:cacheprovider --ctrf=/logs/verifier/ctrf.json
graded=$?
python count_report.py /logs/verifier/ctrf.json
counted=$?

# Nothing written while the test ran decides the outcome. The directory is closed again, the 0 from the top is
# taken away, and the final character is written from the two exit statuses alone.
close_logs
rm -f /logs/verifier/reward.txt
case "$graded:$counted" in
    0:0) echo -n "1" > /logs/verifier/reward.txt ;;
    *)   echo -n "0" > /logs/verifier/reward.txt ;;
esac
exit 0
