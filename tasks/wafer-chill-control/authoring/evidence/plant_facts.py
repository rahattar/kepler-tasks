"""Plant facts quoted in task.toml and the README, measured on the sealed plant.

    python3 authoring/evidence/plant_facts.py > authoring/evidence/plant_facts.txt

1. How much the sag alone moves the peak zone difference at a fixed pressure.
2. How far the two pyrometer spots misread the zone difference while the perfect-knowledge
   benchmark rides the limit: the spots are not the zones, and the error depends on the sag.
3. How much the plate warms during a cycle, and how much the pressure lag delays the
   pressure the wafer actually sees.
"""
import math
import os
import sys

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import grade  # noqa: E402
import plant as pl  # noqa: E402

TRUTH = grade.load_truth()


def wafer(station, film, sag_um, T0=250.0):
    s = TRUTH["stations"][station]
    return pl.Wafer(s["inner_um"] * 1e-6, s["outer_um"] * 1e-6, s["setpoint_C"],
                    s["_alpha_plate"], TRUTH["films"][film]["_alpha_wafer"], sag_um * 1e-6, T0)


def peak_zone_at(w, P, seconds=12.0):
    Tw, Tp, Pc = w.landing()
    worst = 0.0
    for _ in range(int(round(seconds / pl.DT))):
        Tw, Tp, Pc = w.step(Tw, Tp, Pc, np.array([[P]]))
        worst = max(worst, float(w.zone_dT(Tw)[0]))
    return worst


def ride(w):
    """The benchmark's trajectory, recording spots, zones, plate and pressure."""
    cands = np.exp(np.linspace(math.log(pl.P_MIN), math.log(pl.P_MAX), 48))[:, None]
    Tw, Tp, P = w.landing()
    rec = []
    for k in range(300):
        c, e = w.spots(Tw)
        rec.append((k * pl.CTRL_DT, float(w.zone_dT(Tw)[0]), float(abs(c[0] - e[0])),
                    float(Tp[0, 0]) - 273.15 - w.T_set, float(P[0, 0]), float(w.t_mean(Tw)[0])))
        if float(w.t_mean(Tw)[0]) <= pl.T_TARGET:
            break
        m = len(cands)
        W, Q, PP = np.repeat(Tw, m, 0), np.repeat(Tp, m, 0), np.repeat(P, m, 0)
        ok = np.ones(m, bool)
        for _ in range(120):
            W, Q, PP = w.step(W, Q, PP, cands)
            ok &= w.zone_dT(W) <= pl.ZONE_CAP - 0.02
        cmd = float((cands[ok][-1] if ok.any() else cands[0]).ravel()[0])
        for _ in range(10):
            Tw, Tp, P = w.step(Tw, Tp, P, np.array([[cmd]]))
        rec[-1] = rec[-1] + (cmd,)
    return rec


def main():
    print("1. PEAK ZONE DIFFERENCE AT A FIXED 15 Torr, bare film, landing at 250 C")
    for st in ("A", "B"):
        vals = [(s, peak_zone_at(wafer(st, "bare", s), 15.0)) for s in (-50, -25, 0, 25, 50)]
        print("   station %s: " % st + ", ".join("sag %+d um -> %.1f K" % v for v in vals))

    print("\n2. SPOTS VERSUS ZONES while the benchmark rides the 25 K limit (bare, 250 C)")
    print("   |centre - edge| at the instant the zone difference peaks, and the largest gap")
    print("   between the two over the cycle")
    for st in ("A", "B"):
        for s in (-50, 0, 50):
            rec = ride(wafer(st, "bare", s))
            i = int(np.argmax([r[1] for r in rec]))
            gap = max(r[2] - r[1] for r in rec)
            low = min(r[2] - r[1] for r in rec)
            print("   station %s sag %+3d um: zone %.2f K, spots %.2f K at t = %.1f s; spots minus "
                  "zone ranges %+.1f to %+.1f K" % (st, s, rec[i][1], rec[i][2], rec[i][0], low, gap))

    print("\n3. PLATE AND PRESSURE during the benchmark cycle (bare, 250 C)")
    for st in ("A", "B"):
        for s in (-50, 50):
            rec = ride(wafer(st, "bare", s))
            print("   station %s sag %+3d um: cycle %.1f s, plate up to %.1f K above setpoint"
                  % (st, s, rec[-1][0], max(r[3] for r in rec)))
    for t in (pl.CTRL_DT, 0.5, 1.0):
        print("   a step in the pressure command has covered %.0f%% of its size after %.1f s"
              % (100 * (1 - math.exp(-t / pl.TAU_P)), t))


if __name__ == "__main__":
    main()
