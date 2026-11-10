"""Null baselines: answers that use no trial at all. Each must be rejected, and every joint that one of them gets right
is listed, so that the joints a trivial answer passes for free are identified one by one.

    python3 authoring/evidence/null_baselines.py > authoring/evidence/null_baselines.txt
"""
import numpy as np
import common as C

REC = C.record_ratios()
IDS = C.IDS


def hb(j):
    return C.K_HB * C.d_m(j) * C.target_N(j)


def rec(j):
    return REC[C.SCHED[j]["flange_class"]]


def nulls():
    out = [("handbook K, no pattern ratio (the rig's default torque)", {j: hb(j) for j in IDS}),
           ("handbook K with the records' pattern ratios", {j: hb(j) / rec(j) for j in IDS})]
    for s in (0.8, 0.85, 0.9, 0.95, 1.05, 1.1, 1.15):
        out.append(("handbook K scaled by %.2f, with the records' pattern ratios" % s,
                    {j: s * hb(j) / rec(j) for j in IDS}))
    for eid, k in sorted(C.record_k().items()):
        out.append(("the record %s's single-bolt K (%.3f) for every joint, records' ratios" % (eid, k),
                    {j: k * C.d_m(j) * C.target_N(j) / rec(j) for j in IDS}))
    out.append(("one torque for all joints (the median of the handbook torques)",
                {j: float(np.median([hb(i) for i in IDS])) for j in IDS}))
    return out


def right(torques):
    n, bad, errs, _ = C.grade(torques)
    return n, [j for j in IDS if j not in bad]


if __name__ == "__main__":
    print("Null baselines on the shipped scenario (seed %d); gate %d of 16. 'x' marks a joint the answer gets right.\n"
          % (C.SEED, C.J.GATE))
    print("%-74s %5s  %s" % ("null answer", "right", " ".join(j[1:] for j in IDS)))
    free = {j: [] for j in IDS}
    for i, (name, t) in enumerate(nulls(), 1):
        n, ok = right(t)
        for j in ok:
            free[j].append(i)
        print("%2d %-71s %2d/16  %s" % (i, name, n, "  ".join("x" if j in ok else "." for j in IDS)))

    print("\nBest single constant (the strongest trial-free answer), searched over multipliers 0.50 to 1.60 in steps of 0.005:")
    for label, f in (("c x handbook torque", lambda j, c: c * hb(j)),
                     ("c x handbook torque / records' pattern ratio", lambda j, c: c * hb(j) / rec(j)),
                     ("c x the records' mean K x d x target / records' ratio",
                      lambda j, c: c * np.mean(list(C.record_k().values())) * C.d_m(j) * C.target_N(j) / rec(j))):
        best = max((right({j: f(j, c) for j in IDS})[0], c) for c in np.arange(0.5, 1.6, 0.005))
        _, ok = right({j: f(j, best[1]) for j in IDS})
        print("  %-52s best %d/16 at c = %.3f: %s" % (label, best[0], best[1], ", ".join(ok)))

    print("\nJoints a trial-free answer gets right (the numbers are the null answers above that pass it), and the interval")
    print("of multipliers c for which c x handbook torque / records' ratio gets the joint right:")
    grid = np.arange(0.5, 2.0, 0.001)
    ok_c = {}
    for j in IDS:
        ok_c[j] = [c for c in grid if right({i: (c * hb(i) / rec(i) if i == j else hb(i)) for i in IDS})[1].count(j)]
        lo, hi = (min(ok_c[j]), max(ok_c[j])) if ok_c[j] else (float("nan"), float("nan"))
        print("  %s  nulls %-12s  c in [%.3f, %.3f]" % (j, ", ".join(str(i) for i in free[j]) or "none", lo, hi))
    overlap = max(sum(1 for j in IDS if ok_c[j] and min(ok_c[j]) <= c <= max(ok_c[j])) for c in grid)
    never = [j for j in IDS if not free[j]]
    print("\nEvery joint is passed by some multiple of the handbook torque, since each has its own +/-6 percent window; the")
    print("intervals are spread over c = %.2f to %.2f and at most %d of them overlap, so no single trial-free answer gets"
          % (min(min(v) for v in ok_c.values() if v), max(max(v) for v in ok_c.values() if v), overlap))
    print("more than %d of 16 right against the %d required. Of the fixed null answers listed, none passes %s." % (
        overlap, C.J.GATE, ", ".join(never)))
