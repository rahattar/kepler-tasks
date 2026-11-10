"""Which five-visit campaigns can pass. Every five-box campaign drawn from a pool of sixteen boxes that covers each
inlet and controller class on the floor is calibrated with the reference's inference; a class nobody visited
takes each defensible fallback in turn (vertical drops at factory K or on the horizontal-elbow model; long
connectors as ordinary flex or at the kinked factor; an unvisited 2.4 lab at the median of the measured 2.4 zeros
or at the mean of the visited labs), and the campaign counts as passing if any combination passes.

    python3 campaign_study.py > campaign_study.txt
"""
import itertools
from collections import Counter
import methods as M

POOL = ["VAV-3-36", "VAV-3-37", "VAV-3-38",          # labs on firmware 2.4 (never shut)
        "VAV-3-30", "VAV-3-34",                      # kinked connectors (punch list), offices
        "VAV-3-25", "VAV-3-28", "VAV-3-27",          # vertical drops (25 on 2.4; 27 in the 2024 report)
        "VAV-3-31", "VAV-3-35",                      # connectors longer than 5 ft
        "VAV-3-32", "VAV-3-39",                      # east flex within specification (39 a lab on 3.1)
        "VAV-3-04",                                  # straight inlet, failed auto-zero
        "VAV-3-17", "VAV-3-20", "VAV-3-21"]          # west elbow (short run), west flex, east straight


def passes(plan, lab_zeros=("fleet", "labs")):
    cls = {M.CLS[t] for t in plan}
    vopts = ["own"] if "elbow_v" in cls else ["factory", "horizontal"]
    sopts = ["own"] if "sagging" in cls else ["flex", "kinked"]
    lopts = ["fleet"] if set(M.LABS24) <= set(plan) else list(lab_zeros)
    best = None
    for v, s, lz in itertools.product(vopts, sopts, lopts):
        e = M.grade(M.calibrate(list(plan), vertical=v, sag=s, lab_zero=lz))[0]
        best = e if best is None else min(best, e)
    return best


def label(plan):
    c = Counter()
    for t in plan:
        k = "lab" + t[-2:] if t in M.LABS24 else M.CLS[t]
        c[k] += 1
    return " + ".join("%s%s" % (k, "" if n == 1 else " x%d" % n) for k, n in sorted(c.items()))


def main():
    camps = list(itertools.combinations(POOL, 5))
    res = [(passes(p), p) for p in camps]
    ok = [p for e, p in res if e <= 0.10]
    print("campaigns of five distinct boxes from a pool of %d: %d; passing with some defensible fallback: %d"
          % (len(POOL), len(camps), len(ok)))
    need = lambda p: set(M.LABS24) <= set(p) and any(M.CLS[t] == "elbow_v" for t in p) and \
        any(M.CLS[t] == "sagging" for t in p)
    print("passing campaigns that visit the three 2.4 labs, a vertical drop and a long connector: %d of %d"
          % (sum(need(p) for p in ok), len(ok)))
    print("campaigns with that coverage that fail: %d" % sum(need(p) and e > 0.10 for e, p in res))
    print("\npassing campaigns:")
    for p in ok:
        print("  %s   (%s)" % (" ".join(t[-2:] for t in p), label(p)))
    print("\nbest worst-box error of the failing campaigns, by what they leave out")
    groups = {}
    for e, p in res:
        if e <= 0.10:
            continue
        miss = [("lab" + t[-2:]) for t in M.LABS24 if t not in p]
        if not any(M.CLS[t] == "elbow_v" for t in p):
            miss.append("vertical drop")
        if not any(M.CLS[t] == "sagging" for t in p):
            miss.append("long connector")
        key = ", ".join(miss) if miss else "(nothing)"
        groups.setdefault(key, []).append(e)
    for key, es in sorted(groups.items(), key=lambda kv: (len(kv[0]), kv[0])):
        print("  missing %-46s %4d campaigns, best %5.1f %%" % (key, len(es), 100 * min(es)))
    extra = [p for e, p in res if e > 0.10 and passes(p, lab_zeros=("zero",)) <= 0.10]
    print("\nnot a method: also giving an unvisited 2.4 lab offset 0 rescues %d more campaign(s); all of them skip "
          "lab 37, whose zero happens to be small" % len(extra))
    assert all(set(M.LABS24) - set(p) == {"VAV-3-37"} for p in extra)


if __name__ == "__main__":
    main()
