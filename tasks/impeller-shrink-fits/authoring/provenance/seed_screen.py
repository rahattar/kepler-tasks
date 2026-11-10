"""Chooses the laboratory seed: the first seed from 5301 on which (1) no reading a plausible plan could draw is more
than 2.5 standard deviations from its mean (as test 1, 2 or 3: FV520B at 250-400 C, Ti-6Al-4V at 270-310 C, 42CrMo4
at 180-240 C and the rotor steel at 150-250 C, each in steps of 5 C), (2) the sound plans of method_spread.py (all but the 2 % allowance) all get 8 of 8, and (3) the defective routes of
route_study.py all fail. Condition (3) matters for the two routes that the laboratory's scatter can rescue: FV520B
tested at S2's 240 C limit and extrapolated to S6, and the right tests in part order with each clearance-limited bore
only one standard deviation of the stated repeatability inside its limit; each gets 8 of 8 on some seeds.
The seed drives only the laboratory's scatter.

    python3 authoring/provenance/seed_screen.py
"""
import math
import os
import sys

import numpy as np

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "evidence"))
import common as C  # noqa: E402
import method_spread as M  # noqa: E402
import route_study as R  # noqa: E402

S = C.S
PLANS = [kw for name, kw in M.METHODS if "2 %" not in name]
TEMPS = {"FV520B": range(250, 401, 5), "Ti-6Al-4V": range(270, 311, 5), "42CrMo4": range(180, 241, 5),
         "26NiCrMoV14-5": range(150, 251, 5)}


def zmax(seed):
    z = 0.0
    for idx in (1, 2, 3):
        for mi, mat in enumerate(S.LABMAT):
            for T in TEMPS[mat]:
                rng = np.random.default_rng([seed, idx, 2, mi, T])
                v = S.lab_cte(S.LABMAT[mat], T, rng)
                z = max(z, abs(math.log(v / (S.cte(S.LABMAT[mat], T) * 1e6))) / S.NOISE_CTE)
    return z


def main():
    for seed in range(5301, 5600):
        z = zmax(seed)
        if z > 2.5:
            print("seed %d: largest reading offset %.2f sigma" % (seed, z))
            continue
        res = [C.grade(C.solve_route(seed=seed, **kw)[0]) for kw in PLANS]
        allok = all(r[0] == 8 for r in res)
        if allok:
            rescued = [name for name, kw in R.ROUTES if C.grade(C.solve_route(seed=seed, **kw)[0])[0] == 8]
            if rescued:
                print("seed %d: largest reading offset %.2f sigma, sound plans 8 of 8, but a defective route passes: %s" % (
                    seed, z, "; ".join(rescued)))
                continue
        worst = min(min(C.least(r[1], q) for q in ("ret", "clear")) for r in res)
        print("seed %d: largest reading offset %.2f sigma, sound plans all 8 of 8 %s, smallest retention/clearance "
              "margin %+.4f%s" % (seed, z, "yes" if allok else "no ", worst, "  <- chosen" if allok else ""))
        if allok:
            return seed


if __name__ == "__main__":
    main()
