"""Ablation ladder on the shipped hidden set, graded by the shipped verifier.

    python3 authoring/evidence/ladder.py > authoring/evidence/ladder.txt

Two kinds of rung.

CONTROLLERS, run through grade.run_wafer exactly as a submission is (sandboxed process,
seeded sensor noise, 0.01 s zone checks): the reference, built by solution/solve.py from
the public data, and variants of it with one piece removed or mis-set.

HINDSIGHT BOUNDS, computed in-process on the sealed plant with knowledge no controller
has: the best a strategy class could do if it were tuned on the hidden wafers themselves.
They bound what that class of controller can reach; a bound that fails the gate means
no controller of that class passes.

Every rung is scored against the same perfect-knowledge benchmark the verifier computes.
"""
import json
import math
import os
import re
import sys
import tempfile
import time

import numpy as np
from scipy.optimize import least_squares

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tests"))
sys.path.insert(0, os.path.join(ROOT, "solution"))
import grade  # noqa: E402
import plant as pl  # noqa: E402

os.environ.setdefault("CHILL_DATA", os.path.join(ROOT, "environment", "data"))
import solve  # noqa: E402
from refmodel import Grid  # noqa: E402

OUT = tempfile.mkdtemp(prefix="wcc_ladder_")


# ---------------------------------------------------------------- controllers
def identify(ablation=None):
    """The reference identification, optionally with one model structure removed:
    'no-lag'   pressure assumed to follow the command at once (tau fixed at 1 ms)
    'no-plate' plate assumed held at its setpoint (heat capacity fixed at 1e9 J/K)"""
    stations, split, wafer, prod, runs = solve.load()
    sens = prod["sensors"]
    grid = Grid(solve.N_RINGS, wafer["diameter_mm"] * 0.5e-3, split,
                [v * 1e-3 for v in sens["center_pyrometer_annulus_mm"]],
                [v * 1e-3 for v in sens["edge_pyrometer_annulus_mm"]])
    tau = (1e-3 if ablation == "no-lag" else
           solve.fit_tau(runs, prod["chamber_pressure_at_landing_torr"], prod["control_period_s"]))
    theta0 = np.array([math.log(9.0)] * 6 + [math.log(2000.0), math.log(500.0)])
    if ablation == "no-plate":
        fixed = np.array([math.log(1e9), math.log(500.0)])

        def res(th):
            return solve.residuals(np.concatenate([th, fixed]), runs, stations, grid, wafer,
                                   tau, solve.FIT_UNTIL_S)
        fit = least_squares(res, theta0[:6], x_scale=1.0, diff_step=1e-3, max_nfev=200)
        theta = np.concatenate([fit.x, fixed])
    else:
        fit = least_squares(solve.residuals, theta0, args=(runs, stations, grid, wafer, tau,
                                                          solve.FIT_UNTIL_S),
                            x_scale=1.0, diff_step=1e-3, max_nfev=200)
        theta = fit.x
    rms = math.sqrt(float(np.mean(fit.fun ** 2)))
    J = np.exp(theta[:6])
    ident = dict(tau=tau, C_plate=math.exp(theta[6]), G_chiller=math.exp(theta[7]),
                 J={s: {f: float(J[solve.COMBOS.index((s, f))])
                        for f in ("bare", "oxide", "nitride")} for s in ("A", "B")}, rms=rms)
    return ident, (wafer, prod, split)


def write(ident, ctx, name, edits=()):
    path = os.path.join(OUT, name + ".py")
    wafer, prod, split = ctx
    solve.write_controller(ident, wafer, prod, split, path)
    src = open(path).read()
    for pat, rep in edits:
        src, n = re.subn(pat, rep, src, count=1, flags=re.M)
        assert n == 1, (name, pat)
    with open(path, "w") as f:
        f.write(src)
    return path


def grade_controller(path, truth, bench):
    rows = [grade.run_wafer(path, truth, w) for w in truth["wafers"]]
    return summarise(rows, bench)


def summarise(rows, bench):
    tot = sum(r["cycle_s"] if r["cycle_s"] is not None else pl.T_CYCLE_MAX for r in rows)
    tb = sum(bench[r["id"]] for r in rows)
    fails = [r for r in rows if not r["passed"]]
    zone_f = sum(r["worst_zone_dT_K"] > pl.ZONE_CAP + grade.EPS for r in rows)
    hot_f = sum(r["T_release_C"] is not None and r["T_release_C"] > pl.T_TARGET + grade.EPS
                for r in rows)
    late_f = sum(r["T_release_C"] is None for r in rows)
    return dict(ratio=tot / tb, failed=len(fails), zone=zone_f, hot=hot_f, late=late_f,
                worst_zone=max(r["worst_zone_dT_K"] for r in rows),
                hottest=max((r["T_release_C"] or 0.0) for r in rows))


# ---------------------------------------------------------------- hindsight bounds
def sweep_constant(wafer, cands, rng=None):
    """Every candidate pressure held from landing, all at once. Returns per control step:
    time, true mass mean (m, k), running max of the zone difference (m, k)."""
    m = len(cands)
    Tw, Tp, P = wafer.landing(m)
    Pc = np.asarray(cands, float)[:, None]
    n_sub = int(round(pl.CTRL_DT / pl.DT))
    n = int(round(pl.T_CYCLE_MAX / pl.CTRL_DT))
    tm = np.zeros((m, n))
    zmax = np.zeros((m, n))
    run = np.zeros(m)
    for k in range(n):
        tm[:, k] = wafer.t_mean(Tw)
        zmax[:, k] = run
        for _ in range(n_sub):
            Tw, Tp, P = wafer.step(Tw, Tp, P, Pc)
            run = np.maximum(run, wafer.zone_dT(Tw))
    return tm, zmax


def first_ok(tm, zmax):
    """Per row: first control step at which the mass mean is at or under the target with
    the zone limit kept so far, or None."""
    out = []
    for i in range(tm.shape[0]):
        ok = np.flatnonzero((tm[i] <= pl.T_TARGET + grade.EPS) & (zmax[i] <= pl.ZONE_CAP + grade.EPS))
        bad = np.flatnonzero(zmax[i] > pl.ZONE_CAP + grade.EPS)
        if ok.size and (not bad.size or ok[0] < bad[0]):
            out.append(int(ok[0]))
        else:
            out.append(None)
    return out


def constant_pressure_bounds(truth, bench):
    """(a) a recipe: one constant pressure and one fixed release time per station and film,
    chosen with hindsight on the hidden wafers of that group; (b) the best constant
    pressure for each wafer individually, with its sag known and release at the exact
    instant its mass mean reaches the target."""
    cands = np.exp(np.linspace(math.log(pl.P_MIN), math.log(pl.P_MAX), 60))
    per = {}
    for w in truth["wafers"]:
        tm, zmax = sweep_constant(grade.make_wafer(truth, w), cands)
        per[w["id"]] = (w, tm, zmax)
    # (b) known sag, per-wafer constant pressure
    tot_b, tb = 0.0, 0.0
    for wid, (w, tm, zmax) in per.items():
        ks = [k for k in first_ok(tm, zmax) if k is not None]
        tot_b += (min(ks) * pl.CTRL_DT) if ks else pl.T_CYCLE_MAX
        tb += bench[wid]
    known = tot_b / tb
    # (a) recipe per station and film
    groups = {}
    for wid, (w, tm, zmax) in per.items():
        groups.setdefault((w["station"], w["film"]), []).append(wid)
    tot_a = 0.0
    for key, ids in groups.items():
        best = None
        for j in range(len(cands)):
            ks = []
            for wid in ids:
                _, tm, zmax = per[wid]
                k = first_ok(tm[j:j + 1], zmax[j:j + 1])[0]
                ks.append(k)
            if None in ks:
                continue
            k_rel = max(ks)
            # the zone limit must also hold for every wafer up to the common release
            if all(per[wid][2][j, k_rel] <= pl.ZONE_CAP + grade.EPS for wid in ids):
                if best is None or k_rel < best:
                    best = k_rel
        tot_a += len(ids) * (best * pl.CTRL_DT if best is not None else pl.T_CYCLE_MAX)
    recipe = tot_a / tb
    return recipe, known


def model_free_bound(truth, bench):
    """PI control of the measured spot difference to a setpoint, release when a weighted
    spot mean reaches a threshold. Setpoint, gains, base pressure, release weighting and
    threshold all chosen per station with hindsight on that station's hidden wafers."""
    sps = np.array([12.0, 15.0, 18.0, 21.0, 24.0, 27.0, 30.0, 34.0])
    kps = np.array([0.5, 1.5, 4.0])
    kis = np.array([1.0, 4.0, 12.0])
    bases = np.array([8.0, 20.0])
    combos = np.array([(s, kp, ki, b) for s in sps for kp in kps for ki in kis for b in bases])
    m = len(combos)
    weights = (0.0, 0.25, 0.5)
    thetas = np.arange(20.0, 56.01, 0.25)
    n_sub = int(round(pl.CTRL_DT / pl.DT))
    n = int(round(pl.T_CYCLE_MAX / pl.CTRL_DT))
    res = {}
    for w in truth["wafers"]:
        wafer = grade.make_wafer(truth, w)
        rng = np.random.default_rng(w["_noise_seed"])
        Tw, Tp, P = wafer.landing(m)
        integ = np.zeros(m)
        tm = np.zeros((m, n))
        zmax = np.zeros((m, n))
        prox = np.zeros((len(weights), m, n))
        run = np.zeros(m)
        for k in range(n):
            c, e = wafer.spots(Tw)
            c = c + rng.normal(0.0, pl.PYRO_RMS, m)
            e = e + rng.normal(0.0, pl.PYRO_RMS, m)
            tm[:, k] = wafer.t_mean(Tw)
            zmax[:, k] = run
            for i, a in enumerate(weights):
                prox[i, :, k] = a * c + (1.0 - a) * e
            err = combos[:, 0] - np.abs(c - e)
            u = combos[:, 3] + combos[:, 1] * err + combos[:, 2] * integ
            sat = ((u >= pl.P_MAX) & (err > 0)) | ((u <= pl.P_MIN) & (err < 0))
            integ = integ + np.where(sat, 0.0, err * pl.CTRL_DT)
            Pc = np.clip(combos[:, 3] + combos[:, 1] * err + combos[:, 2] * integ,
                         pl.P_MIN, pl.P_MAX)[:, None]
            for _ in range(n_sub):
                Tw, Tp, P = wafer.step(Tw, Tp, P, Pc)
                run = np.maximum(run, wafer.zone_dT(Tw))
        res[w["id"]] = (w, tm, zmax, prox)
    # per station: best (combo, weight, threshold)
    total, tb, fails_total = 0.0, 0.0, 0
    detail = {}
    for st in ("A", "B"):
        ids = [w["id"] for w in truth["wafers"] if w["station"] == st]
        best = None                      # (fails, total_cycle, desc)
        for j in range(m):
            for i, a in enumerate(weights):
                for th in thetas:
                    fails, tot = 0, 0.0
                    for wid in ids:
                        _, tm, zmax, prox = res[wid]
                        hit = np.flatnonzero(prox[i, j] <= th)
                        if not hit.size:
                            fails += 1
                            tot += pl.T_CYCLE_MAX
                            continue
                        k = int(hit[0])
                        ok = (tm[j, k] <= pl.T_TARGET + grade.EPS
                              and zmax[j, k] <= pl.ZONE_CAP + grade.EPS)
                        fails += (not ok)
                        tot += k * pl.CTRL_DT
                    key = (fails, tot)
                    if best is None or key < best[:2]:
                        best = (fails, tot, (tuple(combos[j]), a, th))
        detail[st] = best
        total += best[1]
        fails_total += best[0]
        tb += sum(bench[wid] for wid in ids)
    return total / tb, fails_total, detail


# ---------------------------------------------------------------- main
def main():
    t00 = time.time()
    truth = grade.load_truth()
    b = grade.benchmarks(truth)
    bench = {k: v[0] for k, v in b.items()}
    print("hidden set: %d wafers; total perfect-knowledge cycle %.1f s; gate: every wafer "
          "passes and total cycle <= %.2f x that" % (len(bench), sum(bench.values()),
                                                     1 + truth["allowance"]))
    print("benchmark worst zone difference %.3f K\n" % max(v[1] for v in b.values()))

    print("CONTROLLERS, graded by the shipped verifier")
    print("%-58s %7s %8s %5s %4s %5s %8s %8s" % ("rung", "ratio", "failed", "zone", "hot",
                                                  "late", "worstdT", "hottest"))
    ident, ctx = identify()
    ref = write(ident, ctx, "reference")
    rungs = [
        ("reference: identified model, online sag estimation", ref),
        ("  same model, no estimation, safe for the whole sag range",
         write(ident, ctx, "robust", [(r"^    SAG_GRID_M = .*$", "    SAG_GRID_M = np.array([-55e-6, 55e-6])"),
                                      (r"^    SIGMA_EFF_K = .*$", "    SIGMA_EFF_K = 1e6")])),
        ("  same model, every wafer assumed flat",
         write(ident, ctx, "flat", [(r"^    SAG_GRID_M = .*$", "    SAG_GRID_M = np.array([0.0])")])),
        ("  same model, every wafer assumed at +55 um sag",
         write(ident, ctx, "sag", [(r"^    SAG_GRID_M = .*$", "    SAG_GRID_M = np.array([55e-6])")])),
        ("  same model, every wafer assumed at -55 um (dished)",
         write(ident, ctx, "dish", [(r"^    SAG_GRID_M = .*$", "    SAG_GRID_M = np.array([-55e-6])")])),
        ("  reference with guard 2.0 K and release margin 1.0 C",
         write(ident, ctx, "conservative", [(r"^    GUARD_K = .*$", "    GUARD_K = 2.0"),
                                            (r"^    RELEASE_MARGIN_C = .*$", "    RELEASE_MARGIN_C = 1.0")])),
        ("  reference with no guard and no release margin",
         write(ident, ctx, "bare", [(r"^    GUARD_K = .*$", "    GUARD_K = 0.0"),
                                    (r"^    RELEASE_MARGIN_C = .*$", "    RELEASE_MARGIN_C = 0.0")])),
    ]
    for abl, label in (("no-lag", "  re-identified without the pressure lag"),
                       ("no-plate", "  re-identified with the plate held at setpoint")):
        ia, ca = identify(abl)
        rungs.append((label + " (fit rms %.2f vs %.2f)" % (ia["rms"], ident["rms"]),
                      write(ia, ca, abl)))
    for label, path in rungs:
        t0 = time.time()
        s = grade_controller(path, truth, bench)
        print("%-58s %7.3f %5d/24 %5d %4d %5d %8.2f %8.2f   [%.0f s]"
              % (label, s["ratio"], s["failed"], s["zone"], s["hot"], s["late"],
                 s["worst_zone"], s["hottest"], time.time() - t0), flush=True)

    print("\nHINDSIGHT BOUNDS, tuned on the hidden wafers themselves (no controller can do better")
    print("within its class)")
    recipe, known = constant_pressure_bounds(truth, bench)
    print("%-58s %7.3f   (every wafer passes by construction)"
          % ("one constant pressure and release time per station+film", recipe))
    print("%-58s %7.3f   (every wafer passes by construction)"
          % ("best constant pressure per wafer, sag known, exact release", known), flush=True)
    ratio, fails, detail = model_free_bound(truth, bench)
    print("%-58s %7.3f %5d/24 failed at the best tuning" % (
        "model-free PI on the spot difference, release on spots", ratio, fails))
    for st, (f, tot, (combo, a, th)) in detail.items():
        print("      station %s: setpoint %.0f K, kp %.1f, ki %.1f, base %.0f Torr, release when "
              "%.2f*centre + %.2f*edge <= %.2f C -> %d failed" % (st, combo[0], combo[1], combo[2],
                                                                  combo[3], a, 1 - a, th, f))
    print("\n[ladder %.0f s]" % (time.time() - t00))


if __name__ == "__main__":
    main()
