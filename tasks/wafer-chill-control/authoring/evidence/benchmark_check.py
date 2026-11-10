"""How close the verifier's perfect-knowledge benchmark is to the best a perfect-knowledge
controller can do, and how sensitive it is to its own settings.

    python3 authoring/evidence/benchmark_check.py > authoring/evidence/benchmark_check.txt

The benchmark (plant.clairvoyant) knows the wafer exactly and sees its whole state. Every
control period it holds the largest of 48 log-spaced commands whose 1.2 s constant-command
lookahead keeps the zone difference under the cap minus 0.02 K, and it releases at the first
control instant at which the mass mean is at or under the target.

Variants, each run on all 24 hidden wafers:
  finer      96 candidate commands instead of 48
  longer     2.4 s lookahead instead of 1.2 s
  no guard   cap instead of cap - 0.02 K
  escape     the least conservative safe greedy: a candidate passes if holding it for ONE
             control period and then dropping to the minimum pressure keeps the zone under
             the cap for the horizon. Because the drop is always available at the next
             period, the policy stays safe, and it admits every command the constant-hold
             test admits and more.
If none of these shortens the total cycle by much, the benchmark is close to the best
achievable by riding the zone limit, and the allowance means what it says.
"""
import math
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import grade  # noqa: E402
import plant as pl  # noqa: E402


def greedy(wafer, horizon=1.2, guard=0.02, n_cand=48, mode="hold", dt=pl.DT):
    cands = np.exp(np.linspace(math.log(pl.P_MIN), math.log(pl.P_MAX), n_cand))[:, None]
    Tw, Tp, P = wafer.landing()
    n_sub = int(round(pl.CTRL_DT / dt))
    n_look = int(round(horizon / dt))
    worst = 0.0
    for k in range(int(round(pl.T_CYCLE_MAX / pl.CTRL_DT))):
        if float(wafer.t_mean(Tw)[0]) <= pl.T_TARGET:
            return round(k * pl.CTRL_DT, 6), worst
        m = len(cands)
        W, Q, PP = np.repeat(Tw, m, 0), np.repeat(Tp, m, 0), np.repeat(P, m, 0)
        ok = np.ones(m, bool)
        for j in range(n_look):
            cmd = cands if (mode == "hold" or j < n_sub) else np.full_like(cands, pl.P_MIN)
            W, Q, PP = wafer.step(W, Q, PP, cmd, dt)
            ok &= wafer.zone_dT(W) <= pl.ZONE_CAP - guard
        P_cmd = np.array([[float((cands[ok][-1] if ok.any() else cands[0]).ravel()[0])]])
        for _ in range(n_sub):
            Tw, Tp, P = wafer.step(Tw, Tp, P, P_cmd, dt)
            worst = max(worst, float(wafer.zone_dT(Tw)[0]))
    return float("inf"), worst


VARIANTS = [
    ("shipped benchmark", {}),
    ("finer (96 commands)", {"n_cand": 96}),
    ("longer (2.4 s lookahead)", {"horizon": 2.4}),
    ("no guard", {"guard": 0.0}),
    ("escape lookahead", {"mode": "escape"}),
    ("escape, 96 commands, no guard", {"mode": "escape", "n_cand": 96, "guard": 0.0}),
]


def job(args):
    truth, w, kw = args
    return w["id"], greedy(grade.make_wafer(truth, w), **kw)


def main():
    t0 = time.time()
    truth = grade.load_truth()
    ship = {}
    print("%-32s %10s %9s %10s %9s" % ("benchmark variant", "total (s)", "vs ship",
                                       "worst dT", "max gain"))
    with ProcessPoolExecutor(max_workers=2) as ex:
        for label, kw in VARIANTS:
            res = dict(ex.map(job, [(truth, w, kw) for w in truth["wafers"]]))
            tot = sum(c for c, _ in res.values())
            if not ship:
                ship = {k: c for k, (c, _) in res.items()}
                # cross-check: this copy reproduces plant.clairvoyant exactly
                ref = grade.benchmarks(truth)
                assert all(abs(ref[k][0] - ship[k]) < 1e-9 for k in ship), "copy drifted"
            gain = max((ship[k] - c) / ship[k] for k, (c, _) in res.items())
            print("%-32s %10.1f %9.4f %10.3f %8.1f%%" % (
                label, tot, tot / sum(ship.values()), max(wst for _, wst in res.values()),
                100 * gain), flush=True)
    print("\nvs ship: total cycle relative to the shipped benchmark; max gain: the largest "
          "single-wafer shortening")
    print("[%.0f s]" % (time.time() - t0))


if __name__ == "__main__":
    main()
