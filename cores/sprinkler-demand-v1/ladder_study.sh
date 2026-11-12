#!/bin/sh
# The ladder on every package: error in pressure of each program that stops short. Usage: sh ladder_study.sh
cd "$(dirname "$0")"
mkdir -p /tmp/v1ladder
python3 - <<'PY'
import json, os, subprocess, sys
root = "core"
rows = []
for sub, key in (("data/examples", "expected.json"), ("hidden", "truth.json")):
    for tag in sorted(os.listdir(os.path.join(root, sub))):
        d = os.path.join(root, sub, tag)
        tr = json.load(open(os.path.join(d, key)))
        tr = tr.get("result", tr)
        line = "%-5s" % tag
        for mode in ("absolute", "as_recorded", "all_C", "all_C_valves"):
            out = "/tmp/v1ladder/%s_%s.json" % (tag, mode)
            subprocess.run([sys.executable, "ladder.py", mode, d, out], stderr=subprocess.DEVNULL)
            r = json.load(open(out))
            line += " | %s %+6.1f%% (chi %7.1f)" % (mode, 100 * (r["pressure_psi"] / tr["pressure_psi"] - 1), r["fit_chi2"])
        print(line, flush=True)
PY
