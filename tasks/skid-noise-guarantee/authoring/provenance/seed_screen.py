"""Chooses the laboratory seed. The seed drives only the scatter of the booked instrument's three readings; the
contractor's survey carries its own fixed scatter from isim.SURVEY_SEED, so the records do not move with it.

    python3 authoring/provenance/seed_screen.py

The seed is the first from 7101 on which

1. every sound method of authoring/evidence/method_spread.py gets all 36 values right, and none of them is further
   than MARGIN of the tolerance from the definition, so that no correct method is anywhere near the edge of the band;
2. the separate solution of authoring/evidence/independent.py gets all 36 values right;
3. every defective route of authoring/evidence/route_study.py that is meant to fail does fail.

A gate on the largest offset of a reading is not used: the number of readings a plan could draw is in the thousands,
so the largest of them is 3 to 4 standard deviations out on every seed, and whether that matters is exactly what
condition 1 measures. The offsets of the readings the sound methods do draw are reported with each seed.
"""
import math
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
TOTAL = len(C.IDS) * len(C.KEYS)
MARGIN = 0.7            # of the tolerance
PASSING = ("the levels averaged arithmetically, not in energy",)     # routes that are not meant to fail


def offsets(seed, log):
    """the offsets, in standard deviations, of the readings of one plan"""
    z = []
    for idx, (cmd, pid, state) in enumerate(log, start=1):
        rng = np.random.default_rng([seed, idx, 3, ("slm", "rt").index(cmd), list(S.POS).index(pid),
                                     list(S.STATES).index(state if cmd == "slm" else "off")])
        if cmd == "slm":
            for v, b in zip(S.lab_slm(pid, state, rng), S.BANDS):
                z.append(abs(v - S.lp_total(S.state_machines(state), pid, b)) / S.NOISE_SLM)
        else:
            for v, b in zip(S.lab_rt(pid, rng), S.BANDS):
                z.append(abs(math.log(v / S.T60[b])) / S.NOISE_RT)
    return z


def main():
    for seed in range(7101, 7200):
        z, worst, right = [], 0.0, True
        for _, kw in M.METHODS:
            sheet, log = C.solve_route(seed=seed, **kw)
            n, err, _ = C.grade(sheet)
            right &= n == TOTAL
            worst = max(worst, max(abs(err[m][k]) for m in C.IDS for k in C.KEYS))
            z += offsets(seed, log)
        ind, ilog = I.run(seed)[:2]
        right &= C.grade(ind)[0] == TOTAL
        z += offsets(seed, ilog)
        note = "largest offset of a drawn reading %.2f sigma, sound methods %s, their worst error %.2f dB" % (
            max(z), "all right" if right else "NOT all right", worst)
        if not right:
            print("seed %d: %s" % (seed, note))
            continue
        if worst > MARGIN * S.TOL:
            print("seed %d: %s, over %.2f dB" % (seed, note, MARGIN * S.TOL))
            continue
        bad = [name for name, kw in R.ROUTES
               if name not in PASSING and C.grade(C.solve_route(seed=seed, **kw)[0])[0] == TOTAL]
        if bad:
            print("seed %d: %s, but a defective route passes: %s" % (seed, note, "; ".join(bad)))
            continue
        print("seed %d: %s, every defective route fails  <- chosen" % (seed, note))
        return seed


if __name__ == "__main__":
    main()
