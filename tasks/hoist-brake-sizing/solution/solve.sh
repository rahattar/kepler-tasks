#!/bin/bash
# Runs the reference solution in the agent's environment: seven friction tests (O1 at 20, 60 and 160 C; O2 at 20, 160,
# 200 and 260 C) and one engagement test (S16 at 65 %, AC-side switching), the MS-14 checks on a lumped brake model,
# and /app/output/brakes.json.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd /app
python3 "${DIR}/solve.py" "${DATA:-/app/data}" "${OUT:-/app/output/brakes.json}"
test -s "${OUT:-/app/output/brakes.json}"
