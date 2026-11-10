"""Reference solution.

Deliberately independent of the grading physics in four ways, so that scoring 1 is
evidence the task grades the physics rather than one implementation:

  1. it does not import the grading module -- the wafer model here is written from the
     same textbook physics, not shared code;
  2. it discretises the wafer into equal-AREA annuli, where the grader uses annuli of
     equal radial width;
  3. it integrates with scipy's adaptive LSODA, where the grader uses fixed-step RK4;
  4. it identifies each station's accommodation coefficient by matching the times at
     which the mass mean crosses four temperature thresholds, rather than by least
     squares over the whole curve.

It buys its data from the same bench the agent uses, through the same client, under the
same budget. It never reads the sealed fleet parameters.

Strategy:
  * sixteen stations from twelve passivation lots and eight runs: lot intercepts
    cannot be fitted, so the lot effect has to be modelled through the one lot
    attribute on the traveller, the passivation bath temperature;
  * plan the campaign from the inspection data alone, so that every station the budget
    cannot reach is an INTERPOLATION in roughness and bath temperature jointly, not
    merely inside each covariate's range. A station on the convex hull of the fleet in
    those two covariates can never be interpolated from the others, so every hull
    vertex is measured; on this fleet there are seven, which leaves one run. That run
    goes to the station that minimises the worst prediction variance over the stations
    left unmeasured, taken over every knee position the covariate model might find;
  * identify each measured station's coefficient, in three stages so the plate is not
    assumed isothermal;
  * do NOT assume the bath-temperature effect is linear: fit a straight line and a
    hinge (linear up to a knee, flat beyond, knee chosen on a grid) and keep whichever
    has the smaller residual per degree of freedom. On this fleet the line's residual
    is several times the identification noise and the hinge's is at the noise floor,
    which is the whole difference between commissioning the fleet and not;
  * predict the eight unmeasured stations from that fit;
  * set every station's dwell from its own optimum, which under the jump-distance form
    does not depend on the coefficient at all, and place the pressure at the centre of
    the band the dwell allowance opens, so the recipe absorbs the largest coefficient
    error the allowance can pay for, in both directions at once.
"""
import csv
import json
import os
import subprocess
import sys

import re

import numpy as np
from scipy.integrate import solve_ivp
from scipy.spatial import ConvexHull

DATA = os.environ.get("CHILL_DATA", "/data")
OUT = os.environ.get("CHILL_RECIPE", "/app/recipe.json")
BENCH = os.environ.get("CHILL_BENCH", "/app/bench.py")

# --- physical constants, from the same references as the task statement -------------
R_U = 8.314462618
SIGMA = 5.670374419e-8
TORR = 133.32236842
M_HE = 4.002602e-3
GAMMA = 5.0 / 3.0
PR = 0.68
MU300 = 1.99e-5
K300 = 0.152

N_RINGS = 32                 # equal AREA, not equal width
FIT_THRESHOLDS = (200.0, 150.0, 100.0, 60.0)
ZONE_GUARD_K = 0.35          # against our own discretisation, not against the physics
# Margin held back from the allowance against our own estimate of each station's
# optimum dwell. This model differs from any grader's in discretisation, integrator and
# identification method, and a dry run against the sealed values put that disagreement
# at under 1% on the optimum; 1.5% keeps it inside the allowance with room.
T_MARGIN = 0.015

# Every run is made at one pressure, inside the band the recipes will use, so each trace
# carries information about the regime the recipe operates in.
RUN_P = 12.0
RUN_S = 22.0
KNEE_GRID = np.arange(42.0, 62.01, 0.5)
# For PLANNING, before any data exist, every knee from the coldest bath that can
# carry a slope to beyond the warmest one (which makes the hinge a straight line).
PLAN_KNEES = np.arange(42.0, 64.01, 0.5)
# Knee positions whose fit is within this factor of the best are reported as still
# live, so the log shows how tightly the data pin the knee.
KNEE_LIVE = 1.25


# --- wafer model ---------------------------------------------------------------------
def grid(n=N_RINGS, r_wafer=0.150, r_split=0.075):
    """Equal-area annuli, with a ring boundary forced exactly onto the zone step."""
    a_split = r_split ** 2 / r_wafer ** 2
    n_in = max(2, int(round(n * a_split)))
    e = np.concatenate([np.sqrt(np.linspace(0.0, r_split ** 2, n_in + 1)),
                        np.sqrt(np.linspace(r_split ** 2, r_wafer ** 2,
                                            n - n_in + 1))[1:]])
    r_in, r_out = e[:-1], e[1:]
    area = np.pi * (r_out ** 2 - r_in ** 2)
    r_mid = 0.5 * (r_in + r_out)
    return dict(edges=e, area=area, r_mid=r_mid, inner=r_mid < r_split,
                r_face=e[1:-1], dr=np.diff(r_mid))


class Wafer:
    def __init__(self, props, g=None):
        self.p = props
        self.g = g or grid()
        t = props["thickness_um"] * 1e-6
        self.t = t
        self.mass = props["density_kg_m3"] * t * self.g["area"]
        self.g_lat = (props["thermal_conductivity_W_mK"] * t
                      * 2 * np.pi * self.g["r_face"] / self.g["dr"])
        self.T_wall = props["chamber_wall_temperature_C"] + 273.15
        self.eps = props["top_face_emissivity"]

    @staticmethod
    def cp(T):
        return 703.0 + 0.28 * (T - 300.0)

    @staticmethod
    def k_he(T):
        return K300 * (T / 300.0) ** 0.71

    @staticmethod
    def mfp(P_torr, T):
        mu = MU300 * (T / 300.0) ** 0.69
        return (mu / (P_torr * TORR)) * np.sqrt(np.pi * R_U * T / (2.0 * M_HE))

    @classmethod
    def h_gap(cls, P, d, T, alpha):
        jump = ((2.0 - alpha) / alpha) * (2.0 * GAMMA / (GAMMA + 1.0)) \
            * (cls.mfp(P, T) / PR)
        return cls.k_he(T) / (d + 2.0 * jump)

    def rhs(self, t, y, P, d, Tsp, alpha, C_pl, G_ch):
        Tw, Tp = y[:-1], y[-1]
        h = self.h_gap(P, d, 0.5 * (Tw + Tp), alpha)
        q_gap = h * self.g["area"] * (Tw - Tp)
        q = q_gap + self.eps * SIGMA * self.g["area"] * (Tw ** 4 - self.T_wall ** 4)
        flux = self.g_lat * (Tw[:-1] - Tw[1:])
        q[:-1] += flux
        q[1:] -= flux
        dTw = -q / (self.mass * self.cp(Tw))
        dTp = (q_gap.sum() - G_ch * (Tp - Tsp)) / C_pl
        return np.concatenate([dTw, [dTp]])

    def run(self, P, st, alpha, C_pl, G_ch, t_end, n_out=400):
        d = np.where(self.g["inner"], st["d_in"], st["d_out"])
        Tsp = st["Tsp"] + 273.15
        y0 = np.concatenate([np.full(len(self.g["area"]), st["T0"] + 273.15), [Tsp]])
        ts = np.linspace(0.0, t_end, n_out)
        sol = solve_ivp(self.rhs, (0.0, t_end), y0, method="LSODA", t_eval=ts,
                        args=(P, d, Tsp, alpha, C_pl, G_ch), rtol=1e-7, atol=1e-7)
        Tw = sol.y[:-1].T - 273.15
        Tp = sol.y[-1] - 273.15
        w_m = self.mass / self.mass.sum()
        a_in = self.g["area"] * self.g["inner"]
        a_out = self.g["area"] * (~self.g["inner"])
        return (sol.t, Tw @ w_m, Tw @ (a_in / a_in.sum()),
                Tw @ (a_out / a_out.sum()), Tp)


def crossings(t, T, levels):
    out = []
    for L in levels:
        i = np.nonzero(T <= L)[0]
        if i.size == 0 or i[0] == 0:
            out.append(np.nan)
            continue
        j = i[0]
        f = (T[j - 1] - L) / (T[j - 1] - T[j]) if T[j] != T[j - 1] else 0.0
        out.append(t[j - 1] + f * (t[j] - t[j - 1]))
    return np.array(out)


def golden(f, lo, hi, iters=26):
    a, b = lo, hi
    c, d = b - 0.618 * (b - a), a + 0.618 * (b - a)
    fc, fd = f(c), f(d)
    for _ in range(iters):
        if fc < fd:
            b, d, fd = d, c, fc
            c = b - 0.618 * (b - a)
            fc = f(c)
        else:
            a, c, fc = c, d, fd
            d = a + 0.618 * (b - a)
            fd = f(d)
    return 0.5 * (a + b)


# --- plan the campaign ---------------------------------------------------------------
def remaining_budget():
    r = subprocess.run([sys.executable, BENCH, "status"], capture_output=True, text=True)
    m = re.search(r"(\d+) remaining", r.stdout)
    if r.returncode != 0 or not m:
        raise RuntimeError(f"cannot read the bench budget: {r.stdout} {r.stderr}")
    return int(m.group(1))


def plan_campaign(ST, budget):
    """Which stations to spend the budget on, from the inspection data alone.

    1. Every vertex of the convex hull of the fleet in (roughness, bath temperature):
       no model can interpolate to a hull vertex, so leaving one unmeasured makes it an
       extrapolation however well the rest is sampled.
    2. Any runs left go, one at a time, to the station whose addition minimises the
       largest prediction variance over the stations still unmeasured, taken as the
       worst case over every knee position the hinge model could settle on.
    """
    names = sorted(ST)
    X = np.array([[ST[n]["ra"], ST[n]["bath"]] for n in names])
    hull = [names[i] for i in ConvexHull(X).vertices]
    if len(hull) > budget:
        raise RuntimeError(f"{len(hull)} hull stations but only {budget} runs")

    def design(ns, knee):
        return np.array([[1.0, ST[n]["ra"], min(ST[n]["bath"], knee)] for n in ns])

    def worst_variance(chosen):
        rest = [n for n in names if n not in chosen]
        if not rest:
            return 0.0
        w = 0.0
        for k in PLAN_KNEES:
            A = design(chosen, k)
            M = A.T @ A
            if np.linalg.matrix_rank(M) < 3:
                return np.inf
            V = design(rest, k)
            w = max(w, float(np.max(np.einsum("ij,jk,ik->i", V, np.linalg.inv(M), V))))
        return w

    chosen = list(hull)
    while len(chosen) < budget:
        cands = [n for n in names if n not in chosen]
        chosen.append(min(cands, key=lambda n: (worst_variance(chosen + [n]), n)))
    # run in order of bath temperature, coldest first
    return sorted(chosen, key=lambda n: (ST[n]["bath"], n)), hull


# --- buy the data --------------------------------------------------------------------
def book(station, pressure, seconds):
    r = subprocess.run([sys.executable, BENCH, "run", "--station", station,
                        "--pressure", str(pressure), "--seconds", str(seconds)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"bench refused {station}: {r.stderr.strip()}")
    for line in r.stdout.splitlines():
        if "wrote" in line:
            return os.path.join(os.getcwd(), line.split("wrote")[1].strip().split()[0])
    raise RuntimeError(f"cannot find the trace the bench wrote: {r.stdout}")


def read_trace(path):
    with open(path) as f:
        rows = list(csv.DictReader(f))
    col = lambda k: np.array([float(r[k]) for r in rows])
    return dict(t=col("time_s"), Tm=col("T_mean_C"), Ti=col("T_inner_C"),
                To=col("T_outer_C"), Tp=col("T_plate_rtd_C"))


def main():
    with open(os.path.join(DATA, "stations.json")) as f:
        fleet = json.load(f)["stations"]
    with open(os.path.join(DATA, "wafer.json")) as f:
        props = json.load(f)
    with open(os.path.join(DATA, "spec.json")) as f:
        spec = json.load(f)

    ST = {s["station"]: dict(d_in=s["inner_standoff_um"] * 1e-6,
                             d_out=s["outer_standoff_um"] * 1e-6,
                             T0=s["incoming_temperature_C"],
                             Tsp=s["plate_setpoint_C"],
                             ra=s["plate_roughness_Ra_um"],
                             lot=s["passivation_lot"],
                             bath=s["passivation_bath_C"]) for s in fleet}
    w = Wafer(props)
    T_tgt = spec["target_mean_temperature_C"]
    cap = spec["max_zone_difference_K"]
    delta = spec["dwell_budget_fraction"]
    P_lo, P_hi = spec["he_pressure_min_torr"], spec["he_pressure_max_torr"]

    budget = remaining_budget()
    plan, hull = plan_campaign(ST, budget)
    print(f"  {budget} runs; fleet hull in (roughness, bath): {', '.join(sorted(hull))}; "
          f"campaign: {', '.join(plan)}", flush=True)
    CAMPAIGN = [(n, RUN_P) for n in plan]

    obs = {}
    for name, P in CAMPAIGN:
        obs[name] = (P, read_trace(book(name, P, RUN_S)))
        print(f"  booked {name} at {P} Torr", flush=True)

    def fit_alpha(name, C_pl, G_ch):
        P, o = obs[name]
        lv = [L for L in FIT_THRESHOLDS if L < o["Tm"][0] - 5 and L > T_tgt - 5]
        tgt = crossings(o["t"], o["Tm"], lv)
        ok = np.isfinite(tgt)

        def err(a):
            t, Tm, *_ = w.run(P, ST[name], float(a), C_pl, G_ch, RUN_S)
            mdl = crossings(t, Tm, lv)
            d = mdl[ok] - tgt[ok]
            return float(np.sum(np.where(np.isfinite(d), d, 10.0) ** 2))

        return golden(err, 0.12, 0.85)

    # stage 1: plate pinned at setpoint, rough coefficients
    C_pl, G_ch = 1e9, 1e9
    alphas = {n: fit_alpha(n, C_pl, G_ch) for n, _ in CAMPAIGN}
    print("  stage 1 done", flush=True)

    # stage 2: one plate capacity and chiller conductance for the whole fleet,
    # from the RTD traces, given the stage-1 coefficients
    def plate_err(logs):
        C, G = np.exp(logs)
        e = 0.0
        for n, _ in CAMPAIGN:
            P, o = obs[n]
            t, _, _, _, Tp = w.run(P, ST[n], alphas[n], C, G, RUN_S)
            e += float(np.sum((np.interp(o["t"], t, Tp) - o["Tp"]) ** 2))
        return e

    lg = np.log(2000.0)
    for _ in range(3):
        C = np.exp(golden(lambda x: plate_err([x, np.log(550.0) if _ == 0 else lg]),
                          np.log(500.0), np.log(8000.0), 18))
        G = np.exp(golden(lambda x: plate_err([np.log(C), x]),
                          np.log(150.0), np.log(2000.0), 18))
        lg = np.log(G)
    C_pl, G_ch = float(C), float(G)
    print(f"  stage 2: plate capacity {C_pl:.0f} J/K, chiller {G_ch:.0f} W/K", flush=True)

    # stage 3: refit the coefficients with the plate model in place
    alphas = {n: fit_alpha(n, C_pl, G_ch) for n, _ in CAMPAIGN}
    print("  stage 3 done: " + ", ".join(f"{n} {a:.4f}" for n, a in alphas.items()),
          flush=True)

    # covariate model. Twelve lots and eight runs rule out lot intercepts; the lot
    # attribute on the traveller, bath temperature, has to carry the lot effect. The
    # question is the SHAPE of that dependence, and it is not assumed: a straight line
    # and a hinge are both fitted and the data choose.
    names = [n for n, _ in CAMPAIGN]
    y = np.array([alphas[n] for n in names])
    ra_m = np.array([ST[n]["ra"] for n in names])
    tb_m = np.array([ST[n]["bath"] for n in names])

    def lstsq(X):
        c, *_ = np.linalg.lstsq(X, y, rcond=None)
        r = y - X @ c
        dof = max(1, len(y) - X.shape[1])
        return c, float(np.sum(r ** 2)), float(np.sqrt(np.sum(r ** 2) / dof))

    c_lin, sse_lin, u_lin = lstsq(np.column_stack([np.ones_like(y), ra_m, tb_m]))
    fits = []
    for knee in KNEE_GRID:
        c, sse, u = lstsq(np.column_stack([np.ones_like(y), ra_m,
                                           np.minimum(tb_m, knee)]))
        fits.append((sse, float(knee), c, u))
    fits.sort(key=lambda f: f[0])
    sse_h, knee_h, c_h, u_h = fits[0]
    # the hinge spends one more parameter than the line (the knee); charge for it
    u_h_eff = float(np.sqrt(sse_h / max(1, len(y) - 4)))
    use_hinge = u_h_eff < u_lin
    live = [f for f in fits if f[0] <= KNEE_LIVE * sse_h]
    print(f"  line: residual {u_lin:.4f}/dof   hinge: knee {knee_h:.1f} C, residual "
          f"{u_h_eff:.4f}/dof   -> {'hinge' if use_hinge else 'line'}; "
          f"{len(live)} knee positions still live "
          f"({min(f[1] for f in live):.1f}-{max(f[1] for f in live):.1f} C)",
          flush=True)
    u = u_h_eff if use_hinge else u_lin

    def predict(n):
        ra, tb = ST[n]["ra"], ST[n]["bath"]
        if not use_hinge:
            return float(c_lin[0] + c_lin[1] * ra + c_lin[2] * tb), 0.0
        preds = [c[0] + c[1] * ra + c[2] * min(tb, knee) for _, knee, c, _ in live]
        best = c_h[0] + c_h[1] * ra + c_h[2] * min(tb, knee_h)
        return float(best), float(0.5 * (max(preds) - min(preds)))

    def metrics(P, name, alpha, t_end):
        t, Tm, Ti, To, _ = w.run(P, ST[name], alpha, C_pl, G_ch, t_end)
        return t, Tm, np.abs(Ti - To)

    # Recipe policy. In the jump-distance form every station's gap conductance depends
    # on pressure and accommodation only through the ratio P / ((2-a)/a), so the whole
    # cooldown, and with it the optimum dwell, is the same for every coefficient: the
    # coefficient only decides WHICH pressure realises it. So:
    #   dwell    = this station's optimum dwell x (1 + allowance - a margin for our own
    #              estimate of that optimum), independent of the coefficient;
    #   pressure = the geometric centre of the band of pressures that, at that dwell,
    #              both reach the target and clear the zone limit at the estimated
    #              coefficient.
    # Centring in log-pressure spends the whole allowance on tolerance to coefficient
    # error, in both directions at once, instead of hedging each limit separately.
    def zone_ok(P, n, a, guard):
        _, _, dT = metrics(P, n, a, 30.0)
        return dT.max() <= cap - guard

    def t_target(P, n, a):
        t, Tm, _ = metrics(P, n, a, 40.0)
        return float(crossings(t, Tm, [T_tgt])[0])

    def p_zone_limit(n, a, guard):
        lo, hi = P_lo, P_hi
        for _ in range(22):
            mid = np.sqrt(lo * hi)
            lo, hi = (mid, hi) if zone_ok(mid, n, a, guard) else (lo, mid)
        return lo

    def p_reaching(n, a, dwell, p_top):
        lo, hi = P_lo, p_top          # time to target falls as pressure rises
        if not np.isfinite(t_target(hi, n, a)) or t_target(hi, n, a) > dwell:
            return hi
        for _ in range(22):
            mid = np.sqrt(lo * hi)
            tm = t_target(mid, n, a)
            lo, hi = (mid, hi) if (not np.isfinite(tm) or tm > dwell) else (lo, mid)
        return hi

    recipe = []
    for s in fleet:
        n = s["station"]
        if n in alphas:
            a_hat, tag = alphas[n], "measured"
        else:
            a_hat, _ = predict(n)
            tag = "predicted"
        # the optimum is defined at the limit itself, exactly as the spec states it;
        # the guard belongs on the operating window, not on the definition
        p_opt = p_zone_limit(n, a_hat, 0.0)
        t_star = t_target(p_opt, n, a_hat)
        dw = t_star * (1.0 + delta - T_MARGIN)
        p_star = p_zone_limit(n, a_hat, ZONE_GUARD_K)
        p_low = p_reaching(n, a_hat, dw, p_star)
        P = float(np.sqrt(p_low * p_star))
        recipe.append({"station": n, "he_pressure_torr": round(P, 3),
                       "dwell_s": round(dw, 3)})
        print(f"  {n}: alpha {a_hat:.4f} ({tag}) -> optimum {p_opt:.2f} Torr / "
              f"{t_star:.2f} s; window {p_low:.2f}-{p_star:.2f} Torr "
              f"(+/-{100*(np.sqrt(p_star/p_low)-1):.1f}% in coefficient); "
              f"recipe {P:.2f} Torr, {dw:.2f} s", flush=True)

    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    with open(OUT, "w") as f:
        json.dump({"stations": recipe}, f, indent=2)
    print(f"wrote {OUT} (budget fraction {delta})")


if __name__ == "__main__":
    main()
