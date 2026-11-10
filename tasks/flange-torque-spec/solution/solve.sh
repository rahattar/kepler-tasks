#!/bin/bash
# Runs the reference solution in the agent's environment: eight trials on the rig, a nut-factor fit, and
# /app/output/torques.json.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "${DIR}/solve.py" "${DATA:-/app/data}" "${OUT:-/app/output/torques.json}"
test -s "${OUT:-/app/output/torques.json}"
