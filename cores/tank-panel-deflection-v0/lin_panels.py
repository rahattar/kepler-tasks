#!/usr/bin/env python3
"""lin_panels.py PACKAGE_DIR OUT_CSV: the small-deflection program. Clamped plate bending only (Ritz), so the
deflection and the edge stress are proportional to the pressure."""
import csv, os, sys
import numpy as np
import ref_panels as R

def coeff(r, nu, n=10):
    f = R.Film(r, nu, n)
    c = np.linalg.solve(f.Kb, f.fl)
    return f.rW @ c, 0.5 / (1 - nu * nu) * abs(f.rK @ c)

def main(pkg, out):
    mats = {r["material"]: (float(r["E_GPa"]) * 1e3, float(r["poisson"])) for r in csv.DictReader(open(os.path.join(pkg, "materials.csv")))}
    pan = {r["panel"]: r for r in csv.DictReader(open(os.path.join(pkg, "panels.csv")))}
    memo = {}
    with open(out, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["row", "deflection_mm", "edge_stress_MPa"])
        for r in csv.DictReader(open(os.path.join(pkg, "conditions.csv"))):
            p = pan[r["panel"]]; a, b, t = float(p["a_mm"]), float(p["b_mm"]), float(p["t_mm"]); E, nu = mats[p["material"]]
            key = (round(max(a, b) / min(a, b), 6), nu)
            if key not in memo: memo[key] = coeff(*key)
            Q = float(r["pressure_kPa"]) * 1e-3 * (min(a, b) / t) ** 4 / E
            w.writerow([r["row"], "%.6g" % (memo[key][0] * Q * t), "%.6g" % (memo[key][1] * Q * E * (t / min(a, b)) ** 2)])

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
