#!/bin/bash
# Places this quarter's audit test order, then runs the reference audit and writes the result sheet.
set -eu
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# The order buys the only thing the records cannot supply: the composition of the gas in the one chamber whose log
# holds a single pumping time, which is what separates a trapped volume from wall gas there. Everything else - the
# speeds of the two chambers whose turbo has changed, the chamber whose gauge certificate is out, and the leak
# that has to be told from permeation - comes from the records.
cat > /tmp/plan.json <<'PLAN'
{"tests": [{"chamber": "VC08", "test": "rga"}]}
PLAN
vacwork submit < /tmp/plan.json

mkdir -p /app/output
python3 -I "$HERE/diagnose.py" /app/data /app/output/diagnosis.csv /app/vacwork
cat /app/output/diagnosis.csv
