#!/bin/bash
# Orders the inspection (oxide-ut E3, wall-ut E9) and writes /app/output/damage.json.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA="${DATA:-/app/data}"
FIELD="${FIELD:-/app/fieldwork}"
OUT="${OUT:-/app/output/damage.json}"
echo "running as $(id -un)"
if cat /opt/fieldwork/tubes.py > /dev/null 2>&1; then
    echo "inspection service files readable from the agent's user"
else
    echo "inspection service files not readable from the agent's user"
fi
mkdir -p "$(dirname "${OUT}")"
cd "${DIR}"
python3 solve.py "${DATA}" "${FIELD}" "${OUT}"
test -s "${OUT}"
