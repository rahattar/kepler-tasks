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

That is what makes the order load-bearing: there are forty ways to spend it and two of them work.

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

PLANS = [
    ("no order at all", []),
    ("an analysis on VC08", C.REFERENCE_PLAN),
    ("a rate-of-rise on VC08", [T("VC08", "rate-of-rise")]),
    ("a helium test on VC08", [T("VC08", "helium")]),
    ("a speed test on VC08", [T("VC08", "speed-test")]),
    ("an analysis on VC06", [T("VC06", "rga")]),
    ("an analysis on VC01", [T("VC01", "rga")]),
    ("a rate-of-rise on VC01", [T("VC01", "rate-of-rise")]),
    ("a helium test on VC04", [T("VC04", "helium")]),
    ("a speed test on VC09", [T("VC09", "speed-test")]),
]


def main():
    rows = []
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
    print(C.report("The reference method under different audit orders", rows,
                   ["order", "tests", "right", "verdict", "chambers wrong"]))
    print("budget: %d tests across %d chambers, placed once" % (C.F.BUDGET, len(C.IDS)))
    print("gate: at least %d of %d chambers right" % (C.G.GATE, len(C.IDS)))
    print("")
    print("An order that buys VC06 and VC08 nothing leaves the reference without the composition it needs on")
    print("them; an order that spends every test on chambers whose records already settle them wastes the lot.")
    C.cleanup()
    return 0


if __name__ == "__main__":
    sys.exit(main())
