#!/bin/bash
# Places this quarter's audit test order, then runs the reference audit and writes the result sheet.
set -eu
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# The two chambers whose records cannot settle their cause get a residual gas analysis; the two whose turbo has
# changed since its last speed test get a speed test.
cat > /tmp/plan.json <<'PLAN'
{"tests": [{"chamber": "VC06", "test": "rga"},
           {"chamber": "VC08", "test": "rga"},
           {"chamber": "VC09", "test": "speed-test"},
           {"chamber": "VC10", "test": "speed-test"}]}
PLAN
vacwork submit < /tmp/plan.json

mkdir -p /app/output
python3 -I "$HERE/diagnose.py" /app/data /app/output/diagnosis.csv /app/vacwork
cat /app/output/diagnosis.csv
