"""The allowance. Four facts want a reading and the allowance pays for two; two of the four come out of the records
instead. This file sets out which, and what each plan costs.

    python3 authoring/evidence/budget.py > authoring/evidence/budget.txt
"""
import common as C

S = C.S

PLANS = [
    ("the analysis of the second stage and the weighing of 3B", dict(plan=("gc 2", "weigh 3B"))),
    ("the same two, booked in the other order", dict(plan=("weigh 3B", "gc 2"))),
    ("the analysis of the third stage and the weighing of 3B", dict(plan=("gc 3", "weigh 3B"))),
    ("both analyses, no weighing", dict(plan=("gc 2", "gc 3"))),
    ("both weighings, no analysis", dict(plan=("weigh 2B", "weigh 3B"))),
    ("the analysis of the first stage, which the records already hold, and the weighing",
     dict(plan=("gc 1", "weigh 3B"))),
    ("the weighing of 2B, whose difference the register gives, and the analysis",
     dict(plan=("gc 2", "weigh 2B"))),
    ("one reading: the analysis only", dict(plan=("gc 2",))),
    ("one reading: the weighing only", dict(plan=("weigh 3B",))),
    ("no readings at all", dict(plan=())),
]


def main():
    print("The allowance is %d readings. Four facts want one:\n" % S.BUDGET)
    for f in S.NEEDED:
        why = S.RECOVERABLE.get(f)
        print("  %-10s %s" % (f, "on record: %s" % why if why else "no record settles it"))
    print("\nSo the two readings go on %s, and the other two come out of the records.\n" % ", ".join(
        f for f in S.NEEDED if f not in S.RECOVERABLE))
    print("| plan | readings | right of 12 | what it costs |")
    print("|---|---|---|---|")
    for name, sw in PLANS:
        sheet, log = C.route(**sw)
        n, err, _ = C.grade(sheet)
        bad = C.failed_items(err)
        print("| %s | %s | %d | %s |" % (
            name, ", ".join(log) or "none", n,
            "nothing" if not bad else ", ".join("%s %s" % k for k in bad)))
    print()
    print("A plan that spends a reading on a fact the records already settle leaves one that they do not, and the\n"
          "allowance cannot be refilled: environment/rig/lab.py refuses the third reading (see reference_run.txt).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
