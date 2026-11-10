#!/bin/bash
# Writes /app/output/gt1_corrected_results.csv from the records in /app/data.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA="${DATA:-/app/data}"
OUT="${OUT:-/app/output/gt1_corrected_results.csv}"
mkdir -p "$(dirname "${OUT}")"
cd "${DIR}"
python3 solve.py "${DATA}" "${OUT}"
test -s "${OUT}"
