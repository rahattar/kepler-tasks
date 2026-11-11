#!/bin/bash
# Runs the reference assessment in the agent's environment.
set -eu
cd "$(dirname "${BASH_SOURCE[0]}")"
exec python3 solve.py
