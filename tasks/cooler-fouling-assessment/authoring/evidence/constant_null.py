"""No-science nulls against the per-unit requirement: how many of the ten units a single constant fouling figure
satisfies, for every constant from 0 to 1.2 m2K/kW, and for the constants a submission could pick without any
assessment (zero, a textbook cooling-water allowance, the middle of the bank). Truth from the sealed definition.

    python3 constant_null.py > constant_null.txt
"""
import numpy as np
import methods as M
hx = M.hx
true = {u: hx.rf(M.FLEET[u], hx.T_TEST) for u in hx.UNITS}
print("true as-found fouling on 2026-10-26 (m2K/kW): " + ", ".join("%s %.3f" % (u, true[u]) for u in hx.UNITS))
gaps = np.diff(sorted(true.values()))
print("smallest gap between two units: %.3f m2K/kW, against a window of 2 x %.2f = %.2f" % (gaps.min(), M.TOL, 2 * M.TOL))
grid = np.round(np.arange(0.0, 1.5001, 0.001), 3)
hits = np.array([sum(abs(c - t) <= M.TOL for t in true.values()) for c in grid])
print("constants 0 to 1.5 in steps of 0.001: most units satisfied by any one constant: %d of 10; "
      "constants satisfying none: %.0f %%" % (hits.max(), 100.0 * np.mean(hits == 0)))
for name, c in (("zero", 0.0), ("TEMA-style cooling-water allowance 0.18", 0.18), ("TEMA-style 0.35", 0.35),
                ("middle of the bank (median of the true values)", float(np.median(list(true.values())))),
                ("mean of the true values", float(np.mean(list(true.values()))))):
    ok = [u for u in hx.UNITS if abs(c - true[u]) <= M.TOL]
    print("  %-50s %.3f -> satisfies %d of 10 %s" % (name, c, len(ok), " ".join(ok)))
# answer-key structure: even with the other nine units known exactly, filling a unit from the spacing of the rest
# (midway between its neighbours, or one median gap beyond the end) misses the units that need a test
vals = sorted(true.items(), key=lambda kv: kv[1])
med_gap = float(np.median(gaps))
print("filling one unit from the other nine (exact) and their spacing; median gap %.3f m2K/kW:" % med_gap)
for i, (u, t) in enumerate(vals):
    if i == 0:
        g = vals[1][1] - med_gap
    elif i == len(vals) - 1:
        g = vals[-2][1] + med_gap
    else:
        g = (vals[i - 1][1] + vals[i + 1][1]) / 2
    print("  %-4s true %.3f, spacing guess %.3f, error %+.3f %s" % (u, t, g, g - t, "" if abs(g - t) <= M.TOL else "(fails)"))
