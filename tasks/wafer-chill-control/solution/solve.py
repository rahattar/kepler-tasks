"""Reference solution for wafer-chill-control.

1. Identify the plant from the characterisation logs in /data, with the reference's own
   model (refmodel.py): equal-area annuli, Kennard temperature jump with one lumped jump
   coefficient per station and film, lumped plate and chiller, first-order pressure lag.
     a. the pressure lag, from the manometer column against the command column;
     b. plate heat capacity, chiller conductance and the six jump coefficients together,
        by least squares over every logged channel of all eighteen runs.
2. Write /app/controller.py: one self-contained file holding the model, the identified
   parameters and the controller (controller_template.py) - online sag estimation from the
   two pyrometer spots and predictive riding of the zone limit.

It never reads the verifier's plant, truth or parameters; everything comes from /data.
"""
import csv
import json
import math
import os
import sys
import time

import numpy as np
from scipy.optimize import least_squares, minimize_scalar

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("CHILL_DATA", "/data")
OUT = os.environ.get("CHILL_CONTROLLER", "/app/controller.py")

sys.path.insert(0, HERE)
from refmodel import Grid, Model  # noqa: E402

N_RINGS = 30
DT = 0.01
FIT_UNTIL_S = 14.0
SIG = {"tc": 0.2, "spot": 0.3, "plate": 0.05}


def load():
    def j(name):
        with open(os.path.join(DATA, name)) as f:
            return json.load(f)
    stations = {s["station"]: s for s in j("stations.json")["stations"]}
    split = j("stations.json")["zone_split_radius_mm"] * 1e-3
    wafer = j("wafer.json")
    prod = j("production.json")
    idx = j("characterization/index.json")
    runs = []
    for r in idx["runs"]:
        with open(os.path.join(DATA, "characterization", r["file"])) as f:
            rows = list(csv.DictReader(f))
        col = lambda k: np.array([float(x[k]) for x in rows])  # noqa: E731
        runs.append(dict(meta=r, t=col("time_s"), cmd=col("pressure_cmd_torr"),
                         p=col("pressure_torr"), c=col("center_spot_C"),
                         e=col("edge_spot_C"), plate=col("plate_rtd_C"),
                         ti=col("tc_inner_mean_C"), to=col("tc_outer_mean_C"),
                         tm=col("tc_mass_mean_C")))
    return stations, split, wafer, prod, runs


def fit_tau(runs, p_idle, ctrl_dt):
    """Chamber pressure lag, from the manometer column alone."""
    def sse(log_tau):
        a = math.exp(-ctrl_dt / math.exp(log_tau))
        s = 0.0
        for r in runs:
            p = np.empty_like(r["p"])
            p[0] = p_idle
            for k in range(1, len(p)):
                p[k] = r["cmd"][k - 1] + (p[k - 1] - r["cmd"][k - 1]) * a
            s += float(np.sum(((p - r["p"]) / np.maximum(r["p"], 1.0)) ** 2))
        return s
    res = minimize_scalar(sse, bounds=(math.log(0.02), math.log(3.0)), method="bounded")
    return math.exp(res.x)


COMBOS = [(s, f) for s in ("A", "B") for f in ("bare", "oxide", "nitride")]


def simulate_runs(theta, runs, stations, grid, wafer, tau, upto_s):
    """All runs at once. theta = log J[6], log C, log G."""
    J = np.exp(theta[:6])
    C, G = math.exp(theta[6]), math.exp(theta[7])
    m = Model(grid, wafer, C, G, tau)
    rows = len(runs)
    d_in = np.array([stations[r["meta"]["station"]]["inner_standoff_um"] * 1e-6 for r in runs])
    d_out = np.array([stations[r["meta"]["station"]]["outer_standoff_um"] * 1e-6 for r in runs])
    sag = np.array([r["meta"]["test_wafer_sag_um"] * 1e-6 for r in runs])
    gap = m.gap(d_in, d_out, sag)
    Jv = np.array([[J[COMBOS.index((r["meta"]["station"], r["meta"]["film"]))]] for r in runs])
    Ts = np.array([[stations[r["meta"]["station"]]["plate_setpoint_C"] + 273.15] for r in runs])
    T0 = np.array([r["tm"][0] for r in runs])          # isothermal at landing
    Tw = np.repeat((T0 + 273.15)[:, None], grid.n, axis=1)
    Tp = Ts.copy()
    P = np.full((rows, 1), 3.0)
    n_samp = int(round(upto_s / 0.1)) + 1
    out = np.zeros((rows, n_samp, 6))
    for k in range(n_samp):
        ti, to = m.zones(Tw)
        c, e = m.spots(Tw)
        out[:, k] = np.stack([ti, to, m.t_mean(Tw), c, e, Tp[:, 0] - 273.15], axis=1)
        if k == n_samp - 1:
            break
        Pc = np.array([[r["cmd"][k]] for r in runs])
        for _ in range(10):
            Tw, Tp, P = m.step(Tw, Tp, P, Pc, gap, Jv, Ts, DT)
    return out


def residuals(theta, runs, stations, grid, wafer, tau, upto_s):
    sim = simulate_runs(theta, runs, stations, grid, wafer, tau, upto_s)
    n = sim.shape[1]
    res = []
    for i, r in enumerate(runs):
        for j, (key, sg) in enumerate((("ti", "tc"), ("to", "tc"), ("tm", "tc"),
                                       ("c", "spot"), ("e", "spot"), ("plate", "plate"))):
            res.append((sim[i, :, j] - r[key][:n]) / SIG[sg])
    return np.concatenate(res)


def identify(stations, split, wafer, prod, runs):
    t0 = time.time()
    tau = fit_tau(runs, prod["chamber_pressure_at_landing_torr"], prod["control_period_s"])
    print("  pressure lag: tau = %.3f s" % tau, flush=True)
    sens = prod["sensors"]
    grid = Grid(N_RINGS, wafer["diameter_mm"] * 0.5e-3, split,
                [v * 1e-3 for v in sens["center_pyrometer_annulus_mm"]],
                [v * 1e-3 for v in sens["edge_pyrometer_annulus_mm"]])
    theta0 = np.array([math.log(9.0)] * 6 + [math.log(2000.0), math.log(500.0)])
    fit = least_squares(residuals, theta0, args=(runs, stations, grid, wafer, tau, FIT_UNTIL_S),
                        x_scale=1.0, diff_step=1e-3, max_nfev=200)
    theta = fit.x
    rms = math.sqrt(float(np.mean(fit.fun ** 2)))
    J = np.exp(theta[:6])
    print("  plate %.0f J/K, chiller %.0f W/K; weighted residual rms %.3f  [%.0f s]"
          % (math.exp(theta[6]), math.exp(theta[7]), rms, time.time() - t0), flush=True)
    for (s, f), v in zip(COMBOS, J):
        print("    jump coefficient %s/%-8s %.3f" % (s, f, v))
    return dict(tau=tau, C_plate=math.exp(theta[6]), G_chiller=math.exp(theta[7]),
                J={s: {f: float(J[COMBOS.index((s, f))]) for f in ("bare", "oxide", "nitride")}
                   for s in ("A", "B")},
                grid=grid, rms=rms)


def write_controller(ident, wafer, prod, split, path):
    params = {
        "J": ident["J"], "C_plate": ident["C_plate"], "G_chiller": ident["G_chiller"],
        "tau": ident["tau"], "wafer": wafer,
        "r_wafer_m": wafer["diameter_mm"] * 0.5e-3, "r_split_m": split,
        "spot_center_m": [v * 1e-3 for v in prod["sensors"]["center_pyrometer_annulus_mm"]],
        "spot_edge_m": [v * 1e-3 for v in prod["sensors"]["edge_pyrometer_annulus_mm"]],
        "p_idle": prod["chamber_pressure_at_landing_torr"],
        "p_min": prod["pressure_command_min_torr"], "p_max": prod["pressure_command_max_torr"],
        "t_target": prod["release_mass_mean_max_C"], "zone_cap": prod["zone_difference_max_K"],
        "ctrl_dt": prod["control_period_s"],
    }
    with open(os.path.join(HERE, "refmodel.py")) as f:
        model_src = f.read()
    with open(os.path.join(HERE, "controller_template.py")) as f:
        ctrl_src = f.read()
    src = ('"""Chill-station controller generated by the reference solution."""\n'
           + model_src + "\n\nPARAMS = json.loads(%r)\n\n" % json.dumps(params)
           + ctrl_src)
    src = src.replace("import math\n", "import json\nimport math\n", 1)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        f.write(src)


def main():
    stations, split, wafer, prod, runs = load()
    print("identifying the plant from %d characterisation runs" % len(runs), flush=True)
    ident = identify(stations, split, wafer, prod, runs)
    write_controller(ident, wafer, prod, split, OUT)
    print("wrote %s" % OUT)


if __name__ == "__main__":
    main()
