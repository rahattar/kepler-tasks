#!/bin/bash
# Runs the reference solution in the agent's environment: dilatometer tests of the materials whose parts are
# clearance-limited at their heating limits, each bore at the top of its range, and /app/output/bore_sheet.csv.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd /app
python3 "${DIR}/solve.py" "${DATA:-/app/data}" "${OUT:-/app/output/bore_sheet.csv}"
test -s "${OUT:-/app/output/bore_sheet.csv}"
