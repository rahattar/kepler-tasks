"""Puller 11 PS-R07 supervisory controller (reference). Heater power and pull rate from one MPC: growth rate on the
V/G program (tight), true diameter at a setpoint above the grind minimum, crucible-rotation steps previewed from the
recipe. Model: identified HZ-B superheat chain (dead time, two lags, kh(L)), rotation effect with convection lag,
meniscus and growth-angle diameter dynamics (sheet physics); Kalman filter on meniscus, diameter and a growth
disturbance from the camera (camera offset from the caliper). fit.py embeds the parameters and the PS-R07 table."""
import io
import numpy as np
from scipy.optimize import lsq_linear

PARAMS = None
RECIPE_CSV = None
GH, PHI, BETA, CB = 0.30, 0.24, 0.050, -1.2
W_REF = 8.0
VP_MIN, VP_MAX, DVP_MAX = 0.2, 1.6, 0.05
P_MIN, P_MAX, DP_MAX = 60.0, 140.0, 0.6
A1 = np.exp(-GH)
C1 = (1 - A1) / GH
C3 = (1 - C1) / GH


def v_cool(L):
    L = np.asarray(L, float)
    return 0.98 - 0.10 * (1 - np.exp(-L / 400.0)) - 0.04 * (L / 1500.0)


def p_ref(L, b):
    return 100.0 - 14.0 * (np.asarray(L, float) / 1500.0) + b["p_off"]


def k_h(L, b):
    return b["kh0"] * (1 + 0.6 * (np.asarray(L, float) / 1500.0))


class Recipe:
    def __init__(self, text):
        t = np.genfromtxt(io.StringIO(text), delimiter=",", names=True)
        self.L, self.v, self.rpm = t["length_mm"], t["growth_rate_program_mm_min"], t["crucible_rpm"]
        self.steps = [(float(self.L[i]), float(self.rpm[i])) for i in range(len(self.L)) if i == 0 or self.rpm[i] != self.rpm[i - 1]]

    def __call__(self, L):
        return np.interp(L, self.L, self.v)

    def w_cmd(self, L):
        w = self.steps[0][1]
        for l0, wv in self.steps:
            if L >= l0:
                w = wv
        return w


class MimoMPC:
    def __init__(self, recipe, prm, d_ref=302.0, horizon=180, pblock=5, vfine=20, vblock_fine=2, vblock=10,
                 sv=0.004, sd=0.5, lam_p=0.02, lam_v=2e-4, every=2, preview=True, r_cam=0.15 ** 2, q_dist=2e-8,
                 q_x=1e-6, q_D=1e-5, pyro=False, t_ref=150.0):
        self.rc, self.prm, self.d_ref = recipe, prm, d_ref
        self.H, self.pb = horizon, pblock
        self.vfine, self.vbf, self.vb = vfine, vblock_fine, vblock
        self.sv, self.sd, self.lam_p, self.lam_v = sv, sd, lam_p, lam_v
        self.every, self.preview = every, preview
        self.t_ref = t_ref
        self.r_cam, self.q = r_cam, np.diag([q_x, q_D, q_dist])
        self.n = 0
        self.init = False
        # decision structure: P blocks over the horizon, v_p blocks (fine early, coarse later)
        self.nbP = horizon // pblock
        edges = list(range(0, vfine * vblock_fine, vblock_fine)) + list(range(vfine * vblock_fine, horizon, vblock))
        self.vedges = np.array(edges + [horizon])
        self.nbV = len(edges)
        self.vidx = np.searchsorted(self.vedges, np.arange(horizon), side="right") - 1

    # ---- model pieces
    def vc(self, L, w):
        return v_cool(L) - self.prm["c_rot"] * (w - W_REF)

    def plan(self, L0):
        prm, H = self.prm, self.H
        v0 = float(self.rc(L0))
        L_path = L0 + v0 * np.arange(1, H + 1)
        vt = self.rc(L_path)
        w = np.empty(H)
        x = self.w_m
        for i in range(H):
            cmd = self.rc.w_cmd(L_path[i]) if self.preview else self.rc.w_cmd(L0)
            x += (cmd - x) / prm["tau_rot"]
            w[i] = x
        vcp = self.vc(L_path, w) + self.z[2]                 # vc + d
        b = dict(kh0=prm["kh0"], p_off=self.p_off)
        kh = k_h(L_path, b)
        pr = p_ref(L_path, b)
        dd = int(round(prm["dead"]))
        past = list(self.hist[-dd:]) if dd > 0 else []
        past = [self.hist[0]] * (dd - len(past)) + past
        nP, nV = self.nbP, self.nbV
        nb = 1 + nP + nV
        S1 = np.zeros(nb); S = np.zeros(nb); X = np.zeros(nb); D = np.zeros(nb)
        S1[0], S[0], X[0], D[0] = self.S1_m, self.S_m, self.z[0], self.z[1]
        VG = np.zeros((H, nb)); DD = np.zeros((H, nb))
        for i in range(H):
            up = np.zeros(nb)
            j = i - dd
            if j < 0:
                up[0] = past[i]
            else:
                up[1 + min(j // self.pb, nP - 1)] = 1.0
            uv = np.zeros(nb)
            uv[1 + nP + self.vidx[i]] = 1.0
            drive = kh[i] * up
            drive[0] -= kh[i] * pr[i]
            # meniscus/diameter over the minute with S held at its start value
            vnat = -BETA * S
            vnat[0] += vcp[i]
            u = uv - vnat
            kd = 2.0 * vt[i] * PHI
            D = D - kd * (C1 * X + C3 * u)
            X = A1 * X + C1 * u
            S1 = S1 + (drive - S1) / prm["tau1"]
            S = S + (S1 - S) / prm["tau2"]
            vg = -BETA * S + GH * X
            vg[0] += vcp[i]
            VG[i] = vg
            DD[i] = D
        # decision variables: increments of the block values; values = last applied + cumulative sum
        Tp = np.tril(np.ones((nP, nP))); Tv = np.tril(np.ones((nV, nV)))
        Gp, Gv = VG[:, 1:1 + nP] @ Tp, VG[:, 1 + nP:] @ Tv
        Dp, Dv = DD[:, 1:1 + nP] @ Tp, DD[:, 1 + nP:] @ Tv
        vg0 = VG[:, 0] + VG[:, 1:1 + nP].sum(1) * self.hist[-1] + VG[:, 1 + nP:].sum(1) * self.vp_last
        d0 = DD[:, 0] + DD[:, 1:1 + nP].sum(1) * self.hist[-1] + DD[:, 1 + nP:].sum(1) * self.vp_last
        # diameter reference: first-order approach from the current estimate to the setpoint
        tt = np.arange(1, H + 1)
        dref = self.d_ref + (self.z[1] - self.d_ref) * np.exp(-tt / self.t_ref)
        A = np.vstack([np.hstack([Gp, Gv]) / self.sv, np.hstack([Dp, Dv]) / self.sd,
                       np.sqrt(self.lam_p) * np.hstack([np.eye(nP), np.zeros((nP, nV))]),
                       np.sqrt(self.lam_v) * np.hstack([np.zeros((nV, nP)), np.eye(nV)])])
        rhs = np.concatenate([(vt - vg0) / self.sv, (dref - d0) / self.sd, np.zeros(nP + nV)])
        vlen = np.diff(self.vedges)
        lb = np.concatenate([-DP_MAX * self.pb * np.ones(nP), -DVP_MAX * vlen])
        ub = -lb
        lb[0] = -DP_MAX * self.every; ub[0] = DP_MAX * self.every
        sol = lsq_linear(A, rhs, bounds=(lb, ub), method="bvls").x
        return float(self.hist[-1] + sol[0]), float(self.vp_last + sol[nP])

    def step(self, m):
        prm = self.prm
        L = m["length_mm"]
        v = float(self.rc(L))
        if not self.init:
            self.init = True
            self.w_m = m["crucible_rpm_set"]
            s0 = (self.vc(L, self.w_m) - v) / BETA
            self.S1_m = self.S_m = float(s0)
            b0 = dict(kh0=prm["kh0"], p_off=0.0)
            self.p_off = m["heater_power_kw"] - float(p_ref(L, b0) + s0 / k_h(L, b0))
            self.hist = [m["heater_power_kw"]]
            self.z = np.array([0.0, m["camera_diameter_mm"] - prm.get("cam_off", 0.0), 0.0])
            self.Pz = np.diag([0.01, 0.1, 1e-5])
            self.vp_last = m["pull_rate_mm_min"]
            self.u = (m["heater_power_kw"], m["pull_rate_mm_min"])
        else:
            # KF time update over the last minute (S held at its start value)
            kd = 2.0 * v * PHI
            u_known = self.vp_last - (self.vc(L, self.w_m) - BETA * self.S_m)
            F = np.array([[A1, 0.0, -C1], [-kd * C1, 1.0, kd * C3], [0.0, 0.0, 1.0]])
            g = np.array([C1 * u_known, -kd * C3 * u_known, 0.0])
            self.z = F @ self.z + g
            self.Pz = F @ self.Pz @ F.T + self.q
            # internal superheat model
            dd = int(round(prm["dead"]))
            Pd = self.hist[-dd] if len(self.hist) >= dd else self.hist[0]
            b = dict(kh0=prm["kh0"], p_off=self.p_off)
            self.S1_m += (k_h(L, b) * (Pd - p_ref(L, b)) - self.S1_m) / prm["tau1"]
            self.S_m += (self.S1_m - self.S_m) / prm["tau2"]
            self.w_m += (m["crucible_rpm_set"] - self.w_m) / prm["tau_rot"]
            self.hist.append(m["heater_power_kw"])
        # measurement update: camera = D + CB x
        Hm = np.array([CB, 1.0, 0.0])
        s = Hm @ self.Pz @ Hm + self.r_cam
        K = self.Pz @ Hm / s
        self.z = self.z + K * (m["camera_diameter_mm"] - self.prm.get("cam_off", 0.0) - Hm @ self.z)
        self.Pz = self.Pz - np.outer(K, Hm @ self.Pz)
        if self.n % self.every == 0:
            self.u = self.plan(L)
        self.n += 1
        self.vp_last = float(np.clip(self.u[1], VP_MIN, VP_MAX))
        return self.u[1], self.u[0]


class Controller:
    def __init__(self):
        prm = dict(PARAMS)
        d_ref = prm.pop("d_ref")
        self.mpc = MimoMPC(Recipe(RECIPE_CSV), prm, d_ref=d_ref)

    def step(self, obs):
        vp, p = self.mpc.step(obs)
        return {"pull_rate_mm_min": float(np.clip(vp, VP_MIN, VP_MAX)),
                "heater_power_kw": float(np.clip(p, P_MIN, P_MAX))}
