#!/bin/bash
# Orders the outage programme (survey S5, coast-down S6 and S8) and writes /app/output/damage.json.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA="${DATA:-/app/data}"
FIELD="${FIELD:-/app/fieldwork}"
OUT="${OUT:-/app/output/damage.json}"
echo "running as $(id -un)"
if cat /opt/fieldwork/screens.py > /dev/null 2>&1; then
    echo "field-work files readable from the agent's user"
else
    echo "field-work files not readable from the agent's user"
fi
mkdir -p "$(dirname "${OUT}")"
cd "${DIR}"
python3 solve.py "${DATA}" "${FIELD}" "${OUT}"
test -s "${OUT}"
