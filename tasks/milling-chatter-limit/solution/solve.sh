#!/bin/bash
# Installs the reference program (solution/chatter.py) at /app/output/chatter.py and runs it on the example job as a
# check.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="${OUT:-/app/output/chatter.py}"
DATA="${DATA:-/app/data}"
mkdir -p "$(dirname "${OUT}")"
cp "${DIR}/chatter.py" "${OUT}"
python3 "${OUT}" "${DATA}/examples/job-ex" "$(mktemp)"
test -s "${OUT}"
