#!/bin/bash
# The reward for a submitted indicate.py: one character in /logs/verifier/reward.txt.
#
# The file is written as 0 before anything is run and stays 0 unless all of this holds:
#   - /app/output/indicate.py was delivered;
#   - pytest, running the one test of test_indicate.py, ended with status 0;
#   - the report pytest left counts exactly one test, and it passed (one_passed.py).
# The test itself runs the program on the six cells, each run inside its time limit; see check_program.py.
# A program that runs over on any cell fails that test, so it cannot reach the 1.
set -u
umask 077

mkdir -p /logs/verifier
echo -n "0" > /logs/verifier/reward.txt
rm -f /logs/verifier/ctrf.json /logs/verifier/cells.json
cd "$(dirname "$0")" || exit 0

delivered=no
[ -f /app/output/indicate.py ] && delivered=yes

ran_clean=no
counted=no
if [ "$delivered" = yes ]; then
    if python -m pytest test_indicate.py -q -p no:cacheprovider --ctrf=/logs/verifier/ctrf.json; then
        ran_clean=yes
    fi
    if python one_passed.py /logs/verifier/ctrf.json; then
        counted=yes
    fi
fi
echo "test.sh: delivered=$delivered pytest_clean=$ran_clean one_test_passed=$counted" >&2

# The program ran as nobody while this script waited. The folder is made root's again and the reward file is
# replaced, not appended to, so that the character read afterwards is the one written here.
chown 0:0 /logs/verifier 2>/dev/null
chmod 700 /logs/verifier
rm -f /logs/verifier/reward.txt
if [ "$delivered" = yes ] && [ "$ran_clean" = yes ] && [ "$counted" = yes ]; then
echo -n "1" > /logs/verifier/reward.txt
else
echo -n "0" > /logs/verifier/reward.txt
fi
exit 0
