"""What the audit test order is worth: the reference method under a range of orders.

The budget is one test across ten chambers, placed once before any result is known. VC08's log holds a single
pumping time, so nothing in it separates a trapped volume from wall gas, and the test has to be spent there and
has to be one that answers that question: a residual gas analysis, which gives the composition outright, or a
helium test, which measures the real leak and so leaves what remains to be the trapped volume. A rate-of-rise
gives VC08's whole gas load but not what the gas is, and a throughput test gives a speed that was never in
doubt.

Every other chamber is settleable from the records - the two whose turbo has changed, from their pumpdowns either
side of the change; the one whose gauge certificate is out, from the speed its own throughput tests report; the
one whose constant gas load could be a leak or permeation, from how it follows the shop temperature - so a test
spent anywhere else is the test taken from where it was needed.

That is what makes the order load-bearing. The table below is the measurement, not an illustration: it covers
every order the budget allows - each of the four tests on each of the ten chambers - and placing no order at all,
and it counts how many of them carry the reference to a pass. Do not restate that count here; read it off
plan_sweep.txt, which is also where README.md gets it.

This script places each order through the real `vacwork` program and scores the reference's sheet, so the worth of
an order is measured and not assumed.

    python3 -I plan_sweep.py  > plan_sweep.txt
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as C                                                      # noqa: E402

T = lambda c, k: dict(chamber=c, test=k)                                # noqa: E731

# Exhaustive, not a selection. The budget is one test, so the whole space of orders is every test on every
# chamber, plus placing no order: 4 x 10 + 1. An earlier version of this script listed ten orders by hand while
# the prose claimed a result over all forty, which is a claim the study never made.
WORDS = {"rga": "an analysis", "rate-of-rise": "a rate-of-rise", "helium": "a helium test",
         "speed-test": "a speed test"}
PLANS = ([("no order at all", [])]
         + [("%s on %s" % (WORDS[k], c), [T(c, k)]) for c in C.IDS for k in sorted(WORDS)])


def main():
    assert len(PLANS) == len(C.IDS) * len(WORDS) + 1, "the sweep must cover every order"
    assert C.F.BUDGET == 1, "this sweep enumerates single-test orders; the budget is %d" % C.F.BUDGET
    rows = []
    good = []
    for name, plan in PLANS:
        tag = "sweep-" + name.replace(" ", "-")
        if plan:
            vac = C.place_order(plan, tag)
            answers = C.reference_answers(plan, tag)
        else:
            vac = None
            answers = C.reference_answers_without_order()
        r = C.score(answers)
        wrong = [cid for cid in C.IDS if not r["chambers"][cid]["ok"]]
        rows.append([name, len(plan), "%d/%d" % (r["npass"], len(C.IDS)),
                     "accepted" if r["accepted"] else "rejected", " ".join(wrong) or "-"])
        if r["accepted"]:
            good.append((name, plan))
    print(C.report("The reference method under different audit orders", rows,
                   ["order", "tests", "right", "verdict", "chambers wrong"]))
    print("budget: %d tests across %d chambers, placed once" % (C.F.BUDGET, len(C.IDS)))
    print("gate: at least %d of %d chambers right" % (C.G.GATE, len(C.IDS)))
    print("orders tried: %d (every test on every chamber, and no order)" % len(PLANS))
    print("")
    # Counted from the sweep rather than stated, so the number in the README cannot drift from the number here.
    print("ORDERS THAT WORK: %d of %d" % (len(good), len(PLANS)))
    for name, plan in good:
        print("  %s" % name)
    chambers = sorted({t["chamber"] for _n, p in good for t in p})
    print("chambers they are spent on: %s" % (" ".join(chambers) or "-"))
    print("")
    print("Every other order leaves the reference a chamber short. The chambers each failing order gets wrong")
    print("are in the table above, so what the test is worth is read off the sweep and not asserted.")
    C.cleanup()
    return 0


if __name__ == "__main__":
    sys.exit(main())
