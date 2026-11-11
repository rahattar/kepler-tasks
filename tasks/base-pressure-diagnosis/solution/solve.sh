#!/bin/bash
# Places this quarter's audit test order, then runs the reference audit and writes the result sheet.
set -eu
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# The order buys the one thing the records cannot supply. VC07's constant-looking load fits an air leak, but the
# July speed test, taken just before its fixture plate was refitted, shows the load was not there before the refit,
# and every pumpdown since is at 16 h: a trapped volume and a leak read alike there, and nothing says how fast a
# trapped volume would empty, which is what its gas load at the 36 h reference condition turns on. One measurement
# at a longer pumping time settles it. VC08, whose jump after its bracket work looks like the chamber to test, is
# settled by its own October speed test, taken after a 42 h pumpdown. The other chambers need no test.
cat > /tmp/plan.json <<'PLAN'
{"tests": [{"chamber": "VC07", "test": "rga", "pumping_time_h": 36}]}
PLAN
vacwork submit < /tmp/plan.json

mkdir -p /app/output
python3 -I "$HERE/diagnose.py" /app/data /app/output/diagnosis.csv /app/vacwork
cat /app/output/diagnosis.csv
