#!/bin/bash
# Verdict on the delivered program, as /logs/verifier/reward.txt: a single 0 or 1.
#
# A zero is put down before anything runs. The one replaces it only after a chain of three, each needing the
# last: ropes.py exists at /app/output; pytest on test_ropes.py exits cleanly, meaning rope_bench.py ran the
# program on all six hidden works within LIMIT_S and found no station of any rope outside its band; and
# rope_bench.py --one-passed finds the ctrf report to hold exactly one test, a passing one. Whatever breaks the
# chain leaves the zero. The program runs as nobody, for whom the reward's folder is shut.
#
# Left behind for whoever reads the logs:
#   reward.txt    the verdict above
#   ctrf.json     pytest's report on its one test
#   trials.json   the bench's notes, works by works in the order tried: seconds on the clock and of CPU, how
#                 the run ended, and for a sheet that could be read, rows out and the widest departure of
#                 each rope in bands; a run stopped at the limit is the last entry
mkdir -p /logs/verifier
umask 077
echo -n "0" > /logs/verifier/reward.txt
pushd "$(dirname -- "$(readlink -f -- "$0")")" > /dev/null || exit 0
report=/logs/verifier/ctrf.json
for stale in "$report" /logs/verifier/trials.json; do rm -f "$stale"; done
outcome=refused
test -f /app/output/ropes.py \
  && python -m pytest --ctrf=/logs/verifier/ctrf.json -p no:cacheprovider --quiet test_ropes.py \
  && python rope_bench.py --one-passed "$report" \
  && outcome=accepted
case "$outcome" in
  accepted)
echo -n "1" > /logs/verifier/reward.txt
    ;;
esac
echo "test.sh: the delivered program is $outcome" >&2
exit 0
