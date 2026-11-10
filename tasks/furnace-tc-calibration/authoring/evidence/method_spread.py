"""Spread of sound methods on the shipped bay: every complete three-step plan (F3 at 1050 C, F5 and F8 at one process
step each), in every run order, crossed with the choices a sound method could make: the 850/1050 offset ratio
(least squares or median of the 2025 calibration, the T^4 radiation law zero at the 600 C soak, the F8 factory
table), the statistic of the 600 C soak readings (median or mean), how the drift growth is read from the process
spike - raw trend (least-squares line, or the first and last 48 hours), and how F3's drift is split from the
heater-to-load difference (temperatures at the junction or at the setpoints; the 850 C trend carried to the
calibration by the line or by the last 48 hours), and how the bare-quartz heater-to-load baseline behind the
liner transfer is formed (median or mean; all four quartz T-200 furnaces or only the three that soak in standby),
and how partial boats are handled in the process trends (full boats only, or every row with the boat load as a
regressor, referred to a full boat).
All figures are the worst zone's |wafer - setpoint| in K; acceptance 2 K.

    python3 method_spread.py > method_spread.txt
"""
import itertools
import numpy as np
import methods as M

ONE = ((850,), (1050,))


def plans():
    for s5, s8 in itertools.product(ONE, ONE):
        base = [("F3", (1050,)), ("F5", s5), ("F8", s8)]
        for order in itertools.permutations(base):
            yield list(order)


CHOICES = dict(rho=("ls", "median", "t4", "fat"), stat=("median", "mean"), growth=("fit", "ends"),
               split=("junction", "setpoint"), split_gap=("fit", "ends"), base_stat=("median", "mean"),
               base_set=("quartz", "standby"), boats=("full", "regress"))


def main():
    rows = []
    keys = list(CHOICES)
    for plan in plans():
        for vals in itertools.product(*CHOICES.values()):
            kw = dict(zip(keys, vals))
            e, z, fails = M.grade(M.calibrate(plan, **kw))
            rows.append((e, z, " ".join("%s@%s" % (f, "+".join(map(str, s))) for f, s in plan), kw))
    E = np.array([r[0] for r in rows])
    n_plans = len(list(plans()))
    print("sound methods on the shipped bay: %d calibrations (%d plans and run orders x %d method choices)"
          % (len(rows), n_plans, len(rows) // n_plans))
    print("worst-zone error: min %.2f K, median %.2f K, 95th percentile %.2f K, max %.2f K; fail at 2 K: %d"
          % (E.min(), np.median(E), np.percentile(E, 95), E.max(), int((E > 2.0).sum())))
    print("\nworst-zone error by choice (max over everything else)")
    for k, levels in CHOICES.items():
        print("  %-10s " % k + "  ".join("%s %.2f K" % (l, max(r[0] for r in rows if r[3][k] == l)) for l in levels))
    print("\nten worst calibrations")
    for r in sorted(rows, key=lambda r: -r[0])[:10]:
        print("  %.2f K at %s | %s | %s" % (r[0], r[1], r[2], ", ".join("%s %s" % kv for kv in r[3].items())))
    ref = M.grade(M.calibrate(M.REFERENCE_PLAN))
    print("\nreference (F3@1050 F5@1050 F8@1050; ratio ls, soak median, growth by line, split at the junction): "
          "worst %.2f K at %s" % ref[:2])
    print("ratio estimates: " + ", ".join("%s %.4f" % (k, M.RHO[k]) for k in ("ls", "median", "t4", "fat")))


if __name__ == "__main__":
    main()
