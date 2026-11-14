#!/bin/bash
# The reference is one program, solution/lines.py. This leaves it at /app/output/lines.py, where it is
# delivered, and then makes one trial run of it on each example package from a scratch directory, placing
# that package's survey order, and reports how the results compare with expected.csv. The trial changes
# nothing that is delivered.
set -eu
here="$(cd "$(dirname "$0")" && pwd)"
install -d /app/output
cp "$here/lines.py" /app/output/lines.py
echo "solve.sh: lines.py is at /app/output/lines.py"

trial="$(mktemp -d)"
cp /app/output/lines.py "$trial/"
for site in /app/data/examples/*/; do
    name="$(basename "$site")"
    if (cd "$trial" && python3 lines.py "$site" "$trial/$name.csv"); then
        python3 - "$site/expected.csv" "$trial/$name.csv" "$name" <<'PY' || true
import csv, sys
want = {r["record"]: r for r in csv.DictReader(open(sys.argv[1]))}
got = {r["record"]: r for r in csv.DictReader(open(sys.argv[2]))}
off = [k for k, w in want.items()
       if abs(float(got[k]["dp_kPa"]) / float(w["dp_kPa"]) - 1) > 0.015 or abs(float(got[k]["t_out_C"]) - float(w["t_out_C"])) > 0.5]
print("solve.sh: %s, %d of %d records outside 1.5 per cent and 0.5 K of expected.csv" % (sys.argv[3], len(off), len(want)))
PY
    else
        echo "solve.sh: the trial run on $name did not finish; lines.py is in place all the same"
    fi
done
rm -rf "$trial"
