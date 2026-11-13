#!/bin/bash
# The solution is one file: solution/airflow.py, left at /app/output/airflow.py.
#
# After leaving it there this script runs it once, from a directory of its own, on the two example packages
# under /app/data, the two the survey crew answers for here, and says how they compare with their results.
# That run changes nothing: whatever it reports, the program delivered is the reference.
set -euo pipefail
from="$(cd "$(dirname "$0")" && pwd)"
mkdir -p /app/output
cp "$from/airflow.py" /app/output/airflow.py
echo "airflow.py left at /app/output/airflow.py"

try_it() {
    local room
    room="$(mktemp -d)"
    cp /app/output/airflow.py "$room/airflow.py"
    cd "$room"
    for package in /app/data/examples/*; do
        python3 airflow.py "$package" "$room/$(basename "$package").csv" || return 1
    done
    python3 - "$room" <<'PY'
import csv, glob, os, sys
for expected in sorted(glob.glob("/app/data/examples/*/expected.csv")):
    name = os.path.basename(os.path.dirname(expected))
    want = {r["point"]: float(r["flow_m3_s"]) for r in csv.DictReader(open(expected))}
    got = {r["point"]: float(r["flow_m3_s"]) for r in csv.DictReader(open(os.path.join(sys.argv[1], name + ".csv")))}
    out = sum(1 for p, w in want.items() if abs(got[p] - w) > max(0.015 * abs(w), 0.03))
    print("%s: %d of %d points out of band" % (name, out, len(want)))
PY
    rm -rf "$room"
}

(try_it) || echo "the trial run did not finish; airflow.py is in place all the same"
