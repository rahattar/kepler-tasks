#!/bin/bash
# Installs the reference program (solution/pumpdown.py) at /app/output/pumpdown.py and runs it on the example chamber as a check.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="${OUT:-/app/output/pumpdown.py}"
DATA="${DATA:-/app/data}"
mkdir -p "$(dirname "${OUT}")"
cp "${DIR}/pumpdown.py" "${OUT}"
python3 "${OUT}" "${DATA}/examples/chamber-ex" "$(mktemp)"
test -s "${OUT}"
