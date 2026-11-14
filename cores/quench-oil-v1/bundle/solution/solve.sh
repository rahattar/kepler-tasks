#!/bin/bash
# Puts the reference program where the task asks for it. That is the whole of the solution.
#
# It then tries the program once where it was put, on the two example packages, against their results (the
# laboratory here answers for those two only). The trial only reports; whatever it finds, the program
# delivered is solution/quench.py.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
mkdir -p /app/output
cp "$here/quench.py" /app/output/quench.py
echo "quench.py is at /app/output/quench.py"

trial() {
    local scratch site package
    scratch="$(mktemp -d)"
    cd "$scratch"
    cp /app/output/quench.py quench.py
    for package in /app/data/examples/north_works /app/data/examples/east_works; do
        site="$(basename "$package")"
        python3 quench.py "$package" "$scratch/$site.csv" || return 1
        echo "$site: $(($(wc -l < "$scratch/$site.csv") - 1)) loads"
    done
    python3 - "$scratch" <<'PY'
import csv, sys
bands = {"t85_core_s": 0.015, "cr700_core_K_s": 0.015, "dT_max_K": 0.015, "ts_core500_C": 3.0, "t150_core_s": 0.015}
for site in ("north_works", "east_works"):
    want = {r["load"]: r for r in csv.DictReader(open("/app/data/examples/%s/expected.csv" % site))}
    got = {r["load"]: r for r in csv.DictReader(open("%s/%s.csv" % (sys.argv[1], site)))}
    out = 0
    for load, row in want.items():
        for name, band in bands.items():
            error = abs(float(got[load][name]) - float(row[name]))
            if name != "ts_core500_C":
                error /= abs(float(row[name]))
            if error > band:
                out += 1
                break
    print("%s: %d of %d loads out of band" % (site, out, len(want)))
PY
    local checked=$?
    rm -rf "$scratch"
    return $checked
}

if ! (trial); then
    echo "the trial run did not complete; quench.py is in place all the same"
fi
