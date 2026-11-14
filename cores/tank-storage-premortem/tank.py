"""Prototype stratified chilled-water tank for the pre-mortem.

Fixed grid in height, advection by whole-cell shifts with the remainder carried (no numerical diffusion),
mixing of the inlet zone with the entering water over h_m(Re), implicit diffusion, wall heat gain, and the
plant's cut-offs: a discharge stops when the outlet passes 7.0 C, a charge when the top outlet falls below 6.0 C.
"""
import numpy as np
from scipy.linalg import solve_banded

RHO_CP = 4.19e6          # J/m3K (taken constant)


def nu_of(T):
    return np.interp(T, [0, 5, 10, 15, 20], [1.79e-6, 1.52e-6, 1.31e-6, 1.14e-6, 1.00e-6])


class Tank:
    def __init__(self, H=14.0, Dia=16.0, L_diff=120.0, h_d=0.3, Re0=700.0, D_eff=2e-6, U=0.35, dz=0.02,
                 leak=0.0, dt=120.0):
        self.H, self.A = H, np.pi * Dia ** 2 / 4
        self.P = np.pi * Dia
        self.L, self.h_d, self.Re0, self.D, self.U = L_diff, h_d, Re0, D_eff, U
        self.dz, self.n = dz, int(round(H / dz))
        self.z = (np.arange(self.n) + 0.5) * dz
        self.leak, self.dt = leak, dt
        r = D_eff * dt / dz ** 2
        ab = np.zeros((3, self.n))
        ab[0, 1:] = -r
        ab[1, :] = 1 + 2 * r
        ab[2, :-1] = -r
        ab[1, 0] = ab[1, -1] = 1 + r
        self.ab = ab
        self.gain = U * self.P / self.A / RHO_CP * dt     # per K of (T_amb - T) per step

    def h_mix(self, Q, T_in):
        Re = abs(Q) / (self.L * nu_of(T_in))
        return self.h_d * (1 + (Re / self.Re0) ** 2)

    def run(self, T0, hours, sensors_z=None):
        """T0: initial profile on the grid. hours: list of dicts with Q (m3/s, + charge), T_in_charge, T_in_dis,
        T_amb, mode ('charge', 'discharge', 'standby'). Returns profile history at sensors and per-hour outlet."""
        T = T0.copy()
        carry = 0.0
        steps = int(round(3600 / self.dt))
        out = []
        prof = []
        state = {"stopped": False}
        for hr in hours:
            Q = hr["Q"]
            mode = hr["mode"]
            if mode == "standby":
                Q = -self.leak          # a passing valve: cold out at the bottom, system water in at the top
            delivered = 0.0
            t_out_sum = 0.0
            for _ in range(steps):
                q = Q
                if mode == "discharge" and T[0] > 7.0:
                    q = 0.0
                if mode == "charge" and T[-1] < 6.0:
                    q = 0.0
                if q != 0.0:
                    T_in = hr["T_in_charge"] if q > 0 else hr["T_in_dis"]
                    carry += q / self.A * self.dt
                    k = int(carry / self.dz)
                    if k != 0:
                        carry -= k * self.dz
                        outlet = T[:-k].copy() if False else None
                        if k > 0:      # water moves up; inflow at the bottom
                            leaving = T[-k:].copy()
                            T[k:] = T[:-k].copy()
                            T[:k] = T_in
                        else:
                            k = -k
                            leaving = T[:k].copy()
                            T[:-k] = T[k:].copy()
                            T[-k:] = T_in
                        if mode == "discharge":
                            delivered += RHO_CP * k * self.dz * self.A * (hr["T_in_dis"] - leaving.mean()) / 3.6e9
                    m = int(round(self.h_mix(q, T_in) / self.dz))
                    if q > 0:
                        T[:m] = T[:m].mean()
                    else:
                        T[-m:] = T[-m:].mean()
                T = solve_banded((1, 1), self.ab, T)
                T = T + self.gain * (hr["T_amb"] - T)
            out.append(delivered)
            if sensors_z is not None:
                prof.append(np.interp(sensors_z, self.z, T))
        return T, np.array(out), np.array(prof)
