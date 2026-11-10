"""Spread of sound methods on the shipped bank: the passing allocation (E8, E9, E10) in every order, crossed with
the choices a sound method could make: how the 2025 clean test is split between the films (one common factor, all
on the shell film, all on the tube film), the statistic of the standby readings (median or mean), and how the trend
is carried to the test day (a line with a step at the shock chlorination, over four weeks or the last two, or
a line through the hours after the shock only). Figures: worst unit's |error|, m2K/kW.

    python3 method_spread.py > method_spread.txt
"""
import itertools
import numpy as np
import methods as M

rows = []
for plan in itertools.permutations(["E8", "E9", "E10"]):
    for how, stat, (growth, win) in itertools.product(("common", "shell", "tube"), ("median", "mean"),
                                                      (("step", 28), ("step", 14), ("after", 28))):
        e, w, fails, _ = M.grade(M.estimate(list(plan), scale_how=how, bias_stat=stat, growth=growth, window_days=win)[0])
        rows.append((e, w, plan, how, stat, "line after the shock dose" if growth == "after" else "line and step, %d d" % win))
E = np.array([r[0] for r in rows])
print("sound methods: %d estimates (the passing allocation in every run order x method choices)" % len(rows))
print("worst-unit error: min %.3f, median %.3f, max %.3f m2K/kW; fail at %.2f: %d" % (E.min(), np.median(E), E.max(), M.TOL, int((E > M.TOL).sum())))
for r in sorted(rows, key=lambda r: -r[0])[:5]:
    print("  %.3f at %s | %s | split %s, standby %s, %s" % (r[0], r[1], ",".join(r[2]), r[3], r[4], r[5]))
