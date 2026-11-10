#!/bin/bash
# Starts the clean-and-test service, spends the three slots and writes /app/output/fouling.csv.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA="${DATA:-/app/data}"
OUT="${OUT:-/app/output/fouling.csv}"
URL="${HXTEST_URL:-http://127.0.0.1:8000}"
echo "running as $(id -un)"
if cat /opt/hxtest/hx.py > /dev/null 2>&1; then
    echo "service files readable from the agent's user"
else
    echo "service files not readable from the agent's user"
fi
start-hxtest
mkdir -p "$(dirname "${OUT}")"
cd "${DIR}"
python3 solve.py "${DATA}" "${URL}" "${OUT}"
test -s "${OUT}"
