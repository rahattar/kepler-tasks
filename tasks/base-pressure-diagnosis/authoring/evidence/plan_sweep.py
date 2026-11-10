"""What the audit test order is worth: the reference method under a range of orders.

The budget is four tests across ten chambers, placed once before any result is known. Two chambers, VC06 and VC08,
hold too few pumpdowns for their own records to settle their cause, so an order that buys them nothing leaves the
reference guessing on them. Two more, VC09 and VC10, have had their turbo change since their last speed test; for
those a test is a convenience rather than a necessity, because their speed can be had from their own records
before the change.

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
    ("the thin logs only", [T("VC06", "rga"), T("VC08", "rga")]),
    ("the reference order", C.REFERENCE_PLAN),
    ("rise for the thin logs", [T("VC06", "rate-of-rise"), T("VC08", "rate-of-rise"),
                                T("VC09", "speed-test"), T("VC10", "speed-test")]),
    ("helium for the thin logs", [T("VC06", "helium"), T("VC08", "helium"),
                                  T("VC09", "speed-test"), T("VC10", "speed-test")]),
    ("the changed turbos only", [T("VC09", "speed-test"), T("VC10", "speed-test")]),
    ("four chambers that need nothing", [T("VC01", "rga"), T("VC02", "rga"),
                                         T("VC03", "rga"), T("VC04", "rga")]),
    ("everything on one chamber", [T("VC06", "rga"), T("VC06", "helium"),
                                   T("VC06", "rate-of-rise"), T("VC06", "speed-test")]),
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
