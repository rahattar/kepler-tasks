"""Sealed physics for chill-bench-commissioning. Radially resolved wafer, finite-capacity
plate.

Single source of truth. The bench service and the verifier both import this module;
nothing the agent can reach may. It contains no randomness -- every function here is a
deterministic function of its arguments. Measurement noise lives in the bench service.

MODEL
-----
A 300 mm silicon wafer rests on proximity pins over a temperature-controlled plate.
Backside helium fills the gap. The plate is machined as two concentric zones with a
step in standoff at r = R_SPLIT, so the gap conductance is piecewise constant in
radius while the wafer temperature is not: lateral conduction in the silicon smooths
the step into a continuous radial profile.

The wafer is discretised into N_RINGS annular control volumes of equal radial width,
with a ring boundary placed exactly at R_SPLIT so the standoff step is resolved
without straddling a cell. Each ring exchanges heat by

  1. rarefied conduction through the helium gap to the plate,
         h = k_He(T) / (d + g_wafer + g_plate)
     with g the Kennard temperature-jump distance at each surface,
         g = ((2 - a)/a) * (2*gamma/(gamma + 1)) * (lambda / Pr),
     `a` the thermal accommodation coefficient of the two surfaces and lambda the
     viscosity-based mean free path. At low pressure 2g >> d and h is nearly blind to
     the standoff; at high pressure 2g << d and h -> k/d.

  2. radiation from its exposed top face to the chamber walls,

  3. conduction to its radial neighbours through the silicon cross-section.

The plate is NOT isothermal. It is a lumped mass C_PLATE served by a chiller of
finite conductance G_CHILLER to a fixed setpoint:

    C_PLATE dTp/dt = Q_from_wafer - G_CHILLER (Tp - T_setpoint)

so the plate rises during the transient, and rises further at higher helium pressure
because the heat load is larger. The rise is observable in a plate RTD.

The graded quantities are defined on area means, not on cell values, so any
adequately resolved model of the same physics agrees with this one:

    T_mean  = mass-mean over the whole wafer
    T_inner = area-mean over r <  R_SPLIT
    T_outer = area-mean over r >= R_SPLIT

Ring count and time step are both swept in authoring/evidence/method_study.py,
with the result in method_study.txt. The shipped 80 rings and dt = 0.01 s are within
0.001 C on end temperature, 0.019 K on zone difference and 0.001% on the constrained
optimum of the converged solution (160 rings at dt = 0.005 s, and the limit extrapolated
from the ring sweep) -- each under a tenth of the margin a correct recipe carries.

REFERENCES
----------
Kennard, Kinetic Theory of Gases, McGraw-Hill 1938, ch. 8 (temperature jump).
Springer, Adv. Heat Transfer 7 (1971) 163 (rarefied conduction between surfaces).
Song, Yovanovich & Goodman, J. Heat Transfer 115 (1993) 533 (gas gap conductance).
Helium transport properties: Petersen, Riso Report No. 224 (1970).
"""
import numpy as np

# ---------------------------------------------------------------- constants
R_U = 8.314462618
SIGMA = 5.670374419e-8
TORR = 133.32236842

M_HE = 4.002602e-3
GAMMA_HE = 5.0 / 3.0
PR_HE = 0.68
MU_HE_300 = 1.99e-5
K_HE_300 = 0.152

D_WAFER = 0.300
T_WAFER = 775e-6
RHO_SI = 2329.0
K_SI = 100.0
EMISSIVITY = 0.70
T_WALL = 298.15

R_SPLIT = 0.075
R_WAFER = D_WAFER / 2.0
A_WAFER = np.pi * R_WAFER ** 2

# chiller module, identical on every station in this fleet
C_PLATE = 2000.0           # J/K, lumped plate + manifold
G_CHILLER = 550.0          # W/K, plate to coolant

N_RINGS = 80
DT = 0.01
T_MAX = 40.0


def _grid(n_rings=N_RINGS):
    if n_rings % 2:
        raise ValueError("n_rings must be even so a boundary lands on R_SPLIT")
    edges = np.linspace(0.0, R_WAFER, n_rings + 1)
    r_in, r_out = edges[:-1], edges[1:]
    area = np.pi * (r_out ** 2 - r_in ** 2)
    mass = RHO_SI * T_WAFER * area
    r_mid = 0.5 * (r_in + r_out)
    dr = edges[1] - edges[0]
    g_lat = K_SI * T_WAFER * (2 * np.pi * edges[1:-1]) / dr
    inner = r_mid < R_SPLIT
    return dict(edges=edges, r_mid=r_mid, area=area, mass=mass, dr=dr,
                g_lat=g_lat, inner=inner, n=n_rings)


_G = _grid()


def mu_he(T):
    return MU_HE_300 * (T / 300.0) ** 0.69


def k_he(T):
    return K_HE_300 * (T / 300.0) ** 0.71


def cp_si(T):
    return 703.0 + 0.28 * (T - 300.0)


def mean_free_path(P_torr, T):
    return (mu_he(T) / (P_torr * TORR)) * np.sqrt(np.pi * R_U * T / (2.0 * M_HE))


def jump_distance(P_torr, T, alpha):
    return ((2.0 - alpha) / alpha) * (2.0 * GAMMA_HE / (GAMMA_HE + 1.0)) \
        * (mean_free_path(P_torr, T) / PR_HE)


def gap_conductance(P_torr, d, T_gas, alpha_wafer, alpha_plate):
    return k_he(T_gas) / (d + jump_distance(P_torr, T_gas, alpha_wafer)
                          + jump_distance(P_torr, T_gas, alpha_plate))


class Station:
    """One chill station. Standoffs in metres, temperatures in Celsius.

    `T_setpoint_C` is the chiller setpoint, not the plate temperature: the plate
    departs from it while heat is arriving.
    """

    def __init__(self, name, d_ctr, d_edge, T0_C, T_setpoint_C,
                 alpha_wafer=0.42, alpha_plate=0.42):
        self.name = name
        self.d_ctr = float(d_ctr)
        self.d_edge = float(d_edge)
        self.T0_C = float(T0_C)
        self.T_setpoint_C = float(T_setpoint_C)
        self.alpha_wafer = float(alpha_wafer)
        self.alpha_plate = float(alpha_plate)

    def standoff(self, grid):
        return np.where(grid["inner"], self.d_ctr, self.d_edge)

    def as_dict(self):
        return {"name": self.name, "d_ctr_um": self.d_ctr * 1e6,
                "d_edge_um": self.d_edge * 1e6, "T0_C": self.T0_C,
                "T_setpoint_C": self.T_setpoint_C}


def _rhs(Tw, Tp, P, st, grid, d_ring):
    """Rates for the wafer rings and the plate. Tw is (..., n_rings); Tp is (..., 1)."""
    h = gap_conductance(P, d_ring, 0.5 * (Tw + Tp), st.alpha_wafer, st.alpha_plate)
    q_gap = h * grid["area"] * (Tw - Tp)
    q = q_gap + EMISSIVITY * SIGMA * grid["area"] * (Tw ** 4 - T_WALL ** 4)
    flux = grid["g_lat"] * (Tw[..., :-1] - Tw[..., 1:])
    q[..., :-1] += flux
    q[..., 1:] -= flux
    dTw = -q / (grid["mass"] * cp_si(Tw))
    Q_in = q_gap.sum(axis=-1, keepdims=True)
    dTp = (Q_in - G_CHILLER * (Tp - (st.T_setpoint_C + 273.15))) / C_PLATE
    return dTw, dTp


def integrate(P_torr, st, dt=DT, t_max=T_MAX, stop_below_C=None, n_rings=N_RINGS):
    """RK4 cooldown of the coupled wafer and plate.

    Returns (t, T_mean_C, T_inner_C, T_outer_C, T_plate_C). Temperature arrays are
    (n,) for a scalar pressure and (n, nP) for an array of pressures.
    """
    grid = _G if n_rings == N_RINGS else _grid(n_rings)
    P = np.atleast_1d(np.asarray(P_torr, dtype=float))[:, None]
    d_ring = st.standoff(grid)[None, :]
    Tw = np.full((P.shape[0], grid["n"]), st.T0_C + 273.15)
    Tp = np.full((P.shape[0], 1), st.T_setpoint_C + 273.15)

    m = grid["mass"]
    a_in = grid["area"] * grid["inner"]
    a_out = grid["area"] * (~grid["inner"])
    w_mass, w_in, w_out = m / m.sum(), a_in / a_in.sum(), a_out / a_out.sum()

    n = int(round(t_max / dt)) + 1
    t = np.arange(n) * dt
    mean = np.empty((n, P.shape[0]))
    inner = np.empty((n, P.shape[0]))
    outer = np.empty((n, P.shape[0]))
    plate = np.empty((n, P.shape[0]))
    stop_K = None if stop_below_C is None else stop_below_C + 273.15
    used = n
    for i in range(n):
        mean[i] = Tw @ w_mass
        inner[i] = Tw @ w_in
        outer[i] = Tw @ w_out
        plate[i] = Tp[:, 0]
        if stop_K is not None and (i & 15) == 0 and i > 0 and np.all(mean[i] < stop_K):
            used = i + 1
            break
        k1w, k1p = _rhs(Tw, Tp, P, st, grid, d_ring)
        k2w, k2p = _rhs(Tw + 0.5 * dt * k1w, Tp + 0.5 * dt * k1p, P, st, grid, d_ring)
        k3w, k3p = _rhs(Tw + 0.5 * dt * k2w, Tp + 0.5 * dt * k2p, P, st, grid, d_ring)
        k4w, k4p = _rhs(Tw + dt * k3w, Tp + dt * k3p, P, st, grid, d_ring)
        Tw = Tw + (dt / 6.0) * (k1w + 2 * k2w + 2 * k3w + k4w)
        Tp = Tp + (dt / 6.0) * (k1p + 2 * k2p + 2 * k3p + k4p)
    out = (t[:used], mean[:used] - 273.15, inner[:used] - 273.15,
           outer[:used] - 273.15, plate[:used] - 273.15)
    if np.isscalar(P_torr) or np.asarray(P_torr).ndim == 0:
        return (out[0],) + tuple(a[:, 0] for a in out[1:])
    return out


def cooldown_metrics(P_torr, st, T_target_C, dt=DT, t_max=T_MAX, n_rings=N_RINGS):
    """(time for the mass mean to reach the target, max |T_inner - T_outer| up to then)."""
    t, Tm, Ti, To, _ = integrate(P_torr, st, dt, t_max,
                                 stop_below_C=T_target_C - 1.0, n_rings=n_rings)
    Tm2 = Tm if Tm.ndim > 1 else Tm[:, None]
    grad = np.abs((Ti if Ti.ndim > 1 else Ti[:, None])
                  - (To if To.ndim > 1 else To[:, None]))
    nP = Tm2.shape[1]
    t_hit = np.full(nP, np.inf)
    dT_max = np.full(nP, np.inf)
    for j in range(nP):
        below = np.nonzero(Tm2[:, j] <= T_target_C)[0]
        if below.size == 0:
            continue
        i = below[0]
        if i == 0:
            t_hit[j] = 0.0
        else:
            y0, y1 = Tm2[i - 1, j], Tm2[i, j]
            frac = (y0 - T_target_C) / (y0 - y1) if y1 != y0 else 0.0
            t_hit[j] = t[i - 1] + frac * (t[i] - t[i - 1])
        dT_max[j] = grad[:i + 1, j].max()
    if np.isscalar(P_torr) or np.asarray(P_torr).ndim == 0:
        return float(t_hit[0]), float(dT_max[0])
    return t_hit, dT_max


def state_at(P_torr, dwell_s, st, dt=DT, t_max=T_MAX, n_rings=N_RINGS):
    """(mass-mean wafer T at end of dwell, max |T_inner - T_outer| over the dwell)."""
    t, Tm, Ti, To, _ = integrate(P_torr, st, dt, t_max, n_rings=n_rings)
    grad = np.abs(Ti - To)
    if dwell_s <= 0:
        return float(Tm[0]), 0.0
    if dwell_s >= t[-1]:
        return float(Tm[-1]), float(grad.max())
    i = min(max(int(np.searchsorted(t, dwell_s)), 1), len(t) - 1)
    frac = (dwell_s - t[i - 1]) / (t[i] - t[i - 1])
    return float(Tm[i - 1] + frac * (Tm[i] - Tm[i - 1])), float(grad[:i + 1].max())


def fastest_feasible(st, T_target_C, grad_cap_K, P_min, P_max, dt=DT,
                     coarse=0.5, fine=0.05, n_rings=N_RINGS):
    """Lowest dwell whose zone difference stays at or under grad_cap_K, or None."""
    best = None
    for step, lo, hi in ((coarse, P_min, P_max), (fine, None, None)):
        if lo is None:
            lo, hi = max(P_min, best[0] - coarse), min(P_max, best[0] + coarse)
        P = np.arange(lo, hi + 1e-9, step)
        t_hit, dT = cooldown_metrics(P, st, T_target_C, dt, n_rings=n_rings)
        ok = np.isfinite(t_hit) & (dT <= grad_cap_K)
        if not ok.any():
            return None
        j = int(np.argmin(np.where(ok, t_hit, np.inf)))
        best = (float(P[j]), float(t_hit[j]), float(dT[j]))
    return best
