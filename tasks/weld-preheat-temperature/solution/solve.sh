#!/bin/bash
# Installs the reference program (solution/preheat.py) at /app/output/preheat.py and runs it on the example joint as a check.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="${OUT:-/app/output/preheat.py}"
DATA="${DATA:-/app/data}"
mkdir -p "$(dirname "${OUT}")"
cp "${DIR}/preheat.py" "${OUT}"
python3 "${OUT}" "${DATA}/examples/joint-ex" "$(mktemp)"
test -s "${OUT}"
