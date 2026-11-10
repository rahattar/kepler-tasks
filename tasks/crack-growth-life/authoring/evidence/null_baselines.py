"""Null baselines: answers that use no laboratory test at all. Each must be rejected, and every crack that one of them
gets right is listed, so that the cracks a trivial answer passes for free are identified one by one. 'x' marks a crack
whose interval is within 0.40-0.50 of its true life.

    python3 authoring/evidence/null_baselines.py > authoring/evidence/null_baselines.txt
"""
import numpy as np
import common as C


def nulls():
    out = []
    for nm, kw in (("handbook law and threshold, BS 7910 crack model and loading", {}),
                   ("handbook law and threshold, no Mk", dict(mk="none")),
                   ("handbook law and threshold, no residual stress", dict(resid="none")),
                   ("handbook law and threshold, survey taken at face value (35 days, ranges only)",
                    dict(stoppage=False, cycles=False))):
        iv, lv = C.assess(C.handbook_law, **kw)
        out.append((nm, iv, lv))
        for fv, lab in ((False, "the examples"), (True, "the examples at face value")):
            f = float(np.exp(np.mean([np.log(C.example_factor(C.handbook_law, e, face_value=fv, **kw))
                                      for e in C.EXAMPLES])))
            iv2, lv2 = C.assess(C.handbook_law, **dict(kw, fudge=f))
            out.append((nm + ", rate x%.2f fitted to %s" % (f, lab), iv2, lv2))
    med = float(np.median([C.TRUTH[c] for c in C.IDS]))
    out.append(("one interval for every crack (0.447 x the median true life, an oracle value)",
                {c: 0.447 * med for c in C.IDS}, {c: med for c in C.IDS}))
    return out


if __name__ == "__main__":
    print("Null baselines on the shipped scenario (seed %d); gate %d of 16.\n" % (C.SEED, C.F.GATE))
    print("%-4s %-92s %5s  %s" % ("", "null answer", "right", " ".join(c[1:] for c in C.IDS)))
    free = {c: [] for c in C.IDS}
    best_any = 0
    for i, (nm, iv, lv) in enumerate(nulls(), 1):
        n, ok, _ = C.grade(iv)
        for c in ok:
            free[c].append(i)
        best = max((sum(C.F.LO <= s * lv[c] / C.TRUTH[c] <= C.F.HI for c in C.IDS), s) for s in np.geomspace(0.05, 5, 4000))
        best_any = max(best_any, best[0])
        print("%2d   %-92s %2d/16  %s" % (i, nm, n, "  ".join("x" if c in ok else "." for c in C.IDS)))
        print("     best single multiplier on its lives (an oracle choice): %.3f gets %d" % (best[1], best[0]))
    print("\nCracks a trial-free answer gets right (the numbers are the null answers above that pass it):")
    print("  " + ", ".join("%s %s" % (c, ",".join(str(i) for i in free[c]) or "none") for c in C.IDS))
    print("\nNo trial-free answer gets more than %d of 16, even with the best multiplier chosen with the truth in hand; the "
          "gate is %d." % (best_any, C.F.GATE))
