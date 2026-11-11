"""Two measured design rules for the fleet: is each chamber's gas budget load-bearing, and is it identifiable?

The independent review of 11 November found that at the 16 h reference the mechanism split was worth 0.0% of the
graded answer, and that once the reference moved to 36 h the split mattered on only three chambers, two of which
could not be identified from any record or any one test. Both properties are measured here, on the sealed physics,
before any solver is written, so the fleet is designed to them rather than discovered to fail them.

*Load-bearing.* The cheapest routes to a chamber's gas load use one log entry: take its gas load, subtract the
permeation the register's seal gives, and carry the rest to the reference condition either as a constant (a leak,
with the wall at the table's nominal figure) or as wall gas. A chamber is load-bearing when every such route, on
every entry, misses the truth by at least SHORTCUT_X times the tolerance or names the wrong cause. Noise-free, so
the rule is about the physics and not about a lucky draw.

*Identifiable.* A sound solver fits the gas budget of MS-BP to the chamber's records: a wall coefficient, a leak,
and a trapped volume where the data call for one, with the seal's permeation taken from the table for whichever
elastomer fits best. It chooses among structures by the quality of the fit. Run on the true gas loads with the
shop's read noise, it must land within the tolerance, with the right cause, on at least IDENT_P of draws. One
chamber may need the audit test to get there (the budget is one test); it is identified with the records plus that
test, and must NOT be identifiable from its records alone.

The solver here is the truth's own: it is given gas loads, not readings, so every instrument and configuration
layer is taken as solved. It measures whether the gas budget can be identified at all, which no instrument fix
can supply.

    python3 -I identify.py            # the table, both rules, every chamber
"""
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpphys as P                                                      # noqa: E402
import fleet as F                                                       # noqa: E402

Q_TOL = 0.040                       # the gas-load tolerance the design is measured against
SHORTCUT_X = 2.0                    # a single-entry route must miss by this many tolerances
IDENT_P = 0.99                      # a sound solver must be right on this share of draws
READ_NOISE = 0.006                  # one gauge reading, lognormal sd (build.py's READ_NOISE)
TEST_NOISE = 0.005                  # the audit test's gas-load observation
DRAWS = 300
TAUS = np.exp(np.linspace(math.log(1.0), math.log(P.TAU_MAX), 48))
MATERIALS = tuple(sorted(P.SEALS))

# events that change the gas budget; a trapped volume is handled separately, because the entries before it are
# still a true record of the wall and the leak
GAS_EVENTS = ("internals", "seal", "seal_len", "leak")


def _last_gas_change(ch):
    ds = [d for d, k, _a in ch["events"] if k in GAS_EVENTS]
    return max(ds) if ds else "0000-00-00"


def _trapped_from(ch):
    ds = [d for d, k, _a in ch["events"] if k == "trapped"]
    return max(ds) if ds else None


def observations(ch):
    """One row per pumpdown that still describes the chamber: its date, pumping time, wall temperature, the wall
    regressor (the table's nominal wall load for its surfaces, vent and temperature), the seal's permeation per
    material, whether a trapped volume was present, and the true gas load."""
    since = _last_gas_change(ch)
    tf = _trapped_from(ch)
    seen, rows = set(), []
    for e in ch["log"]:
        date, pid, vent, h, tc, _ser, load = e[:7]
        if date < since or (date, pid) in seen:
            continue
        seen.add((date, pid))
        c = F.config(ch, date)
        if load:
            c = dict(c, surfaces=list(c["surfaces"]) + F.load_surfaces([load], F.FIXTURES))
        T = tc + 273.15
        rows.append(dict(date=date, t=h, T=T, vent=vent,
                         W=P.q_wall_nominal(c["surfaces"], h, vent, T),
                         perm={m: P.q_perm(m, c["seal_cm"], T) for m in MATERIALS},
                         trapped=bool(tf and date >= tf),
                         q=P.q_total(c, h, vent, T)))
    return rows


def test_observation(ch, t_h):
    """The audit test as one extra gas-load observation, at the contractor's wall temperature on the day."""
    c = F.config(ch)
    tc = F.AUDIT_TESTS[ch["id"]][1]
    T = tc + 273.15
    return dict(date=F.AUDIT, t=t_h, T=T, vent="air", W=P.q_wall_nominal(c["surfaces"], t_h, "air", T),
                perm={m: P.q_perm(m, c["seal_cm"], T) for m in MATERIALS},
                trapped=bool(_trapped_from(ch)), q=P.q_total(c, t_h, "air", T), test=True)


def reference_regressors(ch):
    c = F.config(ch)
    return dict(W=P.q_wall_nominal(c["surfaces"], F.REF_H, "air", P.T_REF),
                perm={m: P.q_perm(m, c["seal_cm"], P.T_REF) for m in MATERIALS})


# ----------------------------------------------------------------------------------------------------------------
def _nnls(A, b):
    from scipy.optimize import nnls
    x, rnorm = nnls(A, b)
    return x, rnorm


def fit(rows, qn, material, trapped):
    """Relative least squares of q = C_w W + Q_L [+ Q_v0 exp(-t/tau) after the trapped volume appeared] + Q_perm,
    with every coefficient non-negative. tau by grid, the rest linear. Returns (chi2 in units of the read noise,
    number of parameters, the parameters)."""
    W = np.array([r["W"] for r in rows])
    PM = np.array([r["perm"][material] for r in rows])
    H = np.array([r["t"] for r in rows])
    TR = np.array([1.0 if r["trapped"] else 0.0 for r in rows])
    sig = np.array([TEST_NOISE if r.get("test") else READ_NOISE for r in rows])
    w = 1.0 / (qn * sig)
    y = (qn - PM) * w
    best = None
    taus = TAUS if trapped else [None]
    for tau in taus:
        cols = [W, np.ones_like(W)]
        if tau is not None:
            cols.append(TR * np.exp(-H / tau))
        A = np.column_stack(cols) * w[:, None]
        x, rn = _nnls(A, y)
        chi2 = rn * rn
        if best is None or chi2 < best[0]:
            best = (chi2, x, tau)
    chi2, x, tau = best
    k = 2 + (2 if trapped else 0)
    return chi2, k, dict(c_w=x[0], leak=x[1], qv0=x[2] if trapped else 0.0, tau=tau, material=material)


def at_reference(ref, params):
    comp = {"wall-outgassing": params["c_w"] * ref["W"],
            "air-leak": params["leak"],
            "virtual-leak": params["qv0"] * math.exp(-F.REF_H / params["tau"]) if params["tau"] else 0.0,
            "permeation": ref["perm"][params["material"]]}
    return comp, sum(comp.values())


OVERRIDE_CHI2 = 10.0                # how much better another seal material must fit before it overrides the documents


def documented_seal(ch):
    """The seal material the documents give: the register's, or the last seal change in the maintenance log."""
    m = ch["reg"]["seal"]
    for _d, k, a in ch["events"]:
        if k == "seal":
            m = a[0]
    return m


def solve(rows, qn, has_trap_event, documented):
    """The sound solver: every admissible structure, chosen by AIC. A structure is admissible only where there are
    at least as many observations as parameters. The documented seal material is taken unless another fits the
    records better by OVERRIDE_CHI2: an engineer does not overturn the register on a marginal fit, but does when the
    data plainly contradict it."""
    n = len(rows)
    cands = []
    for m in MATERIALS:
        for tr in ((False, True) if has_trap_event else (False,)):
            k = 2 + (2 if tr else 0)
            if n < k:
                continue
            chi2, k, p = fit(rows, qn, m, tr)
            cands.append((chi2 + 2 * k + (0.0 if m == documented else OVERRIDE_CHI2), chi2, p))
    cands.sort(key=lambda c: c[0])
    return cands[0][2]


# ----------------------------------------------------------------------------------------------------------------
def shortcut_errors(ch):
    """Every single-entry route, noise-free: (pumpdown, mode, relative error, cause it names)."""
    tr = F.truth(ch)
    ref = reference_regressors(ch)
    reg_seal = ch["reg"]["seal"]
    # where the maintenance log changes the seal, the route uses the material the log says, as anyone would
    seal_now = reg_seal
    for d, k, a in ch["events"]:
        if k == "seal":
            seal_now = a[0]
    out = []
    for r in observations(ch):
        pm, pm_ref = r["perm"][seal_now], ref["perm"][seal_now]
        for mode in ("leak", "wall"):
            if mode == "leak":
                comp = {"wall-outgassing": ref["W"], "air-leak": max(r["q"] - r["W"] - pm, 0.0),
                        "virtual-leak": 0.0, "permeation": pm_ref}
            else:
                cw = max(r["q"] - pm, 0.0) / r["W"]
                comp = {"wall-outgassing": cw * ref["W"], "air-leak": 0.0, "virtual-leak": 0.0,
                        "permeation": pm_ref}
            q = sum(comp.values())
            cause = "pump-speed" if tr["cause"] == "pump-speed" else max(comp, key=comp.get)
            out.append((r["date"], mode, q / tr["q_total"] - 1.0, cause))
    return out


def load_bearing(ch):
    tr = F.truth(ch)
    errs = shortcut_errors(ch)
    survivors = [e for e in errs if abs(e[2]) < SHORTCUT_X * Q_TOL and e[3] == tr["cause"]]
    nearest = min((abs(e[2]) for e in errs if e[3] == tr["cause"]), default=float("inf"))
    return not survivors, nearest, survivors


def identifiability(ch, test_time=None, draws=DRAWS, seed=7):
    """Share of draws on which the sound solver is within the tolerance with the right cause; the error spread."""
    tr = F.truth(ch)
    rows = observations(ch)
    if test_time is not None:
        rows = rows + [test_observation(ch, test_time)]
    ref = reference_regressors(ch)
    q = np.array([r["q"] for r in rows])
    sig = np.array([TEST_NOISE if r.get("test") else READ_NOISE for r in rows])
    rng = np.random.default_rng([seed, F.CHAMBER_IDS.index(ch["id"]) if ch["id"] in F.CHAMBER_IDS else 99])
    has_trap = _trapped_from(ch) is not None
    documented = documented_seal(ch)
    ok, errs, wrong_seal = 0, [], 0
    for _ in range(draws):
        qn = q * np.exp(rng.normal(0.0, sig))
        p = solve(rows, qn, has_trap, documented)
        wrong_seal += p["material"] != F.config(ch)["seal"]
        comp, qref = at_reference(ref, p)
        cause = "pump-speed" if tr["cause"] == "pump-speed" else max(comp, key=comp.get)
        e = qref / tr["q_total"] - 1.0
        errs.append(e)
        ok += abs(e) <= Q_TOL and cause == tr["cause"]
    errs = np.array(errs)
    return ok / draws, float(np.std(errs)), float(np.percentile(np.abs(errs), 99))


def best_test_time(ch, times=(16.0, 24.0, 30.0, 36.0, 42.0, 48.0)):
    res = [(identifiability(ch, t, draws=150)[0], t) for t in times]
    return max(res), res


def main():
    print("Load-bearing (single-entry routes miss by >= %.0fx the %.1f%% tolerance or name the wrong cause)"
          % (SHORTCUT_X, 100 * Q_TOL))
    print("and identifiable (sound solver right on >= %.2f of %d draws, %.1f%% read noise)" % (IDENT_P, DRAWS,
                                                                                        100 * READ_NOISE))
    print("")
    print("chamber  cause            load-bearing  nearest route   records alone        with the best test")
    fails = []
    for cid in F.CHAMBER_IDS:
        ch = F.BY[cid]
        tr = F.truth(ch)
        lb, nearest, surv = load_bearing(ch)
        p_rec, sd, p99 = identifiability(ch)
        line = "  %s   %-15s %-12s  %6.1f%%        P=%.2f sd %4.1f%%" % (
            cid, tr["cause"], "yes" if lb else "NO (%d)" % len(surv), 100 * nearest, p_rec, 100 * sd)
        if p_rec < IDENT_P:
            (p_t, t_best), _ = best_test_time(ch)
            line += "     P=%.2f at %.0f h" % (p_t, t_best)
        print(line)
        if not lb:
            fails.append("%s is not load-bearing: %d single-entry route(s) within %.0fx the tolerance"
                         % (cid, len(surv), SHORTCUT_X))
    print("")
    for f in fails:
        print("FAIL", f)
    return 0


if __name__ == "__main__":
    sys.exit(main())
