"""Spread of sound methods on the shipped floor: every complete plan (the three lab boxes on firmware 2.4, one
vertical-drop elbow, one connector longer than 5 ft) in several visit orders, crossed with the choices a sound
method could make: the visit fit (weighted or unweighted least squares through the three readings, or exact
through minimum and maximum), how measured classes reach their unvisited members (amplitude at the horizontal
elbows' decay length, class mean, or a free two-parameter decay fit where a class has three measured members),
and the unknown 2024 zero of a 2.4 box in the 2024 report (none, half or all of today's).

    python3 method_spread.py > method_spread.txt
"""
import itertools
import numpy as np
import methods as M

LABS = M.LABS24
VERT = [t for t in M.TAGS if M.CLS[t] == "elbow_v"]
SAG = [t for t in M.TAGS if M.CLS[t] == "sagging"]


def main():
    rows = []
    for v, s in itertools.product(VERT, SAG):
        perms = list(itertools.permutations(LABS + [v, s]))[::15]          # 8 visit orders per plan
        for plan in perms:
            for fit in ("wls", "ols", "two"):
                for tr in ("decay", "mean", "free"):
                    for z in ("zero", "half", "full"):
                        e, worst, fails = M.grade(M.calibrate(list(plan), fit=fit, transfer=tr, z24=z))
                        rows.append((e, worst, v, s, fit, tr, z, " ".join(x[-2:] for x in plan)))
    E = np.array([r[0] for r in rows])
    print("sound methods on the shipped floor: %d calibrations (%d plans x 8 visit orders x 3 fits x 3 transfers "
          "x 3 2024-zero assumptions)" % (len(rows), len(VERT) * len(SAG)))
    print("worst-box error: min %.1f %%, median %.1f %%, 95th percentile %.1f %%, max %.1f %%; fail at 10 %%: %d"
          % (100 * E.min(), 100 * np.median(E), 100 * np.percentile(E, 95), 100 * E.max(), int((E > 0.10).sum())))
    print("\nworst-box error by choice (max over everything else)")
    for name, i, levels in (("vertical drop visited", 2, VERT), ("long connector visited", 3, SAG),
                            ("visit fit", 4, ("wls", "ols", "two")), ("class transfer", 5, ("decay", "mean", "free")),
                            ("2024 zero of a 2.4 box", 6, ("zero", "half", "full"))):
        print("  %-24s " % name + "  ".join("%s %.1f %%" % (str(l)[-2:] if l.startswith("VAV") else l,
                                                             100 * max(r[0] for r in rows if r[i] == l)) for l in levels))
    print("\nten worst calibrations")
    for r in sorted(rows, reverse=True)[:10]:
        print("  %.1f %% at %s | visits %s | fit %s, transfer %s, 2024 zero %s" % (100 * r[0], r[1], r[7], r[4], r[5], r[6]))
    ref = M.grade(M.calibrate(M.REFERENCE_PLAN))
    print("\nreference (visits %s; wls, decay, half): worst %.1f %% at %s"
          % (" ".join(x[-2:] for x in M.REFERENCE_PLAN), 100 * ref[0], ref[1]))


if __name__ == "__main__":
    main()
