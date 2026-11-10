"""Design Monte Carlo: which campaigns and models clear the gate, on the shipped draw and
across redrawn fleets.

Pure numpy, no thermal simulation. Under the jump-distance form a coefficient error is
exactly a pressure error, so a station is commissioned iff the log error in
f(a) = a/(2-a) between its true and estimated coefficient is inside that station's own
window -- measured exactly, per station, by station_windows.py, for a recipe centred in
the band the 8% allowance opens. The windows are properties of each station's geometry
and temperatures, so they hold unchanged when the coefficients are redrawn. Measured
stations carry identification error of 0.006 in the coefficient, about what both the
reference and the ablation ladder achieve. The gate is 15 of 16.

Two things are reported for every campaign and model:

  shipped  the fraction of 1000 identification-noise draws on the SHIPPED fleet that
           clear the gate -- how reliably the strategy commissions THIS instance;
  redrawn  the fraction of 300 fleets with freshly drawn scatter that clear the gate
           -- whether the strategy is sound in general or lucky here.

    python3 design_mc.py
"""
import itertools
import json
import os

import numpy as np
from scipy.spatial import ConvexHull, Delaunay

HERE = os.path.dirname(os.path.abspath(__file__))

LOTS = dict(zip(["L%02d" % i for i in range(1, 13)],
                [40, 42, 44, 46, 48, 50, 52, 54, 56, 58, 61, 64]))
FLEET = [("S01", 0.42, "L04"), ("S02", 1.18, "L10"), ("S03", 0.61, "L02"),
         ("S04", 1.34, "L08"), ("S05", 0.29, "L05"), ("S06", 0.95, "L12"),
         ("S07", 0.74, "L01"), ("S08", 1.07, "L05"), ("S09", 0.35, "L06"),
         ("S10", 0.88, "L07"), ("S11", 1.26, "L03"), ("S12", 0.53, "L07"),
         ("S13", 0.66, "L06"), ("S14", 1.12, "L09"), ("S15", 0.47, "L02"),
         ("S16", 0.99, "L11")]
NAMES = [f[0] for f in FLEET]
RA = np.array([f[1] for f in FLEET])
TB = np.array([LOTS[f[2]] for f in FLEET], dtype=float)
LOT = np.array([f[2] for f in FLEET])

# the sealed structure, mirrored from authoring/provenance/make_fleet.py
A0, B, RA_REF, SLOPE, T_REF, KNEE, EPS = 0.46, 0.115, 0.80, -0.030, 44.0, 48.0, 0.010
SHIPPED_SEED = 20260919
IDENT = 0.006
GATE_FAILS = 1

_W = json.load(open(os.path.join(HERE, "station_windows.json")))
TOL = np.array([{r["station"]: r["tol_lnf"] for r in _W["stations"]}[n] for n in NAMES])


def alpha(seed):
    rng = np.random.default_rng(seed)
    return A0 + B * (RA - RA_REF) + SLOPE * (np.minimum(TB, KNEE) - T_REF) \
        + rng.normal(0.0, EPS, len(RA))


def lnf(a):
    a = np.clip(a, 0.02, 0.98)
    return np.log(a / (2.0 - a))


def _ls(X, y):
    c, *_ = np.linalg.lstsq(X, y, rcond=None)
    return c, float(np.sum((y - X @ c) ** 2))


def predict(kind, idx, y):
    if kind == "dummies":
        touched = sorted(set(LOT[idx]))
        X = np.column_stack([RA[idx]] + [(LOT[idx] == L).astype(float) for L in touched])
        c, _ = _ls(X, y)
        mean_y, mean_ra = float(np.mean(y)), float(np.mean(RA[idx]))
        out = np.empty(len(RA))
        for i in range(len(RA)):
            out[i] = (c[0] * RA[i] + c[1 + touched.index(LOT[i])] if LOT[i] in touched
                      else mean_y + c[0] * (RA[i] - mean_ra))
        return out
    if kind == "linear":
        c, _ = _ls(np.column_stack([np.ones(len(idx)), RA[idx], TB[idx]]), y)
        return c[0] + c[1] * RA + c[2] * TB
    if kind == "quad":
        c, _ = _ls(np.column_stack([np.ones(len(idx)), RA[idx], TB[idx], TB[idx] ** 2]), y)
        return c[0] + c[1] * RA + c[2] * TB + c[3] * TB ** 2
    if kind in ("hinge", "hinge_lumped"):
        target = y / (2.0 - y) if kind == "hinge_lumped" else y
        best = None
        for k in np.arange(42.0, 62.01, 0.5):
            c, s = _ls(np.column_stack([np.ones(len(idx)), RA[idx],
                                        np.minimum(TB[idx], k)]), target)
            if best is None or s < best[0]:
                best = (s, k, c)
        _, k, c = best
        z = c[0] + c[1] * RA + c[2] * np.minimum(TB, k)
        return 2.0 * z / (1.0 + z) if kind == "hinge_lumped" else z
    raise ValueError(kind)


def failures(kind, idx, a, rng):
    """Stations outside their window, measured ones included (with their noise)."""
    y = a[idx] + rng.normal(0.0, IDENT, len(idx))
    p = predict(kind, idx, y).copy()
    p[idx] = y
    return np.flatnonzero(np.abs(lnf(a) - lnf(p)) > TOL)


CAMPAIGNS = {
    # what most probe agents converged on: the same-lot roughness pair first, both bath
    # extremes, the roughness extreme, then three points along the cold ramp
    "probe standard": ["S05", "S08", "S06", "S04", "S07", "S11", "S01", "S15"],
    # the same, with the roughness extreme traded for the low-roughness plateau corner
    "probe + corner": ["S05", "S08", "S06", "S07", "S11", "S01", "S15", "S09"],
    # the previous reference: eight lots, dense on the cold ramp, one per lot
    "eight lots": ["S07", "S15", "S11", "S01", "S05", "S13", "S04", "S06"],
    # the shipped reference: the seven hull vertices, plus the minimax-variance pick
    "hull + 1": ["S07", "S15", "S11", "S05", "S09", "S04", "S16", "S06"],
}
MODELS = ("dummies", "linear", "quad", "hinge_lumped", "hinge")


def coverage():
    X = np.column_stack([RA, TB])
    hull = sorted(NAMES[i] for i in ConvexHull(X).vertices)
    print("fleet hull in (roughness, bath temperature): %s -- %d stations"
          % (", ".join(hull), len(hull)))
    full = 0
    for S in itertools.combinations(range(len(NAMES)), 8):
        tri = Delaunay(X[list(S)])
        if all(tri.find_simplex(X[i]) >= 0 for i in range(len(NAMES)) if i not in S):
            full += 1
    print("8-run campaigns that leave no unmeasured station outside the measured hull: "
          "%d of %d" % (full, len(list(itertools.combinations(range(16), 8)))))
    for name, camp in CAMPAIGNS.items():
        idx = [NAMES.index(c) for c in camp]
        tri = Delaunay(X[idx])
        out = [NAMES[i] for i in range(len(NAMES))
               if i not in idx and tri.find_simplex(X[i]) < 0]
        print("  %-15s extrapolates to: %s" % (name, ", ".join(out) or "nothing"))


def main():
    a0 = alpha(SHIPPED_SEED)
    struct = A0 + B * (RA - RA_REF) + SLOPE * (np.minimum(TB, KNEE) - T_REF)
    eps = a0 - struct
    print("shipped draw: scatter the inspection report cannot explain (eps / EPS_RMS)")
    print("  " + "  ".join("%s %+.1f" % (n, e / EPS) for n, e in zip(NAMES, eps)))
    print("  %d of 16 negative; the three positive are S11, S12, S14\n"
          % int(np.sum(eps < 0)))
    coverage()
    print("\nwindows: centred recipe at the 8%% allowance, %.3f to %.3f in ln f "
          "(station_windows.json)" % (TOL.min(), TOL.max()))
    print("identification error %.3f; gate 15 of 16\n" % IDENT)
    print("  %-15s %-13s %9s %9s   %s"
          % ("campaign", "model", "shipped", "redrawn", "stations lost most often on "
             "the shipped draw"))
    rng = np.random.default_rng(3)
    seeds = [SHIPPED_SEED + 1000 * k for k in range(1, 301)]
    for name, camp in CAMPAIGNS.items():
        idx = np.array([NAMES.index(c) for c in camp])
        for kind in MODELS:
            lost = np.zeros(len(NAMES))
            ok_ship = 0
            for _ in range(1000):
                f = failures(kind, idx, a0, rng)
                lost[f] += 1
                ok_ship += len(f) <= GATE_FAILS
            ok_red = sum(len(failures(kind, idx, alpha(s), rng)) <= GATE_FAILS
                         for s in seeds)
            top = [(NAMES[i], lost[i] / 10.0) for i in np.argsort(-lost)[:3] if lost[i]]
            print("  %-15s %-13s %8.1f%% %8.1f%%   %s"
                  % (name, kind, ok_ship / 10.0, ok_red / 3.0,
                     ", ".join("%s %.0f%%" % t for t in top) or "-"), flush=True)


def gate_table():
    """Why the gate is 15: the same hinge model, the gate moved, on the shipped fleet."""
    a0 = alpha(SHIPPED_SEED)
    rng = np.random.default_rng(5)
    print("\nthe gate, moved with everything else held: hinge model, 1000 identification-"
          "noise draws\non the shipped fleet, fraction clearing each gate")
    print("  %-15s %10s %10s %10s" % ("campaign", "16 of 16", "15 of 16", "14 of 16"))
    for name, camp in CAMPAIGNS.items():
        idx = np.array([NAMES.index(c) for c in camp])
        f = np.array([len(failures("hinge", idx, a0, rng)) for _ in range(1000)])
        print("  %-15s %9.1f%% %9.1f%% %9.1f%%"
              % (name, 100 * np.mean(f == 0), 100 * np.mean(f <= 1), 100 * np.mean(f <= 2)))
    print("  At 16 of 16 even the hull campaign is mostly luck, because S12's scatter runs")
    print("  against its neighbours'; at 14 of 16 a campaign that never reaches the plateau")
    print("  corner passes too. 15 of 16 is the setting that separates the campaigns.")


if __name__ == "__main__":
    main()
    gate_table()
