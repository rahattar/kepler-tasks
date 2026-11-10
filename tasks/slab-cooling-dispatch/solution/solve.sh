#!/bin/bash
# Fit the two zone models and the forecast factor from /app/data, write the self-contained
# controller to /app/controller.py (OUT overrides, for local runs), then run the interface check.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export OUT="${OUT:-/app/controller.py}"
cd "${DIR}"
python3 fit.py
test -s "${OUT}"
CHECK=/app/check_controller.py
[ -f "${CHECK}" ] || CHECK="${DIR}/../environment/check_controller.py"
python3 "${CHECK}" "${OUT}"
