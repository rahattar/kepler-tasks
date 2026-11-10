"""Hedge study: can an assessment that leaves a choice unresolved pass by hedging it?

    python3 authoring/evidence/hedge_study.py > authoring/evidence/hedge_study.txt

For each choice an assessment has to make (A, the right one, against B, a tempting wrong one), the lives under A and
under B are computed with the same fitted law, crack by crack. A hedge can then do two things:
- across cracks: give some of the cracks that the choice affects A's interval and the others B's, so that whichever
  is true, some of them are right;
- within a crack: give one interval that lies inside the window under both A's life and B's life. That exists only
  when the two lives differ by less than the window's ratio, 0.50 / 0.40 = 1.25, and its tolerance to any other model
  error is the width of the overlap.
The best hedge takes every overlap it can, at the overlap's middle, and splits the remaining affected cracks between
A and B in the way that is worst for it (the hedger cannot know which of A and B is true). Its score is counted
against the sealed truth. With a gate of 15, one miss would pay for a split: an assessment that never resolves an
untested heat, BS 7910's PWHT level, the VSR credit or the site welds would pass by giving the two cracks the choice
affects one answer each. The gate is therefore 16.
"""
import numpy as np

import common as C

P = "paris"
REF = [(P, 0.20, "H1"), (P, 0.35, "H1"), (P, 0.45, "H1"), (P, 0.90, "H1"), (P, 0.70, "H4")]
MIRROR = [(P, 0.20, "H1"), (P, 0.35, "H1"), (P, 0.45, "H1"), (P, 0.90, "H1"), (P, 0.70, "H3")]


def lives(law, hf=None, **kw):
    saved = dict(law.hf)
    if hf:
        law.hf.update(hf)
    try:
        return {c: C.life(law, c, **kw) for c in C.IDS}
    finally:
        law.hf.clear()
        law.hf.update(saved)


def hedge(LA, LB):
    """the best hedge between lives LA and LB: its intervals for each of the two ways of splitting the uncovered
    cracks, and the cracks' overlaps"""
    covered, uncovered, width = {}, [], {}
    for c in C.IDS:
        lo = max(0.40 * LA[c], 0.40 * LB[c])
        hi = min(0.50 * LA[c], 0.50 * LB[c])
        if abs(np.log(LB[c] / LA[c])) < 0.01:
            covered[c] = C.FRACTION * LA[c]
        elif lo <= hi:
            covered[c] = 0.5 * (lo + hi)
            width[c] = hi / lo - 1
        else:
            uncovered.append(c)
    splits = []
    for first in ("A", "B"):
        iv = dict(covered)
        for i, c in enumerate(uncovered):
            use_a = (i % 2 == 0) == (first == "A")
            iv[c] = C.FRACTION * (LA[c] if use_a else LB[c])
        splits.append(iv)
    return splits, uncovered, width


def main():
    ref = C.examples_for_heats(C.fit(C.lab(REF)))
    mirror = C.examples_for_heats(C.fit(C.lab(MIRROR)))
    pairs = [
        ("heat H4 untested (H3 tested): as its grade-mate H3, or as H1", mirror, {}, mirror, dict(hf={"H4": 1.0})),
        ("heat H3 untested (H4 tested): as its grade-mate H4, or as H1", ref, {}, ref, dict(hf={"H3": 1.0})),
        ("heat H2: rate factor from E02, or as H1", ref, {}, ref, dict(hf={"H2": 1.0})),
        ("PWHT residual stress: 0.2 yield (transverse), or 0.3 yield (parallel)", ref, {}, ref, dict(resid=0.3)),
        ("residual stress from the certificate yield, or from the grade's specified minimum", ref, {}, ref,
         dict(resid="nominal")),
        ("vibratory stress relief: not credited, or credited as PWHT", ref, {}, ref, dict(vsr=True)),
        ("attachments welded on site after PWHT: as welded, or as PWHT", ref, {}, ref, dict(site_welds=False)),
        ("unloader 1's survey days: 28 operating, or all 35", ref, {}, ref, dict(stoppage=False)),
        ("unloader 2's grab change: ranges and cycles, or ranges only", ref, {}, ref, dict(cycles=False)),
    ]
    print(__doc__.split("\n\n", 1)[0].splitlines()[0])
    print("Shipped scenario (seed %d); window 0.40-0.50 of the true life; gate %d of 16.\n" % (C.SEED, C.F.GATE))
    worst_pass, passing = 0, []
    for nm, lawA, kwA, lawB, kwB in pairs:
        hfB = kwB.pop("hf", None)
        LA = lives(lawA, **kwA)
        LB = lives(lawB, hf=hfB, **kwB)
        affected = [c for c in C.IDS if abs(np.log(LB[c] / LA[c])) >= 0.01]
        splits, uncovered, width = hedge(LA, LB)
        scores = [C.grade(iv)[0] for iv in splits]
        n_a = C.grade({c: C.FRACTION * LA[c] for c in C.IDS})[0]
        best = min(scores)
        worst_pass = max(worst_pass, best)
        if best >= C.F.GATE:
            passing.append((nm, len(affected), min(LB[c] / LA[c] for c in affected), max(LB[c] / LA[c] for c in affected),
                            uncovered))
        print(nm)
        print("  A alone gets %d of 16. Affected cracks: %s (B/A life %.2f to %.2f)." %
              (n_a, " ".join(affected) or "none",
               min(LB[c] / LA[c] for c in affected) if affected else 1.0,
               max(LB[c] / LA[c] for c in affected) if affected else 1.0))
        if width:
            print("  One interval fits both on %s; overlap %.1f to %.1f percent of the interval, so the hedge tolerates "
                  "at most %.1f percent error elsewhere." % (" ".join(sorted(width)), 100 * min(width.values()),
                                                             100 * max(width.values()), 50 * min(width.values())))
        if uncovered:
            print("  No interval fits both on %s, so the hedge must split them." % " ".join(uncovered))
        print("  Best hedge: %d of 16 (worst case of the split); %s at gate %d.\n" %
              (best, "passes" if best >= C.F.GATE else "fails", C.F.GATE))
    print("At gate %d, every hedge that splits cracks between A and B loses at least one crack and fails." % C.F.GATE)
    for nm, k, lo, hi, unc in passing:
        print("The one choice a hedge survives is \"%s\": on all %d cracks it affects the two lives differ by only %.2f "
              "to %.2f, inside the window's ratio of 1.25, so a single interval fits both without splitting any crack; "
              "the choice is a sensitivity the window absorbs, and the hedge still needs every other part of the model "
              "right." % (nm, k, lo, hi))


if __name__ == "__main__":
    main()
