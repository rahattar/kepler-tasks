#!/bin/bash
# Starts the TC-wafer run service, spends the three temperature steps and writes /app/output/corrections.csv.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA="${DATA:-/app/data}"
OUT="${OUT:-/app/output/corrections.csv}"
URL="${TCWAFER_URL:-http://127.0.0.1:8000}"
RUNS="${RUNS:-/app/runs}"
# diagnostics for the author's harbor log: the service's files must not be readable from here
echo "running as $(id -un)"
if cat /opt/tcwafer/tc.py > /dev/null 2>&1; then
    echo "service files readable from the agent's user"
else
    echo "service files not readable from the agent's user"
fi
start-tcwafer
mkdir -p "$(dirname "${OUT}")"
cd "${DIR}"
python3 solve.py "${DATA}" "${URL}" "${RUNS}" "${OUT}"
test -s "${OUT}"
