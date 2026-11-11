#!/bin/bash
# Runs the reference solution in the agent's environment: it finds the form tester's own error motion from its
# records, orders its four scans through formscan itself, and writes /app/output/form.csv.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd /app
python3 "${DIR}/solve.py" "${DATA:-/app/data}" "${SCANS:-/app/scan_reports}" "${OUT:-/app/output/form.csv}"
test -s "${OUT:-/app/output/form.csv}"
