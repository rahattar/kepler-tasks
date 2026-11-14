#!/bin/bash
# Decides the reward for a submitted quench.py and leaves it, one character, in /logs/verifier/reward.txt.
#
#   1   the program finished all six sites, each run inside its limit, with every load within its bands
#   0   it did not, or that could not be established
#
# `verdict` begins at 1. Four things can take it to 0 and nothing can bring it back: no quench.py delivered,
# no directory to run the test from, pytest ending with any status but 0, and a pytest report in which
# read_report.py does not find exactly one test, passed. While the program is running the file holds 0.
set -u
umask 077

say() { printf 'test.sh: %s\n' "$*" >&2; }

mkdir -p /logs/verifier
chmod 700 /logs/verifier
echo -n "0" > /logs/verifier/reward.txt
rm -f /logs/verifier/ctrf.json

verdict=1
if [ ! -f /app/output/quench.py ]; then
    say "nothing was delivered at /app/output/quench.py"
    verdict=0
fi
if ! cd "$(dirname "$0")"; then
    say "the tests directory cannot be entered"
    verdict=0
fi

if [ "$verdict" -eq 1 ]; then
    say "running quench.py on the six sites"
    python -m pytest test_program.py -q -p no:cacheprovider --ctrf=/logs/verifier/ctrf.json || verdict=0
    python read_report.py /logs/verifier/ctrf.json || verdict=0
fi
say "verdict $verdict"

# quench.py ran as the user nobody in between. The directory is taken back and the reward written again
# from the verdict, so that nothing put there during the run is what gets read.
chown 0:0 /logs/verifier
chmod 700 /logs/verifier
rm -f /logs/verifier/reward.txt
if [ "$verdict" -eq 1 ]; then
    echo -n "1" > /logs/verifier/reward.txt
else
    echo -n "0" > /logs/verifier/reward.txt
fi
exit 0
