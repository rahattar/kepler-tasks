#!/bin/bash
# Places this quarter's audit test order, then runs the reference audit and writes the result sheet.
set -eu
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# The order buys the one thing the records cannot supply. Every chamber's records are fitted as the audit fits
# them, and then asked which other budgets they would accept as well: clause 3.3 allows a trapped volume on any
# chamber, of any size and any time constant up to its bound, so for each one the rest of the budget is refitted
# and kept if the fit is as good within the 95 per cent bound on one quantity. The spread of the kept budgets' gas
# loads at 36 h is how far the records determine the answer. The test goes, at 36 h, where that spread is widest:
# VC06, whose two short pumpdowns were air vents and two long ones nitrogen vents, so a slowly emptying volume
# reads across them as a leak beside a wall. VC07, VC08 and VC04, whose records look the most in need of a test,
# are each settled by their own entries and speed tests once those are read correctly.
python3 -I "$HERE/diagnose.py" --plan /app/data > /tmp/plan.json
cat /tmp/plan.json
vacwork submit < /tmp/plan.json

mkdir -p /app/output
python3 -I "$HERE/diagnose.py" /app/data /app/output/diagnosis.csv /app/vacwork
cat /app/output/diagnosis.csv
