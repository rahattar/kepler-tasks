"""Correct side of the 3 pp bound: the reference with other sound choices, one at a time.

    python3 authoring/evidence/method_spread.py > authoring/evidence/method_spread.txt
"""
import methods as M

VARIANTS = [
    ("reference", {}),
    ("end of record: median of the last 21 days", dict(end="last21")),
    ("end of record: median of the last 28 days", dict(end="last28")),
    ("end of record: line through daily medians", dict(end="daily")),
    ("bypass flow smoothed over 13 h", dict(b_window=13)),
    ("bypass flow smoothed over 49 h", dict(b_window=49)),
    ("bypass flow as the daily median", dict(b_window="daily")),
    ("C3 meter zero as the mean of the shut hours", dict(c3_zero_from="mean")),
    ("C3 meter zero from 07-08 to 07-18 only", dict(c3_zero_from="inner")),
    ("C2 offset against the mean of the others", dict(c2_ref="mean")),
    ("C2 offset against C1 alone", dict(c2_ref="C1")),
    ("Simpson's rule with 20 intervals", dict(simpson=20)),
    ("Simpson's rule with 80 intervals", dict(simpson=80)),
    ("C4 power factor from 10 days either side", dict(c4_window=10)),
    ("C6 step measured against May only", dict(c6_before_from="2026-05-01")),
]

if __name__ == "__main__":
    print("Miss per cell, percentage points (reported - true); the bound is 3 pp.\n")
    worst = 0.0
    for name, o in VARIANTS:
        d = M.misses(o)
        w = max(d.values(), key=abs)
        cell = max(d, key=lambda c: abs(d[c]))
        worst = max(worst, abs(w))
        print("%-46s worst %+5.1f (%s)  %s" % (name, w, cell, " ".join("%s %+.1f" % (c, d[c]) for c in M.CELLS)))
    print("\nLargest miss over all variants: %.1f pp" % worst)
