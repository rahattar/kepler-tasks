#!/bin/bash
# Runs the reference solution in the agent's environment: eight laboratory tests, one of each heat (the three G52 heats
# double tempered; 41-7864 at the pinions' 25 mm surface; 43-2288, 32-0458, 43-2210 and 41-7731 at their batches'
# conditions; 11 tempers), the supplier curves with the Hollomon-Jaffe time conversion and a section correction, and
# /app/output/tempering.json.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd /app
python3 "${DIR}/solve.py" "${DATA:-/app/data}" "${OUT:-/app/output/tempering.json}"
test -s "${OUT:-/app/output/tempering.json}"
