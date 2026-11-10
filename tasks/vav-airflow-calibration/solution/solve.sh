#!/bin/bash
# Starts the capture-hood visit service, spends the five visits and writes /app/output/calibration.csv.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA="${DATA:-/app/data}"
OUT="${OUT:-/app/output/calibration.csv}"
URL="${HOOD_URL:-http://127.0.0.1:8000}"
VISITS="${VISITS:-/app/visits}"
# diagnostics for the author's harbor log: the service's files must not be readable from here
echo "running as $(id -un)"
if cat /opt/hood/vav.py > /dev/null 2>&1; then
    echo "service files readable from the agent's user"
else
    echo "service files not readable from the agent's user"
fi
start-hood
mkdir -p "$(dirname "${OUT}")"
cd "${DIR}"
python3 solve.py "${DATA}" "${URL}" "${VISITS}" "${OUT}"
test -s "${OUT}"
