"""diagcheck.py FIELD: what the reference finds from the cards beside the sealed description of each well."""
import json, os, sys, subprocess, re
import numpy as np
name = sys.argv[1]
sealed = json.load(open("core/sealed/%s.json" % name))
d = [p for p in ("core/environment/data/examples/", "core/environment/data/pending/", "core/hidden/") if os.path.isdir(p + name)][0] + name
p = subprocess.run(["python3", "ref_rodlift.py", d, "/tmp/_dc.csv"], env=dict(os.environ, VERBOSE="1"), capture_output=True, text=True)
found = {}
for ln in p.stderr.splitlines():
    m = re.match(r"(\S+) Fo ([\d.]+) kN pi ([\d.]+) MPa comp reg (\S+) free (\S+) meas (\S+) used (\S+) q_in (\S+)", ln)
    if m:
        found[m.group(1)] = [float(x) for x in m.groups()[1:]]
import rodsim as rs
for w in sealed["wells"]:
    f = found[w["well"]]
    q_true = w["q_in"]
    Ap = rs.area(w["plunger"])
    print("%s %-6s Fo true %6.2f found %6.2f (%+.2f%%)  q_in true %s found %s  fill %.2f  comp meas/free %.3f used/free %.3f" % (
        w["well"], w["kind"], w["Fo"] / 1e3, f[0], 100 * (f[0] * 1e3 / w["Fo"] - 1),
        "full    " if q_true is None else "%.3e" % q_true, "full    " if np.isinf(f[6]) else "%.3e (%+.1f%%)" % (f[6], 100 * (f[6] / q_true - 1) if q_true else float("nan")),
        w["found_fill"], f[4] / f[3], f[5] / f[3]))
