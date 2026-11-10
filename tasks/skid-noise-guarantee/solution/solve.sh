#!/bin/bash
# Runs the reference solution in the agent's environment: the reverberation time of the hall as it is, the
# configuration difference of the two machines changed since the survey, and /app/output/sound_power.csv.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd /app
python3 "${DIR}/solve.py" "${DATA:-/app/data}" "${OUT:-/app/output/sound_power.csv}"
test -s "${OUT:-/app/output/sound_power.csv}"
