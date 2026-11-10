#!/bin/bash
# Runs the reference solution in the agent's environment: one dilatometer test of steel to 275 C and seven slip tests
# (one per hub material and preparation in use, shrink-fitted), each mean interference at the top of its range, and
# /app/output/fits.json.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd /app
python3 "${DIR}/solve.py" "${DATA:-/app/data}" "${OUT:-/app/output/fits.json}"
test -s "${OUT:-/app/output/fits.json}"
