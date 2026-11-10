"""Spread of sound methods on the shipped house: the two passing programmes (third test on S8 or S10), median or
smallest sibling proxy, 8 or 16 start phases per simulated coast-down, and S1's wet-gauge change taken from the
data (August) or from the log (2026-09-08).

    python3 method_spread.py > method_spread.txt
"""
import itertools
import numpy as np
import plans as P

rows = []
for frm in ("2026-08-20", "2026-09-08"):
    for nph in (8, 16):
        o = P.opts(debond_from=frm, n_phase=nph)
        comp = P.components(o)
        for third, proxy in itertools.product(("S8", "S10"), ("median", "min")):
            plan = [("S5", "strain-survey"), ("S6", "coast-down"), (third, "coast-down")]
            w, u, f, _ = P.grade(P.assemble(comp, plan, o, proxy))
            rows.append((w, u, frm, nph, third, proxy, len(f)))
E = np.array([r[0] for r in rows])
print("sound methods: %d estimates" % len(rows))
print("worst-screen relative miss: min %.3f, median %.3f, max %.3f; fail at 0.20: %d" % (E.min(), np.median(E), E.max(), sum(r[6] > 0 for r in rows)))
for r in sorted(rows, key=lambda r: -r[0])[:6]:
    print("  %.3f at %s | S1 change from %s, %d phases, third test %s, proxy %s" % r[:6])
