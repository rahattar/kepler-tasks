#!/usr/bin/env python3
"""The design rules of relief-valve-adequacy, recomputed from the sealed definition and checked.

The rules are what the task was built to, not observations of it. Any change to isim.py that breaks one of them
makes this exit non-zero.

    python3 tune.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import isim as S  # noqa: E402

CONTENDER_MARGIN = 0.05     # the governing case must beat the next by this much
VERDICT_MARGIN = 0.10       # some condition must decide each finding by this much
IDENTIFY_MARGIN = 0.10      # an identified quantity either differs from its data sheet by this much
MATCH_MARGIN = 0.01         # or matches it within this much
INADEQUATE_RANGE = (3, 6)


def rules():
    t = S.truth()
    out = []

    # 1 every contingency name governs somewhere
    governed = sorted({v["case"] for v in t.values()})
    out.append(("every contingency name governs at least one valve",
                len(governed) == len(S.CASES),
                "%d of %d: %s" % (len(governed), len(S.CASES), ", ".join(governed))))

    # 2 the governing case beats the next by a margin
    worst, at = 1.0e9, None
    for vid, r in t.items():
        others = [a for c, a in r["all_cases"].items() if a is not None and c != r["case"]]
        m = (r["area"] / max(others) - 1.0) if others else 1.0e9
        if m < worst:
            worst, at = m, vid
    out.append(("the governing case beats the next contender by %.0f per cent" % (100 * CONTENDER_MARGIN),
                worst >= CONTENDER_MARGIN, "worst %+.1f%% at %s" % (100 * worst, at)))

    # 3 every finding is decided by a margin
    worst, at = 1.0e9, None
    for vid, r in t.items():
        it = S.ITEMS[vid]
        cands = [abs(r["installed"] / r["area"] - 1.0)]
        limit = S.INLET_LIMIT * it["set_now"]
        if r["drop"] > 0.0:
            cands.append(abs(r["drop"] / limit - 1.0))
        m = max(cands)
        if m < worst:
            worst, at = m, vid
    out.append(("every finding is decided by %.0f per cent on some condition" % (100 * VERDICT_MARGIN),
                worst >= VERDICT_MARGIN, "worst %+.1f%% at %s" % (100 * worst, at)))

    # 4 the identified control valve coefficients are either clearly different or clearly the same
    bad = []
    for tag, c in S.CV.items():
        rel = c["actual"] / c["sheet"] - 1.0
        if not (abs(rel) >= IDENTIFY_MARGIN or abs(rel) <= MATCH_MARGIN):
            bad.append("%s %+.1f%%" % (tag, 100 * rel))
    out.append(("each control valve coefficient differs from its data sheet by %.0f per cent or matches "
                "within %.0f per cent" % (100 * IDENTIFY_MARGIN, 100 * MATCH_MARGIN),
                not bad, ", ".join(bad) if bad else "all five clear"))

    # 5 at least one coefficient matches its data sheet, so the sheets are not uniformly suspect
    same = [t_ for t_, c in S.CV.items() if abs(c["actual"] / c["sheet"] - 1.0) <= MATCH_MARGIN]
    out.append(("at least one control valve matches its data sheet", len(same) >= 1, ", ".join(same)))

    # 6 the reboiler coefficient-area differs from the data sheet basis
    worst = 1.0e9
    for name in S.REB:
        ts = S.sat("steam", S.REB[name]["steam_barg"] + S.ATM, "t")
        design = S.REB[name]["design_kw"] / (ts - S.REB[name]["bot_normal_C"])
        worst = min(worst, abs(S.reb_ua(name) / design - 1.0))
    out.append(("the reboiler coefficient-area differs from its data sheet basis by %.0f per cent"
                % (100 * IDENTIFY_MARGIN), worst >= IDENTIFY_MARGIN, "worst %+.1f%%" % (100 * worst)))

    # 7 the findings are mixed
    n_bad = sum(1 for v in t.values() if v["verdict"] == "inadequate")
    out.append(("between %d and %d valves are inadequate" % INADEQUATE_RANGE,
                INADEQUATE_RANGE[0] <= n_bad <= INADEQUATE_RANGE[1], "%d of %d" % (n_bad, len(t))))

    # 8 every required area sits inside the orifice table
    lo, hi = min(S.ORIFICE.values()), max(S.ORIFICE.values())
    worst = max(v["area"] for v in t.values())
    out.append(("no required area exceeds the largest orifice in the table", worst <= hi,
                "largest %.0f against %.0f" % (worst, hi)))

    # 9 the feed meter's bias is big enough to matter and small enough to be plausible
    k = (S.RD_CONFIG / S.RD_NOW) ** 0.5
    out.append(("the feed meter indication is 2 to 8 per cent from the truth",
                0.02 <= abs(1.0 - k) <= 0.08, "%.1f per cent" % (100 * abs(1.0 - k))))

    return out


def main():
    ok = True
    for rule, passed, detail in rules():
        print("%s %-96s %s" % ("pass" if passed else "FAIL", rule, detail))
        ok = ok and passed
    print("\n%s" % ("all design rules hold" if ok else "a design rule is broken"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
