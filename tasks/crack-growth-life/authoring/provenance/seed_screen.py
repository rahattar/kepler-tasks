"""How the laboratory's scatter seed was chosen.

    python3 authoring/provenance/seed_screen.py [FIRST LAST] > authoring/evidence/seed_screen.txt

The seed drives only the laboratory's scatter: each test's draws come from numpy's generator seeded with
(seed, first slot index, round(1000 R), heat number), so every agent that requests the same test in the same slot
gets the same report. The crack lives, the documents and the verifier do not depend on it.

With ten points and 8 percent scatter, a test's mean offset from its curve has a standard deviation of 2.5 percent,
and a heat's rate factor is often read from a single test, so an unlucky seed can fail a sound campaign on scatter
alone. The shipped seed was chosen from 9101-10100 in two stages:
1. Scatter screen: over every Paris and threshold test at R = 0.05, 0.10, ..., 0.90, in any slot and on any heat, the
   largest standardised mean offset of the draws is at most 2.75 sigma and the largest slope offset at most 3.5.
   (9101, the first candidate, fails: an S460NL test at R 0.80 in slot 5 sits 3.46 sigma high.)
2. Sound campaigns: five sound solutions are run on each screened seed (the reference; the campaigns of two probe
   agents, H1 .80 .10 .40 + H2 .80 + H3 .80 and H1 .80 .10 .40 + H3 .80 + H4 .80, fitted as the reference fits; a
   method-spread campaign; and authoring/evidence/independent.py). Of the seeds where all five get 16 of 16, the one
   whose worst interval / life lies closest to the middle of the window (smallest |ln(ratio / 0.447)|) is shipped.
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "evidence"))
import fcgsim as F  # noqa: E402
import common as C  # noqa: E402
import independent as I  # noqa: E402

RS = np.round(np.arange(0.05, 0.901, 0.05), 2)
HEATS = ("H1", "H2", "H3", "H4")
P = "paris"
BATTERY = {"ref": [(P, .20, "H1"), (P, .35, "H1"), (P, .45, "H1"), (P, .90, "H1"), (P, .70, "H4")],
           "x3": [(P, .80, "H1"), (P, .10, "H1"), (P, .80, "H2"), (P, .40, "H1"), (P, .80, "H3")],
           "x1": [(P, .80, "H1"), (P, .10, "H1"), (P, .80, "H3"), (P, .80, "H4"), (P, .40, "H1")],
           "ms": [(P, .10, "H1"), (P, .25, "H1"), (P, .45, "H1"), (P, .90, "H1"), (P, .50, "H3")]}


def points(kind, R, heat):
    top = min(45.0, F.KMAX_LAB * (1 - R))
    dK = np.geomspace(top / 3.75, top, 10) if kind == "paris" else np.geomspace(min(14.0, top), float(F.dkth(R)) * 1.02, 14)
    return int((F.true_rate(heat)(dK, np.full_like(dK, R)) > 1e-11).sum())


def worst(seed):
    """largest |mean offset| per heat and largest |slope offset| over the grid, in standard deviations"""
    zmean = {h: 0.0 for h in HEATS}
    zslope = 0.0
    for R in RS:
        for h in HEATS:
            for idx in range(1, 6):
                for kind in (("paris", "threshold") if idx <= 3 else ("paris",)):
                    n = points(kind, R, h)
                    if n < 3:
                        continue
                    z = np.random.default_rng([seed, idx, int(round(R * 1000)), int(h[1])]).normal(0, 1, n)
                    x = np.arange(n) - (n - 1) / 2
                    zmean[h] = max(zmean[h], abs(z.mean()) * np.sqrt(n))
                    zslope = max(zslope, abs((z * x).sum()) / np.sqrt((x * x).sum()))
    return zmean, zslope


def battery(seed):
    out, all16, w = [], True, 0.0
    for nm, camp in BATTERY.items():
        law = C.examples_for_heats(C.fit(C.lab(camp, seed=seed)))
        iv, _ = C.assess(law)
        n, _, r = C.grade(iv)
        out.append("%s %d %.3f-%.3f" % (nm, n, min(r.values()), max(r.values())))
        all16 &= n == 16
        w = max(w, max(abs(np.log(v / 0.447)) for v in r.values()))
    law = I.fit_closure(C.lab(I.CAMPAIGN, seed=seed))
    n, _, r = C.grade({c: 0.45 * I.life(law, c) for c in C.IDS})
    out.append("ind %d %.3f-%.3f" % (n, min(r.values()), max(r.values())))
    all16 &= n == 16
    w = max(w, max(abs(np.log(v / 0.447)) for v in r.values()))
    return all16, w, out


def main(first=9101, last=10100):
    zm, zs = worst(9101)
    print("seed 9101: largest mean offset %.2f sigma (%s), slope %.2f; fails the screen" %
          (max(zm.values()), ", ".join("%s %.2f" % kv for kv in zm.items()), zs))
    rows = []
    for s in range(first, last + 1):
        zm, zs = worst(s)
        if max(zm.values()) > 2.75 or zs > 3.5:
            continue
        all16, w, out = battery(s)
        rows.append((s, all16, w))
        print("seed %d zmax %.2f slope %.2f all16 %s worst %.3f | %s" % (s, max(zm.values()), zs, all16, w, " | ".join(out)),
              flush=True)
    good = [r for r in rows if r[1]]
    best = min(good, key=lambda r: r[2])
    print("\nseeds %d-%d: %d pass the scatter screen, %d of them with all five sound solutions at 16 of 16; chosen: %d "
          "(worst |ln(interval/life / 0.447)| %.3f)" % (first, last, len(rows), len(good), best[0], best[2]))


if __name__ == "__main__":
    main(*map(int, sys.argv[1:3])) if len(sys.argv) > 2 else main()
