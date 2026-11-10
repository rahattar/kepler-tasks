"""Fit the reference controller from the public data and write it out as one self-contained file.

  * per zone, the 4-state grey-box of controller_template.Model is identified from the trend log by
    multiple-shooting least squares on 2-day windows (air and embedded slab temperature), with the
    soffit convective/radiant coefficients pinned from physics (hc 5.0, hr 5.4 W/m2K) and the east
    valve treated as closed while its actuator was failed (maintenance log);
  * the forecast's diurnal damping factor is estimated from the forecast archive against the logged
    outdoor temperature;
  * controller_template.py is written to OUT with PARAMS embedded as a Python literal (repr), comfort
    margins 0.2 K at both band edges.

usage: python3 fit.py        (env OUT overrides the output path, default /app/controller.py)
Data: /app/data if present, else ../environment/data next to this file.
"""
import csv
import datetime as dt
import json
import os
import sys

import numpy as np
from scipy.optimize import least_squares

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import controller_template as cr  # noqa: E402

DATA = os.environ.get("TABS_DATA") or ("/app/data" if os.path.isdir("/app/data") else os.path.join(HERE, "..", "environment", "data"))
OUT = os.environ.get("OUT", "/app/controller.py")
MARGIN_HI, MARGIN_LO = 0.2, 0.2
VARIANT = "pinned"
PLACEHOLDER = "PARAMS = None  # @@PARAMS@@"

X0 = dict(Cc=300e3, Cl=150e3, Ca=15e3, Cm=60e3, Rcl=0.05, hc=5.0, hr=5.4, ham=8.0, UA=1.0, G=12.0,
          fsol=0.05, fa_sol=0.3)
LB = dict(Cc=50e3, Cl=30e3, Ca=3e3, Cm=5e3, Rcl=0.005, hc=0.3, hr=0.3, ham=0.5, UA=0.2, G=2.0, fsol=0.0, fa_sol=0.0)
UB = dict(Cc=1500e3, Cl=1000e3, Ca=80e3, Cm=400e3, Rcl=0.5, hc=15.0, hr=15.0, ham=30.0, UA=4.0, G=30.0,
          fsol=0.2, fa_sol=1.0)
STUCK = (dt.datetime(2017, 6, 5, 7, 30), dt.datetime(2017, 6, 9, 17, 15))


def load():
    with open(os.path.join(DATA, "trend_log.csv")) as f:
        rows = list(csv.DictReader(f))
    L = {k: np.array([float(r[k]) for r in rows]) for k in rows[0] if k != "time"}
    L["time"] = [dt.datetime.fromisoformat(r["time"]) for r in rows]
    s = [cr.sched(t) for t in L["time"]]
    L["q"] = np.array([x[3] for x in s])
    st = np.array([STUCK[0] <= t <= STUCK[1] for t in L["time"]])
    L["east_valve_command"] = np.where(st, 0.0, L["east_valve_command"])
    return L


def simulate(m, L, z, i0, i1):
    x = np.array([L[f"{z}_slab_temp_c"][i0], 0.5 * (L[f"{z}_air_temp_c"][i0] + L[f"{z}_slab_temp_c"][i0]),
                  L[f"{z}_air_temp_c"][i0], L[f"{z}_air_temp_c"][i0]])
    out = np.zeros((i1 - i0, 2))
    for i in range(i0, i1):
        iv = L[f"facade_irradiance_{z}_w_m2"][i]
        qa, qm = m.gains(L["q"][i], iv)
        A, B, bq = m.disc(L["doas_flow_fraction"][i])
        q = L[f"{z}_valve_command"][i] * m.G * max(x[0] - L["supply_temp_c"][i], 0.0)
        x = A @ x + B @ np.array([L["outdoor_temp_c"][i], cr.T_DOAS, qa, qm]) - bq * q
        out[i - i0] = x[2], x[0]
    return out


def fit_zone(L, z, fixed, win=192):
    names = [k for k in cr.Model.NAMES if k not in fixed]
    sc = np.array([X0[k] for k in names])
    n = len(L["outdoor_temp_c"]) - 1
    starts = list(range(0, n - win, win))

    def th(v):
        d = dict(X0)
        d.update(fixed)
        d.update(dict(zip(names, v * sc)))
        return d

    def resid(v):
        m = cr.Model(th(v))
        r = []
        for s in starts:
            pr = simulate(m, L, z, s, s + win)
            r.append(pr[24:, 0] - L[f"{z}_air_temp_c"][s + 25:s + win + 1])
            r.append(0.5 * (pr[24:, 1] - L[f"{z}_slab_temp_c"][s + 25:s + win + 1]))
        return np.concatenate(r)

    sol = least_squares(resid, np.ones(len(names)), bounds=(np.array([LB[k] for k in names]) / sc,
                                                            np.array([UB[k] for k in names]) / sc), max_nfev=200)
    return th(sol.x), float(np.sqrt(np.mean(sol.fun ** 2)))


def kappa_from_archive(L):
    T = {t: v for t, v in zip(L["time"], L["outdoor_temp_c"])}
    by = {}
    with open(os.path.join(DATA, "forecast_archive.csv")) as f:
        for r in csv.DictReader(f):
            by.setdefault(r["issued"], []).append(r)
    X, Y = [], []
    for iss, rs in by.items():
        f = np.array([float(r["outdoor_temp_c"]) for r in rs])
        if len(f) < 192:
            continue
        m = cr.running_mean(f)
        for k in range(96):
            tv = dt.datetime.fromisoformat(rs[k]["valid_time"])
            if tv in T:
                X.append(f[k] - m[k])
                Y.append(T[tv] - m[k])
    X, Y = np.array(X), np.array(Y)
    slope = float(np.sum(X * Y) / np.sum(X * X))
    return 1 - 1 / slope


def main():
    fixed = dict(hc=5.0, hr=5.4) if VARIANT == "pinned" else {}
    print("data:", os.path.abspath(DATA))
    L = load()
    theta = {}
    for z in cr.ZONES:
        th, rms = fit_zone(L, z, fixed)
        theta[z] = {k: float(v) for k, v in th.items()}
        print(z, f"rms {rms:.3f}", {k: float("%.4g" % v) for k, v in theta[z].items()}, flush=True)
    kappa = float(kappa_from_archive(L))
    print(f"kappa {kappa:.3f}")
    with open(os.path.join(DATA, "chiller.json")) as f:
        chil = json.load(f)
    P = dict(theta=theta, chiller={k: chil[k] for k in ("outdoor_temp_c", "leaving_temp_c", "cop", "capacity_kw")},
             kappa=kappa, margin_hi=MARGIN_HI, margin_lo=MARGIN_LO, variant=VARIANT)
    with open(os.path.join(HERE, "controller_template.py")) as f:
        src = f.read()
    assert src.count(PLACEHOLDER) == 1, "PARAMS placeholder not found exactly once in the template"
    out_dir = os.path.dirname(os.path.abspath(OUT))
    os.makedirs(out_dir, exist_ok=True)
    with open(OUT, "w") as f:
        f.write(src.replace(PLACEHOLDER, "PARAMS = " + repr(P)))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
