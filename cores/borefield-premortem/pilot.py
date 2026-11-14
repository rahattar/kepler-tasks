import numpy as np
from scipy.optimize import minimize, minimize_scalar
from mfls import field_response, grid
rhoc = 2.4e6
H = 150.0
yr = 365.25 * 86400
mo = yr / 12
def loads(years, wint=45.0, summ=-15.0):
    m = np.arange(12 * years)
    return wint * np.clip(np.cos(2 * np.pi * (m + 0.5) / 12), 0, None) + summ * np.clip(-np.cos(2 * np.pi * (m + 0.5) / 12), 0, None)
def fluid(xy, q, lam, vD, Rb=0.10, T0=11.0, Hb=H):
    """monthly mean fluid temperature, extraction q W/m positive (cools the ground)."""
    alpha = lam / rhoc
    U = vD * 4.18e6 / rhoc
    n = len(q)
    tt = (np.arange(1, n + 1)) * mo
    g = field_response(xy, Hb, tt, lam, alpha, U)
    dq = np.diff(np.r_[0.0, q])
    Tb = np.array([T0 - (dq[:k + 1] * g[k::-1]).sum() for k in range(n)])
    return Tb - q * Rb
pil = grid(2, 2, 6.0)
tgt = grid(8, 8, 5.0)
rng = np.random.default_rng(3)
for vD in [3e-8, 6e-8, 1e-7]:
    for years in [3, 5]:
        q = loads(years)
        obs = fluid(pil, q, 2.5, vD) + rng.normal(0, 0.05, len(q))
        f1 = lambda lam: np.sqrt(np.mean((fluid(pil, q, lam, 0.0) - obs) ** 2))
        r1 = minimize_scalar(f1, bounds=(1.5, 5), method="bounded")
        res_tr = np.sqrt(np.mean((fluid(pil, q, 2.5, 0.0) - obs) ** 2))
        q20 = loads(20)
        truth = fluid(tgt, q20, 2.5, vD).min()
        p_trt = fluid(tgt, q20, 2.5, 0.0).min()
        p_abs = fluid(tgt, q20, r1.x, 0.0).min()
        print("vD %.0e pilot %dy: misfit with TRT lambda %.2f K; lambda-only fit %.2f -> misfit %.2f K | target 20y min fluid: truth %.2f, TRT lambda %.2f, refit lambda %.2f" % (
            vD, years, res_tr, r1.x, r1.fun, truth, p_trt, p_abs))
