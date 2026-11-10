#!/bin/bash
# Installs the reference audit program (solution/audit.py) at /app/output/audit.py and runs it on the example audit
# as a check.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="${OUT:-/app/output/audit.py}"
DATA="${DATA:-/app/data}"
mkdir -p "$(dirname "${OUT}")"
cp "${DIR}/audit.py" "${OUT}"
python3 "${OUT}" "${DATA}/examples/s-201" "$(mktemp)" > /dev/null
test -s "${OUT}"
