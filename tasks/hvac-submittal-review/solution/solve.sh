#!/bin/bash
# Starts the field-verification service, reviews the submittal from /app/data and writes /app/review.json.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export DATA="${DATA:-/app/data}"
export OUT="${OUT:-/app/review.json}"
export VERIFY_URL="${VERIFY_URL:-http://127.0.0.1:8000}"
# diagnostics for the author's harbor log: the service's files must not be readable from here
echo "running as $(id -un)"
if cat /opt/verify/project.py > /dev/null 2>&1; then
    echo "service files readable from the agent's user"
else
    echo "service files not readable from the agent's user"
fi
start-verification
cd "${DIR}"
python3 solve.py
test -s "${OUT}"
