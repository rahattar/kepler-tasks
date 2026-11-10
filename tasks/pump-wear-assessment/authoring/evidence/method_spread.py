"""Spread of sound methods on the shipped bank: the reference's choices crossed with the stretch of the trends
fitted (four weeks, the last three, the last two, the hours after the flowmeter's recalibration; P1's trip on
2026-10-09 leaves too few hours after it in the first two weeks to fit them alone), the fit's loss
(least squares or robust soft-L1) and the weight given to the three survey hours (x0.5, x1, x2).

    python3 method_spread.py > method_spread.txt
"""
import itertools
import numpy as np
import methods as M

rows = []
spans = (("four weeks", {}), ("last three weeks", dict(from_day=7)), ("last two weeks", dict(from_day=14)),
         ("after the recalibration", dict(from_day=10.2)))
for (name, kw), loss, wgt in itertools.product(spans, ("linear", "soft_l1"), (0.5, 1.0, 2.0)):
    e, w, fails, _ = M.grade(M.estimate(loss=loss, survey_weight=wgt, **kw)[0])
    rows.append((e, w, name, loss, wgt))
E = np.array([r[0] for r in rows])
print("sound methods: %d estimates" % len(rows))
print("worst-pump error: min %.3f, median %.3f, max %.3f m; fail at %.1f m: %d" % (E.min(), np.median(E), E.max(), M.TOL, int((E > M.TOL).sum())))
for r in sorted(rows, key=lambda r: -r[0])[:5]:
    print("  %.3f at %s | %s, %s, survey weight x%.1f" % r)
