#!/bin/bash
# Installs the reference program (solution/surge.py) at /app/output/surge.py and runs it on the example main as a
# check.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="${OUT:-/app/output/surge.py}"
DATA="${DATA:-/app/data}"
mkdir -p "$(dirname "${OUT}")"
cp "${DIR}/surge.py" "${OUT}"
python3 "${OUT}" "${DATA}/examples/kestrel-lane" "$(mktemp)"
test -s "${OUT}"
