#!/bin/bash
# Installs the reference selection program (solution/design.py) at /app/output/design.py and runs it on the example
# case as a check.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="${OUT:-/app/output/design.py}"
DATA="${DATA:-/app/data}"
mkdir -p "$(dirname "${OUT}")"
cp "${DIR}/design.py" "${OUT}"
python3 "${OUT}" "${DATA}/examples/e410-k400-lube" "$(mktemp)" > /dev/null
test -s "${OUT}"
