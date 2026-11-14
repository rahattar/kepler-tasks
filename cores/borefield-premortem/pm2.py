import numpy as np
from scipy.optimize import minimize, minimize_scalar
from mfls import field_response, grid
rhoc = 2.4e6
H = 150.0
yr = 365.25 * 86400
mo = yr / 12
def loads(years, wint=28.0, summ=-12.0):
    m = np.arange(12 * years)
    c = np.cos(2 * np.pi * (m + 0.5) / 12)
    return wint * np.clip(c, 0, None) + summ * np.clip(-c, 0, None)
_cache = {}
def gfun(xy, lam, vD, n):
    key = (xy.tobytes(), round(lam, 4), round(vD * 1e10), n)
    if key not in _cache:
        _cache[key] = field_response(xy, H, np.arange(1, n + 1) * mo, lam, lam / rhoc, vD * 4.18e6 / rhoc)
    return _cache[key]
def fluid(xy, q, lam, vD, Rb=0.10, T0=11.0):
    g = gfun(xy, lam, vD, len(q))
    dq = np.diff(np.r_[0.0, q])
    Tb = np.array([T0 - (dq[:k + 1] * g[k::-1]).sum() for k in range(len(q))])
    return Tb - q * Rb
old = grid(4, 4, 6.0)
new = grid(8, 8, 6.0)
rng = np.random.default_rng(3)
q5 = loads(5)
q20 = loads(20)
print("target min monthly fluid T, 20 y, no conditions: %.2f C" % fluid(new, q20, 2.5, 0.0).min())
for vD, scale in [(1e-7, 1.0), (0.0, 1.07), (1e-7, 1.07), (5e-8, 1.0)]:
    true_q = q5                      # what the ground took
    metered = q5 * scale             # what the heat meter reports (set for water on a glycol loop)
    obs = fluid(old, true_q, 2.5, vD) + rng.normal(0, 0.05, len(q5))
    base = np.sqrt(np.mean((fluid(old, metered, 2.5, 0.0) - obs) ** 2))
    f_l = minimize_scalar(lambda l: np.sqrt(np.mean((fluid(old, metered, l, 0.0) - obs) ** 2)), bounds=(1.5, 5), method="bounded")
    vs = np.r_[0, np.geomspace(5e-9, 3e-7, 30)]
    m_v = [np.sqrt(np.mean((fluid(old, metered, 2.5, v) - obs) ** 2)) for v in vs]
    v_best = vs[int(np.argmin(m_v))]
    truth = fluid(new, q20, 2.5, vD).min()
    print("vD %.0e meter x%.2f | misfit stated %.2f K | lambda refit %.2f -> %.2f K | vD-only fit %.1e -> %.2f K | target min: truth %.2f, stated %.2f, lambda refit %.2f, vD-only %.2f" % (
        vD, scale, base, f_l.x, f_l.fun, v_best, min(m_v), truth, fluid(new, q20, 2.5, 0.0).min(), fluid(new, q20, f_l.x, 0.0).min(), fluid(new, q20, 2.5, v_best).min()))
