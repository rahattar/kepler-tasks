"""Null baselines: selections made without the laboratory or without modelling the hoists, and the hoists each one
gets right by chance (per-hoist free passes).

    python3 authoring/evidence/null_baselines.py > authoring/evidence/null_baselines.txt

Each hoist is graded on its own, so a trial-free selection can be right on some hoists. The answers tried:
1. One brake for all twelve hoists: every catalogue size at every setting from 50 to 100, the best chosen with the
   truth in hand.
2. Holding alone: on each hoist the smallest size, and the lowest setting, whose rated torque gives f times the
   static torque at 20 C, for f from 1.6 to 2.4, the best f chosen with the truth in hand.
3. A motor rule: brake torque f times the motor's rated torque (P / omega), smallest size that reaches it, for f from
   1.0 to 2.5, the best f chosen with the truth in hand.
4. The reference's own model with no tests: the catalogue's rated torque at every temperature and its engagement
   times at every setting (also in route_study.txt).
5. The register as it stands with no tests: as 4, without the maintenance log.
"""
import numpy as np

import common as C
import hbsim as S

G = 9.81
SET = np.arange(50, 101)


def truth_ok(hid, size, st):
    r = S.margins(hid, size, np.asarray(st, float))
    return np.min([r[k] for k in S.REQUIREMENTS], axis=0) >= 0


def holding_rule(f):
    picks = {}
    for hid, h in C.H0.items():
        need = f * C.R.static(h, h["load"])
        for size, b in C.CAT.items():
            s = int(np.ceil(100 * need / b["Mr"]))
            if s <= 100:
                picks[hid] = (size, max(50, s))
                break
        else:
            picks[hid] = ("S25", 100)
    return picks


def motor_rule(f):
    import csv
    reg = {r["hoist"]: r for r in csv.DictReader(open(C.DATA + "/hoist_register.csv"))}
    picks = {}
    for hid in C.IDS:
        r = reg[hid]
        need = f * float(r["motor_kW"]) * 1000 / (float(r["motor_rpm"]) * np.pi / 30)
        for size, b in C.CAT.items():
            s = int(np.ceil(100 * need / b["Mr"]))
            if s <= 100:
                picks[hid] = (size, max(50, s))
                break
        else:
            picks[hid] = ("S25", 100)
    return picks


def passes(picks):
    return {hid for hid in C.IDS if S.meets(hid, *picks[hid])[0]}


def main():
    print(__doc__.split("\n\n")[0].strip())
    print("Shipped scenario. The selection is accepted only with all 12 right.\n")
    free = {hid: [] for hid in C.IDS}
    tops = []

    # 1. one brake for all
    grid = {}
    for size in S.SIZES:
        ok = np.array([truth_ok(hid, size, SET) for hid in C.IDS])      # hoist x setting
        for j, s in enumerate(SET):
            grid[(size, int(s))] = {C.IDS[i] for i in np.flatnonzero(ok[:, j])}
    best = max(grid, key=lambda k: len(grid[k]))
    tops.append(len(grid[best]))
    print("1. one brake for all: best %s at %d %% gets %d of 12 (%s)" % (best[0], best[1], len(grid[best]),
                                                                      " ".join(sorted(grid[best]))))
    for k, v in grid.items():
        for hid in v:
            free[hid].append("one brake %s/%d" % k)

    # 2. holding alone
    res = []
    for f in np.round(np.arange(1.6, 2.401, 0.05), 2):
        ok = passes(holding_rule(f))
        res.append((len(ok), f, ok))
        for hid in ok:
            free[hid].append("holding x%.2f" % f)
    n, f, ok = max(res, key=lambda t: t[0])
    tops.append(n)
    print("2. holding alone: best f = %.2f gets %d of 12 (%s)" % (f, n, " ".join(sorted(ok)) or "none"))

    # 3. motor rule
    res = []
    for f in np.round(np.arange(1.0, 2.501, 0.1), 2):
        ok = passes(motor_rule(f))
        res.append((len(ok), f, ok))
        for hid in ok:
            free[hid].append("motor x%.1f" % f)
    n, f, ok = max(res, key=lambda t: t[0])
    tops.append(n)
    print("3. motor rule: best f = %.1f gets %d of 12 (%s)" % (f, n, " ".join(sorted(ok)) or "none"))

    # 4. and 5. the reference's model without tests
    for label, H in (("4. reference model, no tests", C.H0), ("5. register as it stands, no tests", C.hoists(miss=("log",)))):
        picks, n, fails = C.run(M=C.catalogue_model(), H=H, reach=1e9)
        ok = {hid for hid in C.IDS if hid not in {x.split()[0] for x in fails}}
        tops.append(n)
        print("%s: %d of 12 (%s)" % (label, n, " ".join(sorted(ok))))
        for hid in ok:
            free[hid].append(label.split(".")[0] + " no-test model")

    print("\nPer-hoist free passes (null answers above that happen to be right on the hoist):")
    for hid in C.IDS:
        v = free[hid]
        one = sum(x.startswith("one brake") for x in v)
        other = [x for x in v if not x.startswith("one brake")]
        print("%s: %3d of %d single-brake answers; %s" % (hid, one, len(grid), ", ".join(other) or "no other null answer"))
    none = [hid for hid in C.IDS if not [x for x in free[hid] if not x.startswith("one brake")]]
    print("\nNo null answer gets more than %d of 12, even with its factor chosen with the truth in hand; the selection "
          "needs all 12. The best single brake gets %d. A factor that suits some hoists does not suit others: no one f "
          "of answers 2 and 3 is right on more than %d. Right under none of answers 2 to 5: %s." %
          (max(tops), len(grid[best]), max(tops[1:3]), " ".join(none) or "none"))


if __name__ == "__main__":
    main()
