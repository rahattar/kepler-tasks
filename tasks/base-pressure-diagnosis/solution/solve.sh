#!/bin/bash
# Places this quarter's audit test order, then runs the reference audit and writes the result sheet.
set -eu
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# The order buys the one thing the records cannot supply. VC08's trapped volume appeared when its cryopanel
# brackets were replaced, and both pumpdowns since are at 16 h: they give its trapped load at 16 h and nothing about
# how fast it empties, which is what its gas load at the 36 h reference condition turns on. One measurement of the
# gas load at a longer pumping time settles it; at the contractor's default 16 h it would only repeat the log. The
# other nine chambers are identified from their own records.
cat > /tmp/plan.json <<'PLAN'
{"tests": [{"chamber": "VC08", "test": "rga", "pumping_time_h": 36}]}
PLAN
vacwork submit < /tmp/plan.json

mkdir -p /app/output
python3 -I "$HERE/diagnose.py" /app/data /app/output/diagnosis.csv /app/vacwork
cat /app/output/diagnosis.csv
