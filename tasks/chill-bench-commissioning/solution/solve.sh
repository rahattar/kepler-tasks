#!/bin/bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd /app
python3 "${DIR}/solve.py"
test -s /app/recipe.json
