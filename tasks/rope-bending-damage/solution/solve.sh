#!/bin/bash
# Puts solution/ropes.py at /app/output/ropes.py, then tries it the way it will be tried: on each works under
# /app/data, from a directory of its own that holds a copy of the program and nothing else. For a works with
# expected.csv, prints how far the sheet is from it, rope by rope, as a share of the rope's greatest damage.
set -euo pipefail
source_dir="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
install -D -m 644 "$source_dir/ropes.py" /app/output/ropes.py

python3 - <<'PY'
import csv, glob, os, shutil, subprocess, tempfile, time

for works in sorted(glob.glob("/app/data/examples/*") + glob.glob("/app/data/pending/*")):
    scratch = tempfile.mkdtemp()
    shutil.copy("/app/output/ropes.py", scratch)
    began = time.process_time(); clock = time.time()
    subprocess.run(["python3", "ropes.py", works, os.path.join(scratch, "damage.csv")], cwd=scratch, check=True)
    with open(os.path.join(scratch, "damage.csv")) as handle:
        sheet = {r["row"]: float(r["damage"]) for r in csv.DictReader(handle)}
    print("%s: %d stations in %.1f s" % (os.path.basename(works), len(sheet), time.time() - clock))
    expected = os.path.join(works, "expected.csv")
    if os.path.exists(expected):
        with open(expected) as handle:
            want = {r["row"]: float(r["damage"]) for r in csv.DictReader(handle)}
        ropes = sorted({row.rsplit("-", 1)[0] for row in want})
        for rope in ropes:
            mine = {row: v for row, v in want.items() if row.rsplit("-", 1)[0] == rope}
            top = max(mine.values())
            gap = max(abs(sheet[row] - v) for row, v in mine.items())
            print("    %s: greatest damage %.4f, sheet off by at most %.2f per cent of it" % (rope, top, 100 * gap / top))
    shutil.rmtree(scratch)
PY
