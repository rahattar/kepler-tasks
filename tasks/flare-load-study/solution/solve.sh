#!/bin/bash
# Produces the reference study inside the agent's own container: it works out which of the crew's tests reach a
# graded value, orders those through fieldtest itself, and writes /app/output/flare_load.csv.
set -eu
cd "$(dirname "${BASH_SOURCE[0]}")"
exec python3 solve.py
