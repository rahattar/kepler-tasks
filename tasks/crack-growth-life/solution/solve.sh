#!/bin/bash
# Runs the reference solution in the agent's environment: five Paris tests in the laboratory (four on heat H1, one on
# S460NL heat H4), a growth-law fit with a linear closure law and heat factors (H2's from the earlier crack E02), and
# /app/output/intervals.json.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "${DIR}/solve.py" "${DATA:-/app/data}" "${OUT:-/app/output/intervals.json}"
test -s "${OUT:-/app/output/intervals.json}"
