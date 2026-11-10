# ---- reference model (written from textbook physics; shares no code with the verifier) ----
#
# Equal-AREA annuli (the verifier uses equal radial width), a forced ring boundary on the
# zone split, Kennard temperature jump with one lumped jump coefficient per station and
# film, a lumped plate with a chiller, and a first-order pressure lag. Everything is
# vectorised over a leading batch axis so hypotheses, candidate commands and
# characterisation runs integrate together.
import math

import numpy as np

R_U = 8.314462618
SIGMA = 5.670374419e-8
TORR = 133.32236842
M_HE = 4.002602e-3
GAMMA_HE = 5.0 / 3.0
PR_HE = 0.68
MU_HE_300 = 1.99e-5
K_HE_300 = 0.152
JUMP_PREFIX = 2.0 * GAMMA_HE / (GAMMA_HE + 1.0) / PR_HE


class Grid:
    def __init__(self, n, r_wafer, r_split, spot_c, spot_e):
        a_split = (r_split / r_wafer) ** 2
        n_in = max(2, int(round(n * a_split)))
        e = np.concatenate([np.sqrt(np.linspace(0.0, r_split ** 2, n_in + 1)),
                            np.sqrt(np.linspace(r_split ** 2, r_wafer ** 2, n - n_in + 1))[1:]])
        self.edges = e
        self.n = n
        self.area = np.pi * (e[1:] ** 2 - e[:-1] ** 2)
        self.r_mid = 0.5 * (e[1:] + e[:-1])
        self.inner = self.r_mid < r_split
        self.w_mean = self.area / self.area.sum()
        a_in = self.area * self.inner
        a_out = self.area * (~self.inner)
        self.w_in = a_in / a_in.sum()
        self.w_out = a_out / a_out.sum()
        self.w_c = self._overlap(*spot_c)
        self.w_e = self._overlap(*spot_e)
        self.r_wafer = r_wafer

    def _overlap(self, a, b):
        lo = np.clip(self.edges[:-1], a, b)
        hi = np.clip(self.edges[1:], a, b)
        w = np.pi * (hi ** 2 - lo ** 2)
        return w / w.sum()


class Model:
    """Batch model. Per-row parameters: gap profile (rows, n), jump coefficient J (rows, 1),
    plate setpoint (rows, 1). Shared: wafer properties, plate C and G, actuator tau."""

    def __init__(self, grid, wafer, C_plate, G_chiller, tau):
        self.g = grid
        t = wafer["thickness_um"] * 1e-6
        self.mass = wafer["density_kg_m3"] * t * grid.area
        dr = np.diff(grid.r_mid)
        self.g_lat = wafer["thermal_conductivity_W_mK"] * t * 2.0 * np.pi * grid.edges[1:-1] / dr
        self.eps = wafer["top_face_emissivity"]
        self.T_wall = wafer["chamber_wall_temperature_C"] + 273.15
        self.C, self.G, self.tau = C_plate, G_chiller, tau

    def gap(self, d_in, d_out, sag):
        """(rows,) arrays -> (rows, n) gap in metres."""
        d = np.where(self.g.inner[None, :], np.asarray(d_in)[:, None], np.asarray(d_out)[:, None])
        phi = 1.0 - (self.g.r_mid / self.g.r_wafer) ** 2
        return np.maximum(d - np.asarray(sag)[:, None] * phi[None, :], 5e-6)

    def rhs(self, Tw, Tp, P, gap, J, Tset):
        Tg = 0.5 * (Tw + Tp)
        mu = MU_HE_300 * (Tg / 300.0) ** 0.69
        lam = (mu / (P * TORR)) * np.sqrt(np.pi * R_U * Tg / (2.0 * M_HE))
        k = K_HE_300 * (Tg / 300.0) ** 0.71
        h = k / (gap + J * JUMP_PREFIX * lam)
        qg = h * self.g.area * (Tw - Tp)
        q = qg + self.eps * SIGMA * self.g.area * (Tw ** 4 - self.T_wall ** 4)
        fl = self.g_lat * (Tw[:, :-1] - Tw[:, 1:])
        q[:, :-1] += fl
        q[:, 1:] -= fl
        cp = 703.0 + 0.28 * (Tw - 300.0)
        dTw = -q / (self.mass * cp)
        dTp = (qg.sum(axis=1, keepdims=True) - self.G * (Tp - Tset)) / self.C
        return dTw, dTp

    def step(self, Tw, Tp, P, Pc, gap, J, Tset, dt):
        eh, ef = math.exp(-0.5 * dt / self.tau), math.exp(-dt / self.tau)
        Pm = Pc + (P - Pc) * eh
        Pe = Pc + (P - Pc) * ef
        a1, b1 = self.rhs(Tw, Tp, P, gap, J, Tset)
        a2, b2 = self.rhs(Tw + 0.5 * dt * a1, Tp + 0.5 * dt * b1, Pm, gap, J, Tset)
        a3, b3 = self.rhs(Tw + 0.5 * dt * a2, Tp + 0.5 * dt * b2, Pm, gap, J, Tset)
        a4, b4 = self.rhs(Tw + dt * a3, Tp + dt * b3, Pe, gap, J, Tset)
        return (Tw + dt / 6.0 * (a1 + 2 * a2 + 2 * a3 + a4),
                Tp + dt / 6.0 * (b1 + 2 * b2 + 2 * b3 + b4), Pe)

    # observables, Celsius
    def t_mean(self, Tw):
        return Tw @ self.g.w_mean - 273.15

    def zone_dT(self, Tw):
        return np.abs(Tw @ self.g.w_in - Tw @ self.g.w_out)

    def zones(self, Tw):
        return Tw @ self.g.w_in - 273.15, Tw @ self.g.w_out - 273.15

    def spots(self, Tw):
        return Tw @ self.g.w_c - 273.15, Tw @ self.g.w_e - 273.15
# ---- end reference model ----
