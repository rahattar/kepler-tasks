"""Chooses the laboratory seed. The seed drives only the scatter of a weighing; the gas analyses are the
laboratory's reports of record and the plant's own records carry their own fixed scatter from isim.SURVEY_SEED, so
nothing in the records moves with the seed.

    python3 authoring/provenance/seed_screen.py

The seed is the first from 4101 on which

1. every sound variation of authoring/evidence/method_spread.py gets all twelve values right, and none of them is
   further than MARGIN of the tolerance from the definition, so that no correct method is near the edge of the band;
2. the separate solution of authoring/evidence/independent.py gets all twelve values right;
3. every defective route of authoring/evidence/route_study.py that is meant to fail does fail.

The offset of the weighing each plan draws is reported with the seed, in standard deviations of the stated
repeatability.
"""
import os
import sys

import numpy as np

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "evidence"))
import common as C  # noqa: E402
import independent as I  # noqa: E402
import method_spread as M  # noqa: E402
import route_study as R  # noqa: E402

S = C.S
TOTAL = len(C.ITEMS)
MARGIN = 0.7            # of the tolerance
PASSING = ("pin reversal not checked",)     # routes that are not meant to fail


def offsets(seed, log):
    """the offsets, in standard deviations, of the weighings of one plan"""
    z = []
    for idx, item in enumerate(log, start=1):
        cmd, arg = item.split()
        if cmd != "weigh":
            continue
        rng = np.random.default_rng([seed, idx, 5, list(S.LAB_CMDS).index("weigh"), C.IDS.index(arg)])
        z.append(abs(S.lab_weigh(arg, rng) - S.CYL[arg]["mrec"]) / S.NOISE_WEIGH)
    return z


def main():
    for seed in range(4101, 4200):
        z, worst, right = [], 0.0, True
        for _, kw in M.VARIATIONS:
            sheet, log = C.route(seed=seed, **kw)
            n, err, _ = C.grade(sheet)
            right &= n == TOTAL
            worst = max(worst, max(abs(err[k]) for k in C.ITEMS if k[1] == "pressure"))
            z += offsets(seed, log)
        ind, ilog = I.solve(seed)
        right &= C.grade(ind)[0] == TOTAL
        z += offsets(seed, ilog)
        note = "largest offset of a weighing %.2f sigma, sound variations %s, their worst error %.3f per cent" % (
            max(z or [0.0]), "all right" if right else "NOT all right", 100.0 * worst)
        if not right:
            print("seed %d: %s" % (seed, note))
            continue
        if worst > MARGIN * S.TOL:
            print("seed %d: %s, over %.3f per cent" % (seed, note, 100.0 * MARGIN * S.TOL))
            continue
        bad = [name for name, kw in R.ROUTES
               if name not in PASSING and C.grade(C.route(seed=seed, **kw)[0])[0] == TOTAL]
        if bad:
            print("seed %d: %s, but a defective route passes: %s" % (seed, note, "; ".join(bad)))
            continue
        print("seed %d: %s, every defective route fails  <- chosen" % (seed, note))
        return seed


if __name__ == "__main__":
    main()
