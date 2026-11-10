#!/bin/bash
# Installs the reference program (solution/hpu.py) at /app/output/hpu.py and runs it on the example package
# as a check.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="${OUT:-/app/output/hpu.py}"
DATA="${DATA:-/app/data}"
mkdir -p "$(dirname "${OUT}")"
cp "${DIR}/hpu.py" "${OUT}"
python3 "${OUT}" "${DATA}/examples/p-01" "$(mktemp)" > /dev/null
test -s "${OUT}"
