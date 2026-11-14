#!/bin/bash
# Delivers the reference ropes.py to /app/output and shows it at work on the three works under /app/data, run
# the way it will be run: from an empty directory that holds a copy of the program and nothing else. For the
# two works that come with expected.csv, the sheet is laid against it rope by rope.
set -euo pipefail
here="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
mkdir -p /app/output
cp "$here/ropes.py" /app/output/ropes.py
chmod 644 /app/output/ropes.py

for works in /app/data/examples/* /app/data/pending/*; do
    bench="$(mktemp -d)"
    cp /app/output/ropes.py "$bench/ropes.py"
    SECONDS=0
    (cd "$bench" && python3 ropes.py "$works" "$bench/damage.csv")
    echo "$(basename "$works"): $(($(wc -l < "$bench/damage.csv") - 1)) stations, about ${SECONDS} s"
    if [ -f "$works/expected.csv" ]; then
        python3 - "$bench/damage.csv" "$works/expected.csv" <<'PY'
import csv, sys
got = {r["row"]: float(r["damage"]) for r in csv.DictReader(open(sys.argv[1]))}
want = {r["row"]: float(r["damage"]) for r in csv.DictReader(open(sys.argv[2]))}
top = {}
for row, value in want.items():
    rope = row.rsplit("-", 1)[0]
    top[rope] = max(top.get(rope, 0.0), value)
for rope in sorted(top):
    worst = max(abs(got[row] - value) for row, value in want.items() if row.rsplit("-", 1)[0] == rope)
    print("    %s: greatest damage %.4f, largest difference from expected.csv %.2f per cent of it" % (rope, top[rope], 100 * worst / top[rope]))
PY
    fi
    rm -rf "$bench"
done
