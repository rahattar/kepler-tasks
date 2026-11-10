"""Sealed plant for wafer-chill-control: one wafer on one vacuum chill station.

Single source of truth for the physics. The data generator and the verifier import this
module; nothing the agent can reach does. It holds no randomness of its own: sensor noise
is drawn from a generator the caller passes in, seeded per wafer.

MODEL
-----
A 300 mm silicon wafer lands on proximity pins over a chilled plate machined as two
concentric zones, with a step in standoff at r = R_SPLIT. Backside helium fills the gap.
The wafer is not flat: a wafer with centre sag s sits closer to the plate in the middle,

    gap(r) = standoff_zone(r) - s * (1 - (r / R_WAFER)^2),

so a sagging wafer (s > 0) cools its centre faster and a dished one (s < 0) slower.

The wafer is discretised into N_RINGS annuli of equal radial width, with a ring boundary
exactly on R_SPLIT. Each ring exchanges heat by

  1. rarefied conduction through the helium gap,
         h = k_He(T) / (gap + g_wafer + g_plate),
         g = ((2 - a)/a) * (2*gamma/(gamma + 1)) * (lambda / Pr),
     the Kennard temperature-jump distance at each surface, with its own accommodation
     coefficient: a_wafer set by the wafer's backside film, a_plate by the station;
  2. radiation from its top face to the chamber walls;
  3. conduction to its radial neighbours through the silicon.

The plate is a lumped mass C_PLATE served by a chiller of conductance G_CHILLER to its
setpoint, so it warms while heat arrives. Chamber pressure follows the commanded pressure
through a first-order lag of time constant TAU_P and starts at P_IDLE when a wafer lands.

GRADED QUANTITIES are defined on area means, so any adequately resolved model computes the
same numbers:

    T_mean   mass-mean wafer temperature (uniform thickness, so the area mean)
    zone dT  |area mean over r < R_SPLIT  -  area mean over r >= R_SPLIT|

The production SENSORS are two pyrometer spots, each the area mean over an annulus
(SPOT_CENTER, SPOT_EDGE, in metres), the plate RTD and the chamber manometer.

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

# chiller module, the same part on both stations
C_PLATE = 2400.0           # J/K, lumped plate and manifold
G_CHILLER = 620.0          # W/K, plate to coolant

# helium supply
TAU_P = 0.25               # s, chamber pressure response to a command
P_IDLE = 3.0               # Torr, chamber pressure when a wafer lands
P_MIN, P_MAX = 3.0, 60.0   # Torr, command range

# production limits
T_TARGET = 50.0            # C, mass mean at release
ZONE_CAP = 25.0            # K, inner/outer zone difference, every instant until release
T_CYCLE_MAX = 30.0         # s, a wafer still on the plate at this time has failed
CTRL_DT = 0.1              # s, control period

# production sensors
SPOT_CENTER = (0.000, 0.010)
SPOT_EDGE = (0.135, 0.145)
PYRO_RMS = 0.30            # K per sample
PLATE_RMS = 0.05           # K per sample
MANO_REL = 0.005           # relative, per sample

N_RINGS = 80
DT = 0.01


# ---------------------------------------------------------------- discretisation
def _overlap_weights(edges, a, b):
    """Area weights of each annulus inside [a, b], normalised to 1."""
    lo = np.clip(edges[:-1], a, b)
    hi = np.clip(edges[1:], a, b)
    w = np.pi * (hi ** 2 - lo ** 2)
    return w / w.sum()


def grid(n_rings=N_RINGS):
    if n_rings % 2:
        raise ValueError("n_rings must be even so a boundary lands on R_SPLIT")
    edges = np.linspace(0.0, R_WAFER, n_rings + 1)
    area = np.pi * (edges[1:] ** 2 - edges[:-1] ** 2)
    r_mid = 0.5 * (edges[:-1] + edges[1:])
    dr = edges[1] - edges[0]
    inner = r_mid < R_SPLIT
    a_in = area * inner
    a_out = area * (~inner)
    return dict(
        n=n_rings, edges=edges, area=area, r_mid=r_mid, inner=inner,
        mass=RHO_SI * T_WAFER * area,
        g_lat=K_SI * T_WAFER * (2.0 * np.pi * edges[1:-1]) / dr,
        w_mean=area / area.sum(),
        w_in=a_in / a_in.sum(), w_out=a_out / a_out.sum(),
        w_spot_c=_overlap_weights(edges, *SPOT_CENTER),
        w_spot_e=_overlap_weights(edges, *SPOT_EDGE),
    )


_G = grid()


# ---------------------------------------------------------------- gas properties
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


# ---------------------------------------------------------------- one wafer
class Wafer:
    """One wafer on one station.

    Standoffs and sag in metres, temperatures in Celsius. alpha_wafer comes from the
    wafer's backside film, alpha_plate from the station.
    """

    def __init__(self, d_inner, d_outer, T_setpoint, alpha_plate, alpha_wafer, sag, T0,
                 n_rings=N_RINGS):
        self.g = _G if n_rings == N_RINGS else grid(n_rings)
        self.T_set = float(T_setpoint)
        self.a_p, self.a_w = float(alpha_plate), float(alpha_wafer)
        self.sag = float(sag)
        self.T0 = float(T0)
        d = np.where(self.g["inner"], d_inner, d_outer)
        self.gap = (d - self.sag * (1.0 - (self.g["r_mid"] / R_WAFER) ** 2))[None, :]
        if np.any(self.gap <= 10e-6):
            raise ValueError("sag closes the gap")

    def rhs(self, Tw, Tp, P):
        """Tw (m, n) and Tp (m, 1) in K, P (m, 1) in Torr -> (dTw/dt, dTp/dt)."""
        g = self.g
        Tgas = 0.5 * (Tw + Tp)
        h = k_he(Tgas) / (self.gap + jump_distance(P, Tgas, self.a_w)
                          + jump_distance(P, Tgas, self.a_p))
        q_gap = h * g["area"] * (Tw - Tp)
        q = q_gap + EMISSIVITY * SIGMA * g["area"] * (Tw ** 4 - T_WALL ** 4)
        flux = g["g_lat"] * (Tw[:, :-1] - Tw[:, 1:])
        q[:, :-1] += flux
        q[:, 1:] -= flux
        dTw = -q / (g["mass"] * cp_si(Tw))
        dTp = (q_gap.sum(axis=1, keepdims=True)
               - G_CHILLER * (Tp - (self.T_set + 273.15))) / C_PLATE
        return dTw, dTp

    def landing(self, m=1):
        """State the moment the wafer lands: isothermal wafer, plate at setpoint."""
        Tw = np.full((m, self.g["n"]), self.T0 + 273.15)
        Tp = np.full((m, 1), self.T_set + 273.15)
        P = np.full((m, 1), P_IDLE)
        return Tw, Tp, P

    def step(self, Tw, Tp, P, P_cmd, dt=DT):
        """One RK4 step with the command held. The chamber pressure is integrated
        exactly, since a held command makes it a known exponential."""
        e_half, e_full = np.exp(-0.5 * dt / TAU_P), np.exp(-dt / TAU_P)
        P_mid = P_cmd + (P - P_cmd) * e_half
        P_end = P_cmd + (P - P_cmd) * e_full
        k1w, k1p = self.rhs(Tw, Tp, P)
        k2w, k2p = self.rhs(Tw + 0.5 * dt * k1w, Tp + 0.5 * dt * k1p, P_mid)
        k3w, k3p = self.rhs(Tw + 0.5 * dt * k2w, Tp + 0.5 * dt * k2p, P_mid)
        k4w, k4p = self.rhs(Tw + dt * k3w, Tp + dt * k3p, P_end)
        return (Tw + (dt / 6.0) * (k1w + 2.0 * k2w + 2.0 * k3w + k4w),
                Tp + (dt / 6.0) * (k1p + 2.0 * k2p + 2.0 * k3p + k4p),
                P_end)

    # graded quantities and sensors, for state arrays (m, n)
    def t_mean(self, Tw):
        return Tw @ self.g["w_mean"] - 273.15

    def zone_dT(self, Tw):
        return np.abs(Tw @ self.g["w_in"] - Tw @ self.g["w_out"])

    def zone_means(self, Tw):
        return Tw @ self.g["w_in"] - 273.15, Tw @ self.g["w_out"] - 273.15

    def spots(self, Tw):
        return Tw @ self.g["w_spot_c"] - 273.15, Tw @ self.g["w_spot_e"] - 273.15

    def reading(self, Tw, Tp, P, rng=None):
        """Production sensors for a single state (m = 1)."""
        c, e = self.spots(Tw)
        out = {"center_C": float(c[0]), "edge_C": float(e[0]),
               "plate_C": float(Tp[0, 0]) - 273.15, "pressure_torr": float(P[0, 0])}
        if rng is not None:
            out["center_C"] += float(rng.normal(0.0, PYRO_RMS))
            out["edge_C"] += float(rng.normal(0.0, PYRO_RMS))
            out["plate_C"] += float(rng.normal(0.0, PLATE_RMS))
            out["pressure_torr"] *= 1.0 + float(rng.normal(0.0, MANO_REL))
        return out


# ---------------------------------------------------------------- the benchmark
def clairvoyant(wafer, horizon=1.2, guard=0.02, n_cand=48):
    """The perfect-knowledge cycle for one wafer.

    A controller that knows the wafer exactly and sees its whole state: every control
    period it holds the largest command whose constant-command lookahead keeps the zone
    difference under the cap, and it releases at the first control instant at which the
    mass mean is at or under the target. Returns (cycle_s, worst_zone_dT_K).
    """
    cands = np.exp(np.linspace(np.log(P_MIN), np.log(P_MAX), n_cand))[:, None]
    Tw, Tp, P = wafer.landing()
    n_sub = int(round(CTRL_DT / DT))
    n_look = int(round(horizon / DT))
    t, worst = 0.0, 0.0
    for k in range(int(round(T_CYCLE_MAX / CTRL_DT))):
        t = k * CTRL_DT
        if float(wafer.t_mean(Tw)[0]) <= T_TARGET:
            return round(t, 6), worst
        m = len(cands)
        W, Q, PP = np.repeat(Tw, m, 0), np.repeat(Tp, m, 0), np.repeat(P, m, 0)
        ok = np.ones(m, bool)
        for _ in range(n_look):
            W, Q, PP = wafer.step(W, Q, PP, cands)
            ok &= wafer.zone_dT(W) <= ZONE_CAP - guard
        P_cmd = np.array([[float((cands[ok][-1] if ok.any() else cands[0]).ravel()[0])]])
        for _ in range(n_sub):
            Tw, Tp, P = wafer.step(Tw, Tp, P, P_cmd)
            worst = max(worst, float(wafer.zone_dT(Tw)[0]))
    return float("inf"), worst
