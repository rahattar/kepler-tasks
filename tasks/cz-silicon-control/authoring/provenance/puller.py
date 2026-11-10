"""Sealed definition: body growth of a 300 mm CZ crystal on Puller 11, hot zone HZ-B. Units: mm, min, K, kW.

Hot-zone constants (HZ) are fixed for the puller; each body varies around them (make_body). The records' bodies are
seeds 101-108 on the fast-pull recipe; the graded bodies are seeds 1-8 on the perfect-silicon recipe. A crucible
rotation step changes melt convection and the heat reaching the interface within minutes (lag tau_rot); the heater
reaches the interface only after a dead time and two lags.
  meniscus     dh/dt = v_p - v_g
  diameter     dD/dt = -2 v_g PHI_H (h - H0)
  growth       v_g   = v_cool(L) - C_ROT (w_eff - W_REF) + aging + GH (h - H0) - BETA S
  rotation     TAU_ROT dw_eff/dt = w_cmd(L) - w_eff
  superheat    TAU1 dS1/dt = K_h(L) (P(t - DEAD) - P_ref(L)) - S1 ;  TAU2 dS/dt = S1 - S
"""
import numpy as np

H0 = 6.8
PHI_H = 0.24
GH = 0.30
BETA = 0.050
CB = -1.2
D_START = 304.0           # true diameter at the end of the crown
D_MIN = 301.0             # grind minimum
L_BODY = 1500.0
DT = 0.25
VP_MIN, VP_MAX, DVP_MAX = 0.2, 1.6, 0.05
P_MIN, P_MAX, DP_MAX = 60.0, 140.0, 0.6
W_REF = 8.0

# hot zone HZ-B (sealed)
HZ = dict(dead=24.0, kh0=0.36, tau1=30.0, tau2=12.0, c_rot=0.015, tau_rot=6.0, cam_off=0.8)
# design sheet values (HZ-A commissioning), used only by the evidence studies
SHEET = dict(dead=15.0, kh0=0.45, tau1=25.0, tau2=12.0, c_rot=0.006, tau_rot=5.0, cam_off=0.0)

RECIPES = {
    "fast_pull": dict(w=[(0, 9.0), (350, 7.0), (800, 5.0), (1200, 4.0)],          # fast-pull production recipe
                v=lambda L: 0.92 + 0.02 * np.sin(np.pi * L / 1500.0) - 0.08 * (L / 1500.0)),
    "perfect_si": dict(w=[(0, 8.0), (300, 12.0), (700, 7.0), (1100, 4.0)],
                v=lambda L: 0.78 + 0.04 * np.sin(np.pi * L / 1500.0) - 0.06 * (L / 1500.0)),
}


def w_cmd(L, recipe):
    w = recipe["w"][0][1]
    for l0, wv in recipe["w"]:
        if L >= l0:
            w = wv
    return w


def v_cool(L):
    L = np.asarray(L, float)
    return 0.98 - 0.10 * (1 - np.exp(-L / 400.0)) - 0.04 * (L / 1500.0)


def p_ref(L, b):
    return 100.0 - 14.0 * (L / 1500.0) + b["p_off"]


def k_h(L, b):
    return b["kh0"] * (1 + 0.6 * (L / 1500.0))


def make_body(seed, hz=HZ):
    rng = np.random.default_rng(seed)
    return dict(kh0=hz["kh0"] * rng.uniform(0.95, 1.05), dead=hz["dead"] + rng.uniform(-1.0, 1.0),
                tau1=hz["tau1"], tau2=hz["tau2"], c_rot=hz["c_rot"] * rng.uniform(0.92, 1.08), tau_rot=hz["tau_rot"],
                age=rng.uniform(-0.02, 0.02), age_rate=rng.uniform(-0.015, 0.015) / 1000.0,
                p_off=rng.uniform(-3.0, 3.0), pyro_drift=rng.uniform(-0.25, 0.25) / 60.0, cam_off=hz.get("cam_off", 0.0),
                noise_seed=int(rng.integers(1 << 30)))


class Puller:
    def __init__(self, b, recipe):
        self.b, self.rc = b, recipe
        self.rng = np.random.default_rng(b["noise_seed"])
        self.t = 0.0
        self.L = 0.0
        self.D = D_START
        self.h = H0
        self.w = w_cmd(0.0, recipe)
        v0 = float(recipe["v"](0.0))
        s0 = (self.vc() - v0) / BETA
        self.S1 = self.S = s0
        self.vp = v0
        self.P = float(p_ref(0.0, b) + s0 / k_h(0.0, b))
        self.hist_P = []
        self.log = []

    def vc(self):
        b = self.b
        return float(v_cool(self.L) - b["c_rot"] * (self.w - W_REF) + b["age"] + b["age_rate"] * self.L)

    def growth(self):
        return self.vc() + GH * (self.h - H0) - BETA * self.S

    def measure(self):
        b = self.b
        cam = self.D + b["cam_off"] + CB * (self.h - H0) + self.rng.normal(0, 0.15)
        pyro = self.S + b["pyro_drift"] * self.t + self.rng.normal(0, 0.3)
        return dict(t=self.t, length_mm=self.L, camera_diameter_mm=cam, pull_rate_mm_min=self.vp,
                    heater_power_kw=self.P, pyrometer_k=pyro, crucible_rpm_set=w_cmd(self.L, self.rc))

    def apply(self, vp_set, p_set, minutes=1.0):
        b = self.b
        vp_set = float(np.clip(vp_set, VP_MIN, VP_MAX))
        p_set = float(np.clip(p_set, P_MIN, P_MAX))
        k = int(round(b["dead"] / DT))
        for _ in range(int(round(minutes / DT))):
            self.vp += np.clip(vp_set - self.vp, -DVP_MAX * DT, DVP_MAX * DT)
            self.P += np.clip(p_set - self.P, -DP_MAX * DT, DP_MAX * DT)
            self.hist_P.append(self.P)
            P_del = self.hist_P[-k - 1] if len(self.hist_P) > k else self.hist_P[0]
            vg = self.growth()
            dS1 = (k_h(self.L, b) * (P_del - p_ref(self.L, b)) - self.S1) / b["tau1"]
            dS = (self.S1 - self.S) / b["tau2"]
            dw = (w_cmd(self.L, self.rc) - self.w) / b["tau_rot"]
            self.S1 += DT * dS1
            self.S += DT * dS
            self.w += DT * dw
            self.h += DT * (self.vp - vg)
            self.D += DT * (-2.0 * vg * PHI_H * (self.h - H0))
            self.L += DT * vg
            self.t += DT
        vg = self.growth()
        self.log.append((self.t, self.L, self.D, self.h, vg, float(self.rc["v"](self.L)), self.vp, self.P, self.S))
        return vg


def run(controller_factory, b, recipe, max_min=4000):
    pl = Puller(b, recipe)
    ctl = controller_factory()
    while pl.L < L_BODY and pl.t < max_min:
        vp, p = ctl.step(pl.measure())
        pl.apply(vp, p, 1.0)
    return np.array(pl.log)


GRADED_SEEDS = tuple(range(1, 9))
RECORD_SEEDS = tuple(range(101, 109))


def score(log, l0=50.0, win=0.01, avg_mm=5):
    """V/G relative error (growth rate over its program, averaged over avg_mm of body), true diameter stats."""
    t, L, D, h, vg, vt = (log[:, i] for i in range(6))
    m = L >= l0
    Lg = np.arange(l0, L[-1], 1.0)
    rel = np.interp(Lg, L, vg / vt - 1.0)
    k = max(int(avg_mm), 1)
    ra = np.convolve(rel, np.ones(k) / k, mode="valid")
    Dg = np.interp(Lg, L, D)
    return dict(vg_max=float(np.max(np.abs(ra))), vg_out_mm=float(np.sum(np.abs(ra) > win)),
                vg_rms=float(np.sqrt(np.mean(ra ** 2))), d_min=float(Dg.min()), d_mean=float(Dg.mean()),
                done=bool(L[-1] >= L_BODY), minutes=float(t[-1]))
