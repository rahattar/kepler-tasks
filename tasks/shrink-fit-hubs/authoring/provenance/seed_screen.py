"""Chooses the laboratory seed: the first seed from 7101 on which nine sound plans all get 12 of 12 with at least
0.3 % to spare on torque, stress and clearance, and no reading they draw is more than 2.5 standard deviations from its
mean. The seed drives only the laboratory's scatter.

    python3 authoring/provenance/seed_screen.py
"""
import math
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "evidence"))
import common as C  # noqa: E402

PLANS = [
    ("reference", {}),
    ("dilatometer last", dict(order=2)),
    ("steel cte to 270 C", dict(cte_T=270)),
    ("steel cte to 280 C", dict(cte_T=280)),
    ("friction at each pair's highest pressure", dict(friction="highest")),
    ("friction at each pair's median pressure", dict(friction="median")),
    ("oven at the heating limit", dict(oven="limit")),
    ("allowance 1.5 % of the oven expansion", dict(allowance=0.015)),
    ("friction at the highest pressure, mid-window pick", dict(friction="highest", pick="mid")),
]


def zmax(log):
    z = 0.0
    for e in log:
        if e[0] == "slip":
            _, mat, prep, p, shrink, v = e
            mean = C.S.MU50[(C.S.LABMAT[mat], prep)] * (p / 50.0) ** (-C.S.KF) * (1.0 if shrink else C.S.PRESS_FACTOR)
            z = max(z, abs(math.log(v / mean)) / C.S.NOISE_MU)
        else:
            _, mat, T, v = e
            z = max(z, abs(math.log(v / (C.S.cte(C.S.LABMAT[mat], T) * 1e6))) / C.S.NOISE_CTE)
    return z


def screen(seed):
    worst, zw, allok = 9.0, 0.0, True
    for _, kw in PLANS:
        f, log = C.solve_route(seed=seed, **kw)
        n, res, _ = C.grade(f)
        allok &= n == 12
        worst = min(worst, C.smallest_margin(res))
        zw = max(zw, zmax(log))
    return allok, worst, zw


def main():
    for seed in range(7101, 7200):
        ok, worst, zw = screen(seed)
        good = ok and worst >= 0.003 and zw <= 2.5
        print("seed %d: all plans 12/12 %s, smallest margin %+.4f, largest reading offset %.2f sigma%s" % (
            seed, "yes" if ok else "no ", worst, zw, "  <- chosen" if good else ""))
        if good:
            return seed


if __name__ == "__main__":
    main()
