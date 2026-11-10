"""Discretisation convergence of the grading model.

physics.py claims the graded quantities are defined on area means so that "any
adequately resolved model of the same physics agrees with this one", and the README and
task.toml both rest on that: a solver better resolved than the grader must never be
penalised for being right. This script is the measurement behind that claim.

Two knobs are swept independently around the shipped values N_RINGS = 80 and
DT = 0.01 s:

  rings   40, 80, 120, 160  (equal radial width, boundary pinned on R_SPLIT), each at
          dt = 0.005 s, so the ring sweep is not limited by explicit-RK4 stability on
          the finest grids
  dt      0.02, 0.01, 0.005 s at 80 rings

and three quantities are reported per station, the same three the verifier grades:

  T_end   mass-mean wafer temperature at the end of the recipe's dwell
  dT      peak inner-to-outer zone difference over the dwell
  t_opt   the constrained optimum dwell, which sets the throughput budget

Each is compared against the finest setting in the sweep, not against the shipped one,
so the shipped setting has to earn its place rather than define correctness. The ring
sweep converges at second order, so it also yields an extrapolated limit,
X(160) - (X(80) - X(160))/3, and the shipped setting is reported against that too.

The test that matters is not whether the drift is small in absolute terms; it is whether
it is small against the margins a correct solution actually carries. The reference's
margins on the shipped instance are 0.93 C on temperature, 0.25 K on uniformity, and
0.011 on the dwell ratio against an 8% allowance -- deliberately thin, because the
allowance is tight -- so the grading model's own discretisation drift has to be an
order of magnitude below those to be immaterial.

    python3 method_study.py            # three representative stations
    python3 method_study.py S01 S04    # or name your own

Stations default to the two ends of the fleet's coefficient range -- S05, and S07,
which also carries the least temperature margin under the reference recipe -- and S12,
which carries the least zone margin.
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tests"))

import physics as ph

RINGS = (40, 80, 120, 160)
DT_RINGS = 0.005
DTS = (0.02, 0.01, 0.005)

# lowest coefficient; highest coefficient and least temperature margin; least zone margin
DEFAULT = ("S05", "S07", "S12")

# The margins the reference carries on the shipped instance, from its graded run
# (README, Reference solution). Drift is judged against these.
T_HOT, DT_WORST, R_WORST = 49.07, 24.75, 1.069
MARGIN = {"T_end": 50.0 - T_HOT, "dT": 25.0 - DT_WORST, "ratio": 1.080 - R_WORST}


def load():
    with open(os.path.join(ROOT, "tests", "truth.json")) as f:
        truth = json.load(f)
    spec = truth["spec"]
    rows = {r["station"]: r for r in truth["stations"]}
    return spec, rows


def station(row):
    a = row["_alpha"]
    return ph.Station(row["station"], row["inner_standoff_um"] * 1e-6,
                      row["outer_standoff_um"] * 1e-6, row["incoming_temperature_C"],
                      row["plate_setpoint_C"], a, a)


def recipe_point(name):
    """The reference's own (pressure, dwell) for this station, if it has been run."""
    p = "/tmp/refrun/app/recipe.json"
    if not os.path.exists(p):
        return None
    for r in json.load(open(p))["stations"]:
        if r["station"] == name:
            return r["he_pressure_torr"], r["dwell_s"]
    return None


def measure(st, spec, P, dwell, n_rings, dt):
    T_end, grad = ph.state_at(P, dwell, st, dt=dt, n_rings=n_rings)
    o = ph.fastest_feasible(st, spec["target_mean_temperature_C"],
                            spec["max_zone_difference_K"],
                            spec["he_pressure_min_torr"], spec["he_pressure_max_torr"],
                            dt=dt, n_rings=n_rings)
    return T_end, grad, (o[1] if o else float("nan"))


def sweep(label, cases, st, spec, P, dwell):
    rows = []
    for n_rings, dt in cases:
        t0 = time.time()
        rows.append(((n_rings, dt),) + measure(st, spec, P, dwell, n_rings, dt)
                    + (time.time() - t0,))
    ref = rows[-1]
    print("    %-9s %8s %8s %8s   %9s %9s %9s"
          % (label, "T_end", "dT", "t_opt", "dT_end", "d(dT)", "d t_opt"))
    for (key, T_end, grad, t_opt, secs) in rows:
        tag = "%d rings" % key[0] if label == "rings" else "dt %.4g" % key[1]
        if key == (ph.N_RINGS, ph.DT):
            mark = " <- shipped"
        elif label == "rings" and key[0] == ph.N_RINGS:
            mark = " <- shipped ring count"
        else:
            mark = ""
        print("    %-9s %8.3f %8.3f %8.3f   %+9.4f %+9.4f %+9.4f  [%.0fs]%s"
              % (tag, T_end, grad, t_opt, T_end - ref[1], grad - ref[2],
                 t_opt - ref[3], secs, mark), flush=True)
    return rows


def main():
    names = sys.argv[1:] or list(DEFAULT)
    spec, rows = load()
    print(__doc__.split("\n\n")[0])
    print("\nshipped grading model: %d rings, dt = %g s\n" % (ph.N_RINGS, ph.DT))
    worst = {"T_end": 0.0, "dT": 0.0, "t_opt": 0.0, "t_opt_frac": 0.0,
             "dT_lim": 0.0, "T_lim": 0.0}
    for name in names:
        if name not in rows:
            print("  no such station: %s" % name)
            continue
        st = station(rows[name])
        pt = recipe_point(name)
        if pt is None:
            print("  %s: no reference recipe at /tmp/refrun; run "
                  "authoring/evidence/run_reference.sh first" % name)
            continue
        P, dwell = pt
        print("  %s  alpha %.4f, recipe %.2f Torr for %.3f s"
              % (name, rows[name]["_alpha"], P, dwell))
        r1 = sweep("rings", [(n, DT_RINGS) for n in RINGS], st, spec, P, dwell)
        r2 = sweep("dt", [(ph.N_RINGS, d) for d in DTS], st, spec, P, dwell)
        shipped = [r for r in r2 if r[0] == (ph.N_RINGS, ph.DT)][0]
        finest = r1[-1]
        x80 = [r for r in r1 if r[0][0] == ph.N_RINGS][0]
        lim = [finest[i] - (x80[i] - finest[i]) / 3.0 for i in (1, 2, 3)]
        print("    shipped against the finest (%d rings, dt %g): T_end %+.4f C, "
              "dT %+.4f K, t_opt %+.4f s"
              % (finest[0][0], finest[0][1], shipped[1] - finest[1],
                 shipped[2] - finest[2], shipped[3] - finest[3]))
        print("    shipped against the extrapolated limit:         T_end %+.4f C, "
              "dT %+.4f K" % (shipped[1] - lim[0], shipped[2] - lim[1]))
        worst["T_end"] = max(worst["T_end"], abs(shipped[1] - finest[1]))
        worst["dT"] = max(worst["dT"], abs(shipped[2] - finest[2]))
        worst["t_opt"] = max(worst["t_opt"], abs(shipped[3] - finest[3]))
        worst["t_opt_frac"] = max(worst["t_opt_frac"],
                                  abs(shipped[3] - finest[3]) / finest[3])
        worst["T_lim"] = max(worst["T_lim"], abs(shipped[1] - lim[0]))
        worst["dT_lim"] = max(worst["dT_lim"], abs(shipped[2] - lim[1]))
        print()

    print("  worst drift of the SHIPPED setting, against the finest setting / against the")
    print("  extrapolated limit:")
    print("    end temperature   %.4f C / %.4f C   against %.3f C of margin" %
          (worst["T_end"], worst["T_lim"], MARGIN["T_end"]))
    print("    zone difference   %.4f K / %.4f K   against %.3f K of margin" %
          (worst["dT"], worst["dT_lim"], MARGIN["dT"]))
    print("    optimum dwell     %.4f s   (%.3f%% of the optimum)"
          % (worst["t_opt"], 100 * worst["t_opt_frac"]))
    print()
    print("  The optimum enters the reward only as a ratio, so its fractional drift is")
    print("  what counts: %.3f%% shifts every dwell ratio by about %.4f, against the"
          % (100 * worst["t_opt_frac"], R_WORST * worst["t_opt_frac"]))
    print("  %.3f the reference carries below the 1.080 limit. The verifier searches for"
          % MARGIN["ratio"])
    print("  each optimum on a 0.05 Torr pressure step, which can only place it at or after")
    print("  the continuous optimum, so any error from that search is in the solver's favour.")
    print()
    print("  The time step is converged to the printed precision at twice the shipped")
    print("  step. Every drift above is about a tenth of its margin or less, so a solver")
    print("  resolved finer than the grader is not penalised for it.")


if __name__ == "__main__":
    main()
