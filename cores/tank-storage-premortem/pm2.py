import numpy as np, time
from scipy.optimize import minimize_scalar
from tank import Tank
import pm
QD = pm.QD
SZ = pm.SZ
fc = pm.schedule(10, start_dow=0, design_nights=(0, 1, 2, 3, 4, 7, 8, 9), design_days=(1, 2, 3, 4, 7, 8, 9), seed=2)
rng = np.random.default_rng(9)
def hist_and_forecast(kw, dz=0.02):
    t = Tank(dz=dz, **kw)
    T1, e1, p1 = t.run(np.full(t.n, 12.5), pm.hist, SZ)
    T2, e2, _ = t.run(T1, fc)
    return p1, np.array([e2[i * 24:(i + 1) * 24].sum() for i in range(10)])
truths = {"sound": {}, "blocked": {"L_diff": 60.0}, "leak": {"leak": 1.5 / 3600}, "both": {"L_diff": 60.0, "leak": 1.5 / 3600}}
noise = 0.02 * rng.normal(size=(28 * 24, len(SZ))) + 0.03 * rng.normal(size=len(SZ))
res = {}
for name, kw in truths.items():
    p, e = hist_and_forecast(kw)
    res[name] = (p + noise, e)
sound_e = res["sound"][1]
for name in ["blocked", "leak", "both"]:
    obs, e = res[name]
    print("%-8s forecast vs sound %%:" % name, np.round(100 * (e / np.where(sound_e > 0, sound_e, 1) - 1), 1))
def fit_D(obs, extra=None, U=False):
    def f(logD):
        kw = dict(D_eff=10 ** logD); kw.update(extra or {})
        p, _ = hist_and_forecast(kw, dz=0.02)
        return np.sqrt(((p - obs) ** 2).mean())
    r = minimize_scalar(f, bounds=(-7, -3.5), method="bounded", options=dict(xatol=0.02))
    return 10 ** r.x, r.fun
for name in ["sound", "blocked", "both"]:
    obs, e = res[name]
    D, rms = fit_D(obs)
    _, ef = hist_and_forecast(dict(D_eff=D))
    print("%-8s D_eff fit %.2e  rms %.3f K  forecast err %%:" % (name, D, rms), np.round(100 * (ef / np.where(e > 0, e, 1) - 1), 1))
