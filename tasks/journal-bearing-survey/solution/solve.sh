#!/bin/bash
# Puts the reference program where the task asks for it, then runs it once on the three packages in /app/data
# as a check that it works where it was put: the two examples against their results, the pending package for
# its laboratory order.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
mkdir -p /app/output
cp "$here/bearing.py" /app/output/bearing.py

scratch="$(mktemp -d)"
cd "$scratch"
cp /app/output/bearing.py bearing.py
for package in /app/data/examples/north_works /app/data/examples/east_works /app/data/pending/west_quarry; do
    site="$(basename "$package")"
    python3 bearing.py "$package" "$scratch/$site.csv"
    echo "$site: $(($(wc -l < "$scratch/$site.csv") - 1)) points"
done
python3 - "$scratch" <<'PY'
import csv, sys
bands = {"h_min_um": 0.015, "power_kW": 0.015, "p_max_MPa": 0.015, "attitude_deg": 1.0, "t_eff_C": 0.5}
for site in ("north_works", "east_works"):
    want = {r["point"]: r for r in csv.DictReader(open("/app/data/examples/%s/expected.csv" % site))}
    got = {r["point"]: r for r in csv.DictReader(open("%s/%s.csv" % (sys.argv[1], site)))}
    out = 0
    for point, row in want.items():
        for name, band in bands.items():
            error = abs(float(got[point][name]) - float(row[name]))
            if name in ("h_min_um", "power_kW", "p_max_MPa"):
                error /= abs(float(row[name]))
            if error > band:
                out += 1
                break
    print("%s: %d of %d points out of band" % (site, out, len(want)))
PY
rm -rf "$scratch"
