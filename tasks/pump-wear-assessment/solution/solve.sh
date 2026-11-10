#!/bin/bash
# Reads the plant records and writes /app/output/overhaul.json.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA="${DATA:-/app/data}"
OUT="${OUT:-/app/output/overhaul.json}"
mkdir -p "$(dirname "${OUT}")"
cd "${DIR}"
python3 solve.py "${DATA}" "${OUT}"
test -s "${OUT}"
