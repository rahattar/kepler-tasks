#!/bin/bash
# Installs the reference program (solution/fan.py) at /app/output/fan.py and runs it on the example fan as a check.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="${OUT:-/app/output/fan.py}"
DATA="${DATA:-/app/data}"
mkdir -p "$(dirname "${OUT}")"
cp "${DIR}/fan.py" "${OUT}"
python3 "${OUT}" "${DATA}/examples/boiler-fd-fan" "$(mktemp)"
test -s "${OUT}"
