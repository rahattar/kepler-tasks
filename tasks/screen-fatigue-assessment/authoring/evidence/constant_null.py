"""No-science nulls against the per-screen requirement (within 20 %): how many of the ten screens a single constant
Miner sum satisfies, over a fine logarithmic grid and for constants a submission could pick without any assessment;
and filling one screen from the spacing of the other nine (exact), geometrically.

    python3 constant_null.py > constant_null.txt
"""
import os
import sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "provenance"))
import screens as S

true = S.DAMAGE
vals = sorted(true.items(), key=lambda kv: kv[1])
ratios = [b[1] / a[1] for a, b in zip(vals, vals[1:])]
print("true Miner sums to 2026-10-31: " + ", ".join("%s %.3f" % kv for kv in vals))
print("smallest ratio between neighbours %.3f; one constant can satisfy two screens only if their ratio is at most %.3f" % (min(ratios), 1.2 / 0.8))
grid = np.exp(np.linspace(np.log(0.01), np.log(10), 20001))
hits = np.array([sum(abs(c / t - 1) <= S.TOL for t in true.values()) for c in grid])
print("constants 0.01-10 on a log grid: most screens satisfied by one constant: %d of 10; constants satisfying none: %.0f %%" % (hits.max(), 100 * np.mean(hits == 0)))
for name, c in (("D = 1 (design life)", 1.0), ("D = 0.5", 0.5), ("geometric mean of the true values", float(np.exp(np.mean(np.log(list(true.values())))))),
                ("median of the true values", float(np.median(list(true.values()))))):
    ok = [u for u in S.UNITS if abs(c / true[u] - 1) <= S.TOL]
    print("  %-38s %.3f -> satisfies %d of 10 %s" % (name, c, len(ok), " ".join(ok)))
g = float(np.exp(np.median(np.log(ratios))))
print("filling one screen from the other nine (exact) and their spacing; median neighbour ratio %.3f:" % g)
for i, (u, t) in enumerate(vals):
    if i == 0:
        guess = vals[1][1] / g
    elif i == len(vals) - 1:
        guess = vals[-2][1] * g
    else:
        guess = np.sqrt(vals[i - 1][1] * vals[i + 1][1])
    e = guess / t - 1
    print("  %-4s true %.3f, spacing guess %.3f, miss %+.3f%s" % (u, t, guess, e, " (fails)" if abs(e) > S.TOL else ""))
