#!/usr/bin/env python3
"""Every way the laser programme could be spent.

    python3 visit_study.py

A programme is six of the 36 trains. What a programme can give depends only on which of the six things the
records cannot supply it measures: each turbine, and one train of each group of changed pumps. So the
1,947,792 programmes fall into 64 kinds, by which of the six they cover. For each kind one programme is
carried through to a sheet, with whatever is left unmeasured filled in every way an engineer could fill it
from the records, and the best of those sheets is graded by the verifier's module. The 150 programmes that
cover all six are each carried through and graded, one by one.
"""
import itertools
import math
import sys

import common

FILL = dict(unmeasured=("rescale", "plain", "sibling", "delta", "factor"),
            turbine=("hot_check", "other", "thermal"))


def main():
    recs = common.records()
    ref = common.Variant(recs)
    groups = ref.groups()
    needs = [[tag] for tag in ref.turbines_to_measure()] + groups
    names = ["%s" % need[0] if len(need) == 1 else "%s (%d)" % ("/".join(sorted({ref.stationary(t)[1] for t in need})), len(need))
             for need in needs]
    covered_tags = {tag for need in needs for tag in need}
    others = [tag for tag in ref.tags if tag not in covered_tags]
    budget = ref.budget
    total = math.comb(len(ref.tags), budget)
    print("Programmes of %d trains from %d: %d. Graded by tests/grade_moves.py.\n" % (budget, len(ref.tags), total))
    print("The six things the records cannot supply: %s.\n" % "; ".join(names))

    def count(pattern):
        """Programmes that measure exactly the needs in `pattern` (at least one train of each, none of the rest)."""
        ways = {0: 1}
        for need, on in zip(needs, pattern):
            if not on:
                continue
            nxt = {}
            for used, n in ways.items():
                for k in range(1, len(need) + 1):
                    nxt[used + k] = nxt.get(used + k, 0) + n * math.comb(len(need), k)
            ways = nxt
        return sum(n * math.comb(len(others), budget - used) for used, n in ways.items() if used <= budget)

    rows, seen = [], 0
    for pattern in itertools.product((1, 0), repeat=len(needs)):
        n = count(pattern)
        seen += n
        if not n:
            continue
        plan = [need[0] for need, on in zip(needs, pattern) if on]
        plan += others[:budget - len(plan)]
        best = None
        for how, turbine in itertools.product(FILL["unmeasured"], FILL["turbine"]):
            sheet, _ = common.run(plan=plan, recs=recs, unmeasured=how, turbine=turbine)
            outcome = common.grade(sheet)
            if best is None or outcome.aligned > best[0].aligned:
                best = (outcome, how, turbine)
        rows.append((sum(pattern), pattern, n, best))
    assert seen == total, (seen, total)
    print("| measured | left unmeasured | programmes | best sheet, aligned of %d | trains it misses |" % len(ref.tags))
    print("|---|---|---|---|---|")
    winners = 0
    for _, pattern, n, (outcome, how, turbine) in sorted(rows, key=lambda r: (-r[0], [1 - p for p in r[1]])):
        on = [name for name, p in zip(names, pattern) if p]
        off = [name for name, p in zip(names, pattern) if not p]
        winners += n if outcome.accepted else 0
        lost = common.missed(outcome)
        print("| %s | %s | %d | %d | %s |" % (", ".join(on) or "nothing", ", ".join(off) or "nothing", n,
                                              outcome.aligned, " ".join(lost) if len(lost) <= 8 else "%d trains" % len(lost)))
    second = max(o.aligned for _, _, _, (o, _, _) in rows if not o.accepted)
    print("\nkinds of programme: %d" % len(rows))
    print("programmes of a kind whose best sheet leaves every train aligned: %d of %d" % (winners, total))
    print("the best any other programme can do: %d of %d" % (second, len(ref.tags)))

    full = [list(p) for p in itertools.product(*needs)]
    good = 0
    for plan in full:
        sheet, _ = common.run(plan=plan, recs=recs)
        good += common.grade(sheet).accepted
    print("\nprogrammes that measure all six with one train each: %d; carried through by the reference and "
          "accepted: %d" % (len(full), good))
    print("the reference's own programme: %s" % " ".join(ref.programme()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
