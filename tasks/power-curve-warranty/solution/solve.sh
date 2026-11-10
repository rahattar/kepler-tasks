#!/bin/bash
# Installs the reference program (solution/pp12.py) at /app/output/pp12.py and runs it on the example package as a
# check.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="${OUT:-/app/output/pp12.py}"
DATA="${DATA:-/app/data}"
mkdir -p "$(dirname "${OUT}")"
cp "${DIR}/pp12.py" "${OUT}"
python3 "${OUT}" "${DATA}/examples/ridgeback-2026h1" "$(mktemp)"
test -s "${OUT}"
