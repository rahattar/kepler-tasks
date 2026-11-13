#!/bin/bash
# Oracle step. The reference indicate.py goes to /app/output and is then tried on every package under
# /app/data from an empty directory, the way it will be run. Where a package holds expected.csv, the table
# the program wrote is set against it with the accuracies of IS-2 section 9. The program's own line on
# stderr says what it settled for the cell's indicating system.
set -euo pipefail
install -D -m 644 "$(dirname "$(readlink -f "$0")")/indicate.py" /app/output/indicate.py

try_package() {
    local package="$1" run
    run="$(mktemp -d)"
    cp /app/output/indicate.py "$run/"
    (cd "$run" && python3 indicate.py "$package" table.csv)
    if [ -f "$package/expected.csv" ]; then
        python3 -c '
import sys
import pandas as pd
keys = ["point", "cylinder"]
both = pd.read_csv(sys.argv[1]).merge(pd.read_csv(sys.argv[2]), on=keys, suffixes=("", "_is2"))
share = {"imep_bar": 0.02, "pmax_bar": 0.01, "q_gross_J": 0.03}
widest = 0.0
for column in both.columns:
    if column in keys or column.endswith("_is2"):
        continue
    gap = (both[column] - both[column + "_is2"]).abs()
    widest = max(widest, (gap / (share[column] * both[column + "_is2"].abs()) if column in share else gap / 0.3).max())
print("  %d rows, the widest departure %.2f of what IS-2 section 9 allows" % (len(both), widest))
' "$run/table.csv" "$package/expected.csv"
    else
        echo "  $(($(wc -l < "$run/table.csv") - 1)) rows, no results on file"
    fi
    rm -rf "$run"
}

for package in /app/data/examples/* /app/data/pending/*; do
    echo "$(basename "$package")"
    try_package "$package"
done
