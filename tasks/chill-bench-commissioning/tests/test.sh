#!/bin/bash
# Reward is 0 unless pytest exits clean. Written before anything else runs, so a crash,
# a timeout or a missing artifact all leave 0 behind.
set -u

mkdir -p /logs/verifier
echo -n "0" > /logs/verifier/reward.txt

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE" || exit 0

python -m pytest test_recipe.py \
    -p no:cacheprovider \
    --ctrf=/logs/verifier/ctrf.json \
    -v
RC=$?

if [ "$RC" -eq 0 ]; then
    echo -n "1" > /logs/verifier/reward.txt
fi

exit 0
