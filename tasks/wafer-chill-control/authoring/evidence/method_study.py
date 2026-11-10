"""Convergence of the sealed plant in its two resolution settings.

    python3 authoring/evidence/method_study.py > authoring/evidence/method_study.txt

The verifier resolves the wafer into 80 rings of equal width and integrates with RK4 at
0.01 s, checking the zone difference at every step. A controller is graded on three
quantities that depend on that resolution: the largest zone difference, the mass mean at
release and, through the benchmark, the perfect-knowledge cycle. This script fixes a
command sequence and replays it at other ring counts and time steps, and recomputes the
benchmark at each, on the four hidden wafers at the corners of the population: the
deepest sag and the deepest dish on each station.

What matters is the size of each difference against the margins the reference carries
(0.38 K on the zone limit and 0.27 C on the release limit on the shipped set).
"""
import math
import os
import sys
import time

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tests"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import grade  # noqa: E402
import plant as pl  # noqa: E402
from benchmark_check import greedy  # noqa: E402


def wafer_at(truth, w, n_rings):
    s = truth["stations"][w["station"]]
    return pl.Wafer(s["inner_um"] * 1e-6, s["outer_um"] * 1e-6, s["setpoint_C"],
                    s["_alpha_plate"], truth["films"][w["film"]]["_alpha_wafer"],
                    w["_sag_um"] * 1e-6, w["_T0_C"], n_rings=n_rings)


def commands(wafer):
    """The shipped benchmark's command sequence on this wafer, and its release step."""
    cands = np.exp(np.linspace(math.log(pl.P_MIN), math.log(pl.P_MAX), 48))[:, None]
    Tw, Tp, P = wafer.landing()
    out = []
    for k in range(300):
        if float(wafer.t_mean(Tw)[0]) <= pl.T_TARGET:
            return out
        m = len(cands)
        W, Q, PP = np.repeat(Tw, m, 0), np.repeat(Tp, m, 0), np.repeat(P, m, 0)
        ok = np.ones(m, bool)
        for _ in range(120):
            W, Q, PP = wafer.step(W, Q, PP, cands)
            ok &= wafer.zone_dT(W) <= pl.ZONE_CAP - 0.02
        c = float((cands[ok][-1] if ok.any() else cands[0]).ravel()[0])
        out.append(c)
        for _ in range(10):
            Tw, Tp, P = wafer.step(Tw, Tp, P, np.array([[c]]))
    return out


def replay(wafer, cmds, dt):
    Tw, Tp, P = wafer.landing()
    n_sub = int(round(pl.CTRL_DT / dt))
    worst = 0.0
    for c in cmds:
        for _ in range(n_sub):
            Tw, Tp, P = wafer.step(Tw, Tp, P, np.array([[c]]), dt)
            worst = max(worst, float(wafer.zone_dT(Tw)[0]))
    return worst, float(wafer.t_mean(Tw)[0])


def main():
    t0 = time.time()
    truth = grade.load_truth()
    picks = []
    for st in ("A", "B"):
        ws = [w for w in truth["wafers"] if w["station"] == st]
        picks += [max(ws, key=lambda w: w["_sag_um"]), min(ws, key=lambda w: w["_sag_um"])]
    settings = [(40, 0.01), (80, 0.01), (160, 0.01), (80, 0.005), (160, 0.005), (160, 0.0025)]
    print("replay of the shipped benchmark's commands, and the benchmark recomputed")
    print("%-5s %-8s %6s %8s  %10s %10s %10s" % ("wafer", "sag um", "rings", "dt s",
                                                "max dT K", "T_rel C", "bench s"))
    for w in picks:
        cmds = commands(wafer_at(truth, w, 80))
        base = None
        for n, dt in settings:
            worst, trel = replay(wafer_at(truth, w, n), cmds, dt)
            bench, _ = greedy(wafer_at(truth, w, n), dt=dt)
            if (n, dt) == (80, 0.01):
                base = (worst, trel, bench)
            print("%-5s %+8.1f %6d %8.4f  %10.3f %10.3f %10.1f" % (w["id"], w["_sag_um"], n, dt,
                                                                  worst, trel, bench), flush=True)
        print()
    print("[%.0f s]" % (time.time() - t0))


if __name__ == "__main__":
    main()
