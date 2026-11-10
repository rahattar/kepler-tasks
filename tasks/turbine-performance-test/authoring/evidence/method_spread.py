"""Correct side of the 0.5 % bound: the reference with other sound choices, one at a time.

    python3 authoring/evidence/method_spread.py > authoring/evidence/method_spread.txt
"""
import methods as M

VARIANTS = [
    ("reference", {}),
    ("last qualifying 30-minute window of each run", dict(window="last")),
    ("every base-load minute of each run", dict(window="all")),
    ("RTD bias from the noon reference-thermometer spot checks", dict(cit_from="spot")),
    ("fuel zero as the mean of the standstill minutes", dict(zero_stat="mean")),
    ("contaminated gas sample with its air removed", dict(gc_air="removed")),
    ("corrections applied minute by minute, then averaged", dict(per_minute=True)),
    ("one LHV for both days", dict(lhv_pooled=True)),
]

if __name__ == "__main__":
    print("Miss in percent, (output, heat rate) per condition; the bound is 0.5 %.\n")
    worst = 0.0
    for name, o in VARIANTS:
        d = M.misses(o)
        w = max((abs(v) for vv in d.values() for v in vv))
        worst = max(worst, w)
        print("%-56s worst %5.2f   as_found %+5.2f %+5.2f   as_left %+5.2f %+5.2f"
              % (name, w, d["as_found"][0], d["as_found"][1], d["as_left"][0], d["as_left"][1]))
    print("\nLargest miss over all variants: %.2f %%" % worst)
