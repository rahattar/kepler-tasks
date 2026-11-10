"""Spread of sound methods on the shipped bank: the passing allocations (E9, E8 and either C-310 of the pair) in
every run order, crossed with the choices a sound method could make: how the 2025 clean test is split between the
films (one common factor, all on the shell film, all on the tube film), the statistic of the standby readings
(median or mean), and how the trend is carried to the test day (one rate with a level shift across the chlorine-free
days and a step at the shock dose, over seven weeks or the last three, or a line through the hours after the shock
dose only). Figures: worst unit's |error|, m2K/kW.

    python3 method_spread.py > method_spread.txt
"""
import itertools
import numpy as np
import methods as M

GROWTH = {("jump", 49): "rate, outage shift and shock step, 49 d", ("jump", 21): "rate, outage shift and shock step, 21 d",
          ("after", 49): "line through the hours after the shock dose"}
rows = []
for twin in ("E1", "E10"):
    for plan in itertools.permutations([twin, "E9", "E8"]):
        for how, stat, gw in itertools.product(("common", "shell", "tube"), ("median", "mean"), GROWTH):
            e, w, fails, _ = M.grade(M.estimate(list(plan), scale_how=how, bias_stat=stat, growth=gw[0],
                                                window_days=gw[1])[0])
            rows.append((e, w, plan, how, stat, GROWTH[gw]))
E = np.array([r[0] for r in rows])
print("sound methods: %d estimates (each passing allocation in every run order x method choices)" % len(rows))
print("worst-unit error: min %.3f, median %.3f, max %.3f m2K/kW; fail at %.2f: %d"
      % (E.min(), np.median(E), E.max(), M.TOL, int((E > M.TOL).sum())))
for r in sorted(rows, key=lambda r: -r[0])[:5]:
    print("  %.3f at %s | %s | split %s, standby %s, %s" % (r[0], r[1], ",".join(r[2]), r[3], r[4], r[5]))
