#!/bin/bash
# The reward for a delivered airflow.py: one character in /logs/verifier/reward.txt.
#
#   1   every one of the six runs ended inside its limit and every airflow is in band
#   0   anything else, including not being able to tell
#
# The file says 0 from the first moment and for as long as the program is running. It is written again at
# the end, after the directory has been taken back from whatever the program's user may have done to it.
# `granted` can only go from yes to no: no airflow.py, no tests directory, pytest not ending with status 0,
# or a report that is not one test, passed.
set -u
umask 077

note() { printf 'test.sh: %s\n' "$*" >&2; }

mkdir -p /logs/verifier
chmod 700 /logs/verifier
echo -n "0" > /logs/verifier/reward.txt
rm -f /logs/verifier/ctrf.json

granted=yes
[ -f /app/output/airflow.py ] || { note "there is no /app/output/airflow.py"; granted=no; }
cd "$(dirname "$0")" || { note "cannot enter the tests directory"; granted=no; }

if [ "$granted" = yes ]; then
    note "airflow.py on the six districts"
    python -m pytest test_airflow.py -q -p no:cacheprovider --ctrf=/logs/verifier/ctrf.json || granted=no
    python one_passed.py /logs/verifier/ctrf.json || granted=no
fi
note "granted: $granted"

chown 0:0 /logs/verifier
chmod 700 /logs/verifier
rm -f /logs/verifier/reward.txt
if [ "$granted" = yes ]; then
echo -n "1" > /logs/verifier/reward.txt
else
echo -n "0" > /logs/verifier/reward.txt
fi
exit 0
