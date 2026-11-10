#!/bin/bash
# Installs the reference route diagnosis program (solution/diagnose.py) at /app/output/diagnose.py and runs it on the
# example route as a check.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="${OUT:-/app/output/diagnose.py}"
DATA="${DATA:-/app/data}"
mkdir -p "$(dirname "${OUT}")"
cp "${DIR}/diagnose.py" "${OUT}"
python3 "${OUT}" "${DATA}/examples/u2-2026-10-20" "$(mktemp)" > /dev/null
test -s "${OUT}"
