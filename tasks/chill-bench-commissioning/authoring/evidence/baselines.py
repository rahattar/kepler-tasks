"""Baseline ladder for the commissioning-bench design.

Each rung is a complete commissioning strategy: a campaign (which stations to spend
the budget on), a model for reaching the stations it did not measure, and a margin
policy. Every rung is built only from what an agent can see -- the public inspection
report and the traces the bench returns -- and is then graded by the real grader.

MEASURED stations. `validate_fit()` recovers one station's accommodation coefficient
by least squares on its own bench trace and reports the error. ident.py already
measured the identifiability: a 0.02 change in the coefficient moves the trace by
2-3.6 K against 0.5 K per-sample noise, so a single run pins it to a few parts in a
thousand. The ladder therefore models a measured station as the true coefficient plus
a small identification error rather than repeating that fit 350 times.

UNMEASURED stations can only be reached through a model fitted across the measured
ones, so the ladder isolates the model, not the physics.

Margin policy, identical on every rung so the comparison is fair: the reference's own.
The dwell is the station's optimum at the estimated coefficient times (1 + allowance -
1.5%), and the pressure is the geometric centre of the band that dwell opens. Under
the jump-distance form the optimum dwell does not depend on the coefficient at all, so
a coefficient error moves only the pressure, and centring tolerates the largest error
the allowance can absorb in either direction. A rung fails only because its model put
the coefficient outside that band.

The structure being tested: sixteen stations from twelve passivation lots, eight runs.
The lot effect is carried by the lot's bath temperature through a saturating relation.
So the rungs are the models a solver might reach for, in roughly the order a hurried
one tries them: lot intercepts (cannot cover twelve lots with eight runs), a straight
line in bath temperature (the natural first continuous model, and wrong), a quadratic
(curvature acknowledged), and a hinge (the shape that is actually there). Each is run
under more than one campaign so that campaign luck is visible separately from model
choice.

The campaigns differ in one geometric property. Seven stations are vertices of the
fleet's convex hull in (roughness, bath temperature); no model can interpolate to a
hull vertex, so a campaign that leaves one unmeasured extrapolates to it however well
it samples the rest. The reference measures all seven plus one. The campaign most
probe agents converged on, and the reference's own previous campaign, each leave out
S09, the low-roughness plateau corner.
"""
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
# The shipped verifier and the sealed bench core, not copies of them: a duplicated
# grader in this directory is how the ladder came to be scored against a retired gate.
sys.path.insert(0, os.path.join(ROOT, "tests"))
sys.path.insert(0, os.path.join(ROOT, "environment", "bench"))

import grade
import physics as ph
import bench_core as core
sys.path.insert(0, HERE)
import design_mc

TR = grade.load_truth()
SPEC = TR["spec"]
T_TGT = SPEC["target_mean_temperature_C"]
CAP = SPEC["max_zone_difference_K"]
P_LO, P_HI = SPEC["he_pressure_min_torr"], SPEC["he_pressure_max_torr"]
NEED = SPEC["min_stations_commissioned"]
PUB = {r["station"]: r for r in TR["stations"]}
NAMES = [r["station"] for r in TR["stations"]]

IDENT_ERR = 0.006          # what the reference's identification actually achieves
DELTA = SPEC["dwell_budget_fraction"]
T_MARGIN = 0.015           # the reference's own margin against its optimum estimate
MEAS_MARGIN = 0.0          # kept for the detail print; centring needs no hedge
COVER = U_FLOOR = HEDGE_CAP = 0.0
FIT_P, FIT_S = 12.0, 18.0

OUT = os.environ.get("TMPDIR") or "/tmp"

_pgrid = np.exp(np.linspace(np.log(P_LO), np.log(40.0), 400))
_cache = {}
_rng = np.random.default_rng(4242)
DETAIL = []


def _station(name, alpha):
    r = PUB[name]
    return ph.Station(name, r["inner_standoff_um"] * 1e-6,
                      r["outer_standoff_um"] * 1e-6, r["incoming_temperature_C"],
                      r["plate_setpoint_C"], alpha, alpha)


def _metrics(name, alpha):
    key = (name, round(float(alpha), 4))
    if key not in _cache:
        _cache[key] = ph.cooldown_metrics(_pgrid, _station(name, key[1]), T_TGT)
    return _cache[key]


def validate_fit(name):
    """Recover one station's coefficient from its own bench trace, by least squares."""
    _, rows = core.trace(name, FIT_P, FIT_S, 1)
    arr = np.array([[float(x) for x in r] for r in rows])
    t_obs, T_obs = arr[:, 0], arr[:, 1]

    def sse(a):
        t, Tm, _, _, _ = ph.integrate(FIT_P, _station(name, float(a)), t_max=FIT_S)
        return float(np.sum((np.interp(t_obs, t, Tm) - T_obs) ** 2))

    g = np.arange(0.15, 0.701, 0.025)
    v = [sse(a) for a in g]
    j = int(np.argmin(v))
    lo, hi = g[max(0, j - 1)], g[min(len(g) - 1, j + 1)]
    g2 = np.linspace(lo, hi, 9)
    v2 = [sse(a) for a in g2]
    return float(g2[int(np.argmin(v2))])


def measured(name):
    return PUB[name]["_alpha"] + _rng.normal(0.0, IDENT_ERR)


def recipe_for(name, alpha_hat, u=None):
    """The reference's own policy, applied identically on every rung.

    Under the jump-distance form the optimum dwell does not depend on the coefficient,
    so the dwell is set from the station's optimum at alpha_hat, less the reference's
    own margin, and the pressure is placed at the geometric centre of the band that
    dwell opens. Both band edges are interpolated in log pressure between grid points,
    so the recipe is centred to well under a tenth of a percent rather than to the
    grid's one-percent step. `u` is accepted for signature compatibility and ignored:
    centring already spends the whole allowance on tolerance in both directions.
    """
    t_hit, dT = _metrics(name, alpha_hat)
    lp = np.log(_pgrid)
    ok = np.isfinite(dT) & (dT <= CAP)
    if not ok.any():
        return P_LO, 30.0
    j = int(np.flatnonzero(ok)[-1])
    if j + 1 < len(lp) and np.isfinite(dT[j + 1]) and dT[j + 1] > dT[j]:
        fr = (CAP - dT[j]) / (dT[j + 1] - dT[j])
        lp_opt = lp[j] + fr * (lp[j + 1] - lp[j])
        t_opt = t_hit[j] + fr * (t_hit[j + 1] - t_hit[j])
    else:
        lp_opt, t_opt = lp[j], t_hit[j]
    dwell = float(t_opt) * (1.0 + DELTA - T_MARGIN)
    reach = np.isfinite(t_hit) & (t_hit <= dwell)
    if not reach.any():
        return float(np.exp(lp_opt)), dwell
    k = int(np.flatnonzero(reach)[0])
    if k > 0 and np.isfinite(t_hit[k - 1]) and t_hit[k - 1] > t_hit[k]:
        fr = (t_hit[k - 1] - dwell) / (t_hit[k - 1] - t_hit[k])
        lp_low = lp[k - 1] + fr * (lp[k] - lp[k - 1])
    else:
        lp_low = lp[k]
    return float(np.exp(0.5 * (lp_low + lp_opt))), dwell


def fit(campaign, model):
    """Returns (predictor over any station, residual per dof, measured dict).

    Models, in the order a hurried agent tends to try them:
      dummies  lot intercepts + roughness slope; a lot it never measured gets the
               fleet mean of the measured coefficients (the only thing left)
      linear   intercept + roughness + bath temperature, straight
      quad     ... + bath temperature squared
      hinge    intercept + roughness + min(bath, knee), knee chosen on a grid
    """
    y = np.array([measured(n) for n in campaign])
    ra = np.array([PUB[n]["plate_roughness_Ra_um"] for n in campaign])
    tb = np.array([PUB[n]["passivation_bath_C"] for n in campaign])
    lot = np.array([PUB[n]["passivation_lot"] for n in campaign])

    def solve(A):
        c, *_ = np.linalg.lstsq(A, y, rcond=None)
        r = y - A @ c
        return c, float(np.sum(r ** 2)), max(1, len(y) - A.shape[1])

    if model == "dummies":
        touched = sorted(set(lot))
        A = np.column_stack([ra] + [(lot == L).astype(float) for L in touched])
        c, sse, dof = solve(A)
        fleet_mean, ra_mean = float(np.mean(y)), float(np.mean(ra))

        def pred(n):
            r = PUB[n]
            if r["passivation_lot"] in touched:
                return float(c[0] * r["plate_roughness_Ra_um"]
                             + c[1 + touched.index(r["passivation_lot"])])
            return float(fleet_mean + c[0] * (r["plate_roughness_Ra_um"] - ra_mean))
    elif model == "linear":
        c, sse, dof = solve(np.column_stack([np.ones_like(y), ra, tb]))
        pred = lambda n: float(c[0] + c[1] * PUB[n]["plate_roughness_Ra_um"]
                               + c[2] * PUB[n]["passivation_bath_C"])
    elif model == "quad":
        c, sse, dof = solve(np.column_stack([np.ones_like(y), ra, tb, tb ** 2]))
        pred = lambda n: float(c[0] + c[1] * PUB[n]["plate_roughness_Ra_um"]
                               + c[2] * PUB[n]["passivation_bath_C"]
                               + c[3] * PUB[n]["passivation_bath_C"] ** 2)
    elif model == "hinge":
        best = None
        for knee in np.arange(42.0, 62.01, 0.5):
            c, sse, _ = solve(np.column_stack([np.ones_like(y), ra,
                                               np.minimum(tb, knee)]))
            if best is None or sse < best[0]:
                best = (sse, knee, c)
        sse, knee, c = best
        dof = max(1, len(y) - 4)          # the knee is a parameter too
        pred = lambda n: float(c[0] + c[1] * PUB[n]["plate_roughness_Ra_um"]
                               + c[2] * min(PUB[n]["passivation_bath_C"], knee))
    elif model == "hinge_lumped":
        # The same hinge, but regressed on the lumped conductance coefficient
        # alpha/(2-alpha), which is what an agent identifies if it fits the gap as
        # h = 1/(d/k + 1/(A P)) and never converts A back to the accommodation
        # coefficient. alpha/(2-alpha) is a curved function of alpha, so a relation
        # that is linear in alpha is not linear in it.
        z = y / (2.0 - y)
        best = None
        for knee in np.arange(42.0, 62.01, 0.5):
            X = np.column_stack([np.ones_like(z), ra, np.minimum(tb, knee)])
            c, *_ = np.linalg.lstsq(X, z, rcond=None)
            r = z - X @ c
            if best is None or float(np.sum(r ** 2)) < best[0]:
                best = (float(np.sum(r ** 2)), knee, c)
        _, knee, c = best
        def pred(n):
            zz = (c[0] + c[1] * PUB[n]["plate_roughness_Ra_um"]
                  + c[2] * min(PUB[n]["passivation_bath_C"], knee))
            return float(2.0 * zz / (1.0 + zz))
        res = y - np.array([pred(n) for n in campaign])
        sse, dof = float(np.sum(res ** 2)), max(1, len(y) - 4)
    else:
        raise ValueError(model)
    return pred, float(np.sqrt(sse / dof)), dict(zip(campaign, y))


def build(campaign, model, honest_u=True, fixed_alpha=None):
    if fixed_alpha is not None:
        rec = [{"station": n, **dict(zip(("he_pressure_torr", "dwell_s"),
                                         [round(v, 3) for v in
                                          recipe_for(n, fixed_alpha, 0.0)]))}
               for n in NAMES]
        return {"stations": rec}, 0.0, max(abs(fixed_alpha - PUB[n]["_alpha"])
                                           for n in NAMES), 0
    pred, u_fit, known = fit(campaign, model)
    u = u_fit if honest_u else 0.0
    rec, err = [], []
    for n in NAMES:
        if n in known:
            a_hat, uu = known[n], MEAS_MARGIN
        else:
            a_hat = pred(n)
            uu = 0.0
            err.append(abs(a_hat - PUB[n]["_alpha"]))
        P, dw = recipe_for(n, a_hat, uu)
        rec.append({"station": n, "he_pressure_torr": round(P, 3),
                    "dwell_s": round(dw, 3)})
        DETAIL.append({"station": n, "measured": n in known, "alpha_hat": a_hat,
                       "alpha_true": PUB[n]["_alpha"], "margin": uu})
    return {"stations": rec}, u, (max(err) if err else 0.0), len(err)


CAMPAIGNS = {
    # the first eight in the file: an accident of ordering, five lots below the knee
    "first 8 listed":  ["S01", "S02", "S03", "S04", "S05", "S06", "S07", "S08"],
    # what most probe agents converged on: the same-lot roughness pair first, both bath
    # extremes, the roughness extreme, then three points along the cold ramp
    "probe standard":  ["S05", "S08", "S06", "S04", "S07", "S11", "S01", "S15"],
    # the same, with the roughness extreme traded for the low-roughness plateau corner
    "probe + corner":  ["S05", "S08", "S06", "S07", "S11", "S01", "S15", "S09"],
    # the previous reference: eight distinct lots, dense on the cold ramp. Inside the
    # range of each covariate, but S09 lies outside the hull of what it measures.
    "eight lots":      ["S07", "S15", "S11", "S01", "S05", "S13", "S04", "S06"],
    # the shipped reference: the seven vertices of the fleet's hull in (roughness, bath
    # temperature), plus the station that minimises the worst prediction variance
    "hull + 1":        ["S07", "S15", "S11", "S05", "S09", "S04", "S16", "S06"],
}

LADDER = [
    ("no bench runs, literature coefficient 0.40", None, None, True, 0.40),
    ("probe standard, lot intercepts", "probe standard", "dummies", True, None),
    ("hull + 1, lot intercepts", "hull + 1", "dummies", True, None),
    ("probe standard, straight line in bath temp", "probe standard", "linear", True, None),
    ("hull + 1, straight line in bath temp", "hull + 1", "linear", True, None),
    ("probe standard, quadratic in bath temp", "probe standard", "quad", True, None),
    ("hull + 1, quadratic in bath temp", "hull + 1", "quad", True, None),
    ("first 8 listed, hinge", "first 8 listed", "hinge", True, None),
    ("probe standard, hinge in lumped coefficient", "probe standard", "hinge_lumped", True, None),
    ("probe standard, hinge", "probe standard", "hinge", True, None),
    ("eight lots (previous reference), hinge", "eight lots", "hinge", True, None),
    ("probe + corner, hinge in lumped coefficient", "probe + corner", "hinge_lumped", True, None),
    ("probe + corner, hinge", "probe + corner", "hinge", True, None),
    ("hull + 1, hinge in lumped coefficient", "hull + 1", "hinge_lumped", True, None),
    ("hull + 1 (the reference's plan), hinge", "hull + 1", "hinge", True, None),
]


def window_fails(rec_detail):
    """Stations the exact windows (station_windows.json) say this draw loses."""
    out = set()
    for d in rec_detail:
        e = abs(design_mc.lnf(d["alpha_true"]) - design_mc.lnf(d["alpha_hat"]))
        if e > design_mc.TOL[design_mc.NAMES.index(d["station"])]:
            out.add(d["station"])
    return out


def noise_rate(camp, model, n=400):
    """Fraction of identification-noise draws on the shipped fleet that clear the gate."""
    if camp is None:
        return float("nan")
    idx = np.array([design_mc.NAMES.index(c) for c in CAMPAIGNS[camp]])
    a0 = np.array([PUB[nm]["_alpha"] for nm in design_mc.NAMES])
    rng = np.random.default_rng(17)
    return float(np.mean([len(design_mc.failures(model, idx, a0, rng)) <= len(NAMES) - NEED
                          for _ in range(n)]))


if __name__ == "__main__":
    t0 = time.time()
    v = validate_fit("S06")
    print("fit validation: S06 coefficient recovered as %.4f from one bench trace, "
          "true %.4f (error %.4f)\n" % (v, PUB["S06"]["_alpha"],
                                        abs(v - PUB["S06"]["_alpha"])))
    print("fleet: %d stations, %d lots, budget %d, gate %d of %d\n"
          % (len(NAMES), len({r["passivation_lot"] for r in PUB.values()}),
             TR["budget_runs"], NEED, len(NAMES)))

    print("Every rung below is one complete draw, graded by the shipped verifier. 'noise'")
    print("is the fraction of 400 further identification-noise draws on the same fleet that")
    print("clear the gate, from the exact per-station windows (design_mc.py), and 'windows'")
    print("checks that those windows predict exactly the stations the verifier failed.\n")
    print("%-46s %6s %8s %6s %7s %7s %8s  %s"
          % ("strategy", "u", "max err", "comm", "reward", "noise", "windows",
             "stations lost to"))
    print("-" * 124)
    agree = total = 0
    for label, camp, model, honest, fixed in LADDER:
        DETAIL.clear()
        rec, u, mx, n_un = build(CAMPAIGNS.get(camp), model, honest, fixed)
        rp = os.path.join(OUT, "rec.json")
        with open(rp, "w") as f:
            json.dump(rec, f)
        r = grade.grade(rp, TR)
        bad = []
        if r["error"]:
            bad = [r["error"]]
        else:
            for key, tag in (("meets_temperature", "temperature"),
                             ("meets_uniformity", "uniformity"),
                             ("meets_dwell_budget", "dwell budget")):
                n = sum(1 for s in r["stations"] if not s[key])
                if n:
                    bad.append(f"{tag} ({n})")
        lost = [] if r["error"] else sorted(
            x["station"] for x in r["stations"]
            if not (x["meets_temperature"] and x["meets_uniformity"]
                    and x["meets_dwell_budget"]))
        if fixed is None and not r["error"]:
            wf = window_fails(DETAIL)
            same = wf == set(lost)
            agree += same
            total += 1
            wtag = "agree" if same else "DIFFER"
        else:
            wtag = "-"
        print("%-46s %6.4f %8.4f %6s %7d %6.0f%% %8s  %s%s   [%.0fs]"
              % (label, u, mx,
                 "-" if r["error"] else "%2d/%d" % (r["commissioned"], len(NAMES)),
                 r["reward"], 100 * noise_rate(camp, model) if camp else float("nan"),
                 wtag, ", ".join(bad) if bad else "-",
                 (" -- " + " ".join(lost)) if 0 < len(lost) <= 4 else "",
                 time.time() - t0), flush=True)
        if wtag == "DIFFER":
            for d in DETAIL:
                if (d["station"] in wf) != (d["station"] in lost):
                    e = abs(design_mc.lnf(d["alpha_true"]) - design_mc.lnf(d["alpha_hat"]))
                    w = design_mc.TOL[design_mc.NAMES.index(d["station"])]
                    print("        %s (%s): log error %.4f against a window of %.4f; the "
                          "verifier %s it"
                          % (d["station"], "measured" if d["measured"] else "predicted",
                             e, w, "failed" if d["station"] in lost else "passed"))
        if label == LADDER[-1][0] and not r["error"]:
            print("-" * 124)
            print("windows predicted the verifier's verdict on every station of %d of %d "
                  "rungs; any difference is listed under its rung with its distance from "
                  "the window edge" % (agree, total))
            det = {d["station"]: d for d in DETAIL}
            print("      per station on the correct-model rung:")
            for row in r["stations"]:
                d = det[row["station"]]
                print("        %-4s %-9s a=%.4f true=%.4f err=%+.4f marg=%.4f | "
                      "P=%5.2f dw=%6.3f T=%6.2f dT=%5.2f x%.3f%s%s%s"
                      % (row["station"], "measured" if d["measured"] else "predicted",
                         d["alpha_hat"], d["alpha_true"],
                         d["alpha_hat"] - d["alpha_true"], d["margin"],
                         row["he_pressure_torr"], row["dwell_s"], row["T_end_C"],
                         row["zone_diff_K"], row["dwell_ratio"],
                         "" if row["meets_temperature"] else "  TEMP",
                         "" if row["meets_uniformity"] else "  UNIF",
                         "" if row["meets_dwell_budget"] else "  BUDGET"), flush=True)
