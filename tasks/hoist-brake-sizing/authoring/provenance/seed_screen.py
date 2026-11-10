"""How the laboratory's scatter seed was chosen.

    python3 authoring/provenance/seed_screen.py [FIRST LAST] > authoring/evidence/seed_screen.txt

The seed drives only the laboratory's scatter: each test's readings come from numpy's generator seeded with
(seed, test number, key), the key being the temperature and lining or the size, setting and switching, so every
agent that requests the same test in the same place of its plan gets the same report. The hoists, the documents and
the verifier do not depend on it.

A friction test's mean has a scatter of 2 / sqrt(8) = 0.7 percent and an engagement test's 3 / sqrt(5) = 1.3 percent,
and a lining's friction at a temperature is often read from one test, so an unlucky draw could move a sound
selection. The seed is the first one from FIRST (default 7301, the seed of every probe run) that passes two stages:
1. Scatter screen: over every friction test at 20, 30, ..., 320 C on either lining and every engagement test of any
   size at 50, 55, ..., 100 % with either switching, each in any of the 8 places of a plan, the largest standardised
   mean offset of the readings is at most 3.0 sigma for friction and 3.3 sigma for engagement.
2. Sound selections: the reference, its tests in reverse order, the method spread's 10 C lower and 10 C higher
   plans, and the reference tests with a PCHIP fit all meet every requirement on all 12 hoists.
authoring/evidence/independent.py is then run on the chosen seed (independent.txt).
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "evidence"))
import hbsim as S  # noqa: E402
import common as C  # noqa: E402
import method_spread as MS  # noqa: E402

TEMPS = np.arange(20, 321, 10)
SETS = np.arange(50, 101, 5)
ZF, ZE = 3.0, 3.3


def scatter(seed):
    zf = ze = 0.0
    for idx in range(1, S.BUDGET + 1):
        for lin in ("O1", "O2"):
            for T in TEMPS:
                z = np.random.default_rng([seed, idx] + C.lab_key(C.F(int(T), lin))).normal(0, 1, S.FRICTION_POINTS)
                zf = max(zf, abs(z.mean()) * np.sqrt(S.FRICTION_POINTS))
        for size in S.SIZES:
            for s in SETS:
                for sw in ("AC", "DC"):
                    z = np.random.default_rng([seed, idx] + C.lab_key(C.E(size, int(s), sw))).normal(0, 1, S.ENGAGE_POINTS)
                    ze = max(ze, abs(z.mean()) * np.sqrt(S.ENGAGE_POINTS))
    return zf, ze


BATTERY = [("reference", dict(plan=C.REF_PLAN)), ("reversed", dict(plan=C.REF_PLAN[::-1])),
           ("lower", dict(plan=MS.LOW)), ("higher", dict(plan=MS.HIGH)), ("pchip", dict(plan=C.REF_PLAN, cls=C.Pchip))]


def main(first=7301, last=8300):
    print(__doc__.split("\n\n")[0].strip())
    print("Candidates %d-%d, in order.\n" % (first, last))
    for seed in range(first, last + 1):
        zf, ze = scatter(seed)
        if zf > ZF or ze > ZE:
            print("seed %d: scatter screen fails (friction %.2f sigma, engagement %.2f sigma)" % (seed, zf, ze), flush=True)
            continue
        res = []
        for nm, kw in BATTERY:
            picks, n, fails = C.run(seed=seed, **kw)
            worst = min(C.truth_margin(h, p[1], p[2]) for h, p in picks.items())
            res.append((nm, n, worst, fails))
        ok = all(n == 12 for _, n, _, _ in res)
        print("seed %d: scatter %.2f / %.2f sigma; %s" % (seed, zf, ze, "; ".join(
            "%s %d/12 (smallest true margin %+.3f)%s" % (nm, n, w, (" " + " ".join(f)) if f else "") for nm, n, w, f in res)),
            flush=True)
        if ok:
            print("\nShipped seed: %d (the first candidate passing both stages)." % seed)
            return seed
    print("no seed found")


if __name__ == "__main__":
    a = [int(x) for x in sys.argv[1:3]]
    main(*a)
