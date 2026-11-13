"""compare.py OUT_CSV TRUTH_CSV: errors of a result table against the sealed one, by well."""
import csv, sys
import numpy as np
o = {r["setting"]: r for r in csv.DictReader(open(sys.argv[1]))}
t = list(csv.DictReader(open(sys.argv[2])))
tol = dict(st=0.03, liq=0.03, load=0.02)
by = {}
for r in t:
    x = o[r["setting"]]; w = r["setting"].rsplit("-", 1)[0]
    pp = float(r["pprl_kN"])
    e = (float(x["plunger_stroke_m"]) / float(r["plunger_stroke_m"]) - 1, float(x["liquid_m3_d"]) / float(r["liquid_m3_d"]) - 1,
         (float(x["pprl_kN"]) - pp) / pp, (float(x["mprl_kN"]) - float(r["mprl_kN"])) / pp)
    by.setdefault(w, []).append(e)
tot = 0
for w, e in by.items():
    e = np.array(e)
    bad = (np.abs(e[:, 0]) > tol["st"]) | (np.abs(e[:, 1]) > tol["liq"]) | (np.abs(e[:, 2]) > tol["load"]) | (np.abs(e[:, 3]) > tol["load"])
    tot += bad.sum()
    wm = np.abs(e).max(axis=0) * 100
    print("%s out %3d of %3d   worst %% stroke %5.2f liquid %5.2f pprl %5.2f mprl %5.2f" % (w, bad.sum(), len(e), *wm))
print("rows out:", tot, "of", len(t))
