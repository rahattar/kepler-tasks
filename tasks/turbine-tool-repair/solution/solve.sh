#!/bin/bash
# Installs the corrected reduction program (solution/gtperf.py) at /app/output/gtperf.py and runs it on the shipped
# examples as a check.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="${OUT:-/app/output/gtperf.py}"
DATA="${DATA:-/app/data}"
mkdir -p "$(dirname "${OUT}")"
cp "${DIR}/gtperf.py" "${OUT}"
for d in "${DATA}"/examples/*/; do
    python3 "${OUT}" "${d}" "$(mktemp)" > /dev/null
done
test -s "${OUT}"
