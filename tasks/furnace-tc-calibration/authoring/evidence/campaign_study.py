"""Which allocations of the three TC-wafer steps can pass. Every set of three distinct (furnace, step) pairs from the
24 possible (8 furnaces x 600, 850, 1050 C) is calibrated with the engine's inference, run in furnace order; a
quantity no step settles takes each defensible fallback in turn (F8: its factory values or the 2025 T-200 offsets;
F5: its 2025 offsets or the 2025 T-200 offsets of the other quartz furnaces; a doping furnace with unknown drift: the
bay median or the other doping furnace's drift), and the allocation counts as passing if any combination passes.
F6's drift comes from its hold carried forward by the growth in its trend in every case. Figures are worst-zone
|wafer - setpoint| in K; acceptance 2 K.

    python3 campaign_study.py > campaign_study.txt
"""
import itertools
from collections import defaultdict
import methods as M

PAIRS = [(f, s) for f in M.FURN for s in (600, 850, 1050)]


def as_plan(pairs):
    by = defaultdict(list)
    for f, s in pairs:
        by[f].append(s)
    return [(f, tuple(sorted(by[f]))) for f in M.FURN if f in by]


def best(plan):
    out = None
    for f8 in ("fat", "fleet"):
        for f5 in ("2025", "fleet"):
            for unknown in ("median", "other"):
                e = M.grade(M.calibrate(plan, f8=f8, f5=f5, unknown=unknown))[0]
                out = e if out is None else min(out, e)
    return out


def coverage(plan):
    """What a plan leaves unsettled, from the records' point of view."""
    s = dict(plan)
    proc = lambda f: bool(set(s.get(f, ())) & {850, 1050})
    miss = []
    if not proc("F5"):
        miss.append("F5 offset (new tube)")
    if not proc("F8"):
        miss.append("F8 offset (no site calibration)")
    f3 = set(s.get("F3", ()))
    clean_sic = any(proc(f) for f in ("F2", "F7"))
    f3_ok = 1050 in f3 or (600 in f3 and (bool(f3 & {850}) or clean_sic)) or (850 in f3 and clean_sic)
    if not f3_ok:
        miss.append("F3 drift and offset")
    return miss


def main():
    combos = list(itertools.combinations(PAIRS, 3))
    res = [(best(as_plan(c)), as_plan(c)) for c in combos]
    ok = [p for e, p in res if e <= 2.0]
    print("allocations of the three steps over 8 furnaces x 3 steps: %d; passing with some defensible fallback: %d"
          % (len(combos), len(ok)))
    print("passing allocations that settle F5, F8 and F3: %d of %d (with three steps F3 is settled only by its own "
          "1050 C step, split with its 850 C trend)" % (sum(not coverage(p) for p in ok), len(ok)))
    print("allocations with that coverage that fail: %d" % sum(not coverage(p) and e > 2.0 for e, p in res))
    print("best failing allocation: %.2f K" % min(e for e, p in res if e > 2.0))
    print("\npassing allocations:")
    for p in ok:
        print("  " + " ".join("%s@%s" % (f, "+".join(map(str, s))) for f, s in p))
    groups = defaultdict(list)
    for e, p in res:
        if e > 2.0:
            groups[", ".join(coverage(p)) or "(nothing)"].append(e)
    print("\nbest worst-zone error of the failing allocations, by what they leave unsettled")
    for k, es in sorted(groups.items(), key=lambda kv: (kv[0].count(","), kv[0])):
        print("  %-62s %5d allocations, best %5.2f K" % (k, len(es), min(es)))


if __name__ == "__main__":
    main()
