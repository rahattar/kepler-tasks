#!/bin/bash
# The reward is written from pytest's exit status at the end, in both branches, so it
# cannot be left at a value anything else wrote while grading ran. A crash, a timeout or
# a missing supervisor all leave 0.
set -u

mkdir -p /logs/verifier
chmod 700 /logs/verifier          # root only: the supervisor runs as nobody and must not see the reward
echo -n "0" > /logs/verifier/reward.txt

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE" || exit 0

python -m pytest test_supervisor.py \
    -p no:cacheprovider \
    --ctrf=/logs/verifier/ctrf.json \
    -v
RC=$?

if [ "$RC" -eq 0 ]; then
    echo -n "1" > /logs/verifier/reward.txt
else
    echo -n "0" > /logs/verifier/reward.txt
fi

exit 0
