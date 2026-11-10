"""Exactly how much coefficient error each station's recipe can absorb.

In the jump-distance form the gap conductance depends on helium pressure P and
accommodation coefficient a only through the effective pressure

    P_eff = P * f(a),    f(a) = a / (2 - a),

so the whole cooldown of a station is a function of P_eff alone. Two consequences carry
the whole design:

  * the optimum dwell does not depend on the coefficient at all -- only the pressure that
    realises it does;
  * an error in the coefficient is EXACTLY an error in pressure. A recipe built for a
    coefficient a_hat but run on a station whose coefficient is a delivers
    P_eff * f(a) / f(a_hat), so what decides the outcome is the log error
    e = ln f(a) - ln f(a_hat), not the error in a itself.

For each station this script fixes the dwell where a careful recipe puts it -- the
station's optimum x (1 + allowance - 1.5%) -- and finds, at the true coefficient, the
band of pressures that both reaches the temperature target by then and keeps the zone
difference under its limit for the whole dwell. A recipe centred in that band survives
any |e| up to half the band's log-width. Because the band lives in P_eff, it is a
property of the station's geometry and temperatures only; it does not change when the
coefficients are redrawn, which is what lets design_mc.py use it across fleets.

In terms of the coefficient itself, d ln f / d ln a = 2 / (2 - a), so a given band
tolerates a relative coefficient error smaller by (2 - a)/2: about 15% smaller on the
low-coefficient stations, 28% smaller on the highest.

The reference does not centre exactly: it places the top of its band 0.35 K under the
zone limit (a guard against its own discretisation), which shifts its centre toward low
pressure. That buys tolerance for an under-predicted coefficient -- the zone side --
and spends tolerance for an over-predicted one. Both are reported.

    python3 station_windows.py           # writes station_windows.json beside it
"""
import json
import os
import sys
from multiprocessing import Pool

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tests"))

import grade
import physics as ph

MARGIN = 0.015          # the reference's margin against its own optimum estimate
GUARD_K = 0.35          # the reference's zone guard


def f(a):
    return a / (2.0 - a)


def _crossing(P, y, level, rising):
    """Pressure where y crosses level, interpolated in log P on the scanned grid."""
    ok = (y >= level) if rising else (y <= level)
    idx = np.flatnonzero(ok)
    if idx.size == 0:
        return np.nan
    j = idx[0]
    if j == 0:
        return float(P[0])
    x0, x1 = np.log(P[j - 1]), np.log(P[j])
    y0, y1 = y[j - 1], y[j]
    frac = (level - y0) / (y1 - y0) if y1 != y0 else 0.0
    return float(np.exp(x0 + frac * (x1 - x0)))


def band(st, dwell, p_opt, spec, lo=0.70, hi=1.03, n=500):
    """(p_low, p_high, p_high_guarded) at a fixed dwell, at the station's true coefficient."""
    P = np.exp(np.linspace(np.log(lo * p_opt), np.log(hi * p_opt), n))
    t, Tm, Ti, To, _ = ph.integrate(P, st, t_max=dwell + 0.05)
    i = min(max(int(np.searchsorted(t, dwell)), 1), len(t) - 1)
    frac = (dwell - t[i - 1]) / (t[i] - t[i - 1])
    T_end = Tm[i - 1] + frac * (Tm[i] - Tm[i - 1])
    zone = np.abs(Ti - To)[:i + 1].max(axis=0)
    p_low = _crossing(P, T_end, spec["target_mean_temperature_C"], rising=False)
    cap = spec["max_zone_difference_K"]
    p_high = _crossing(P, zone, cap, rising=True)
    p_high_g = _crossing(P, zone, cap - GUARD_K, rising=True)
    return p_low, p_high, p_high_g


def one(args):
    name, truth_path, allowance = args
    truth = json.load(open(truth_path))
    spec = truth["spec"]
    st = {s.name: s for s in grade._stations(truth)}[name]
    o = ph.fastest_feasible(st, spec["target_mean_temperature_C"],
                            spec["max_zone_difference_K"], spec["he_pressure_min_torr"],
                            spec["he_pressure_max_torr"])
    p_opt, t_opt = o[0], o[1]
    dwell = t_opt * (1.0 + allowance - MARGIN)
    p_low, p_high, p_high_g = band(st, dwell, p_opt, spec)
    a = st.alpha_wafer
    w = 0.5 * np.log(p_high / p_low)                 # centred: +/- w in ln f
    c_g = np.sqrt(p_low * p_high_g)                  # the reference's guarded centre
    up_g, dn_g = np.log(p_high / c_g), np.log(c_g / p_low)

    def a_at(lnf_shift):
        """The coefficient estimate whose ln f sits lnf_shift from the truth's."""
        ff = f(a) * np.exp(lnf_shift)
        return 2.0 * ff / (1.0 + ff)

    return dict(station=name, alpha=a, p_opt=p_opt, t_opt=t_opt, dwell=dwell,
                p_low=p_low, p_high=p_high, p_high_guarded=p_high_g,
                tol_lnf=w,
                tol_alpha_low_pct=100 * (1 - a_at(-w) / a),
                tol_alpha_high_pct=100 * (a_at(w) / a - 1),
                ref_under_lnf=up_g, ref_over_lnf=dn_g,
                ref_under_pct=100 * (1 - a_at(-up_g) / a),
                ref_over_pct=100 * (a_at(dn_g) / a - 1))


def windows(truth_path, allowance, procs=2):
    truth = json.load(open(truth_path))
    names = [s["station"] for s in truth["stations"]]
    with Pool(procs) as pool:
        return pool.map(one, [(n, truth_path, allowance) for n in names])


def main():
    truth_path = os.path.join(ROOT, "tests", "truth.json")
    truth = json.load(open(truth_path))
    allowance = truth["spec"]["dwell_budget_fraction"]
    rows = windows(truth_path, allowance)
    print(__doc__.split("\n\n")[0])
    print("\nallowance %.0f%%; dwell fixed at the optimum x (1 + %.3f)\n"
          % (100 * allowance, allowance - MARGIN))
    print("  station  alpha   P_opt   t_opt | band at that dwell | centred recipe tolerates "
          "        | reference (guarded)")
    print("                   Torr      s   | P_low  P_high Torr | +/- ln f   a low    a high"
          "  | a low    a high")
    for r in rows:
        print("  %-6s  %.4f  %6.2f  %6.3f | %6.2f  %6.2f     | %6.4f   -%5.2f%%  +%5.2f%%"
              "  | -%5.2f%%  +%5.2f%%"
              % (r["station"], r["alpha"], r["p_opt"], r["t_opt"], r["p_low"],
                 r["p_high"], r["tol_lnf"], r["tol_alpha_low_pct"],
                 r["tol_alpha_high_pct"], r["ref_under_pct"], r["ref_over_pct"]))
    lo = [r["tol_alpha_low_pct"] for r in rows]
    hi = [r["tol_alpha_high_pct"] for r in rows]
    print("\n  a centred recipe tolerates a coefficient estimate between %.1f%% and %.1f%% "
          "low," % (min(lo), max(lo)))
    print("  and between %.1f%% and %.1f%% high, depending on the station"
          % (min(hi), max(hi)))
    print("  ('a low' is how far BELOW the truth the reference's estimate may sit before")
    print("   the zone limit fails; 'a high' how far above before the temperature does)")
    with open(os.path.join(HERE, "station_windows.json"), "w") as fh:
        json.dump({"allowance": allowance, "margin": MARGIN, "guard_K": GUARD_K,
                   "stations": rows}, fh, indent=1)


if __name__ == "__main__":
    main()
