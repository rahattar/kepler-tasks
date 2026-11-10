#!/bin/bash
# Reward 1 only if pytest exits cleanly; 0 is written first, so an early exit or a crash leaves 0.
set -u

mkdir -p /logs/verifier
chmod 700 /logs/verifier
echo -n "0" > /logs/verifier/reward.txt

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE" || exit 0

python -m pytest test_overhaul.py \
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
