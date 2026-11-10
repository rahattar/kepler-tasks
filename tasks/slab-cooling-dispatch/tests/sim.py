"""Closed-loop simulation of the two-zone TABS group: sensors, valves, chiller, per-week metrics."""
import datetime as _dt
import numpy as np
from zone import Plant
from chiller import cop, leaving_temp, TS_MIN, TS_MAX
from instance import DT, SPD, ZONES, ZP

NSUB = 15
DTS = DT / NSUB
NOISE = 0.1
EPOCH = _dt.datetime(2017, 1, 1)


def iso(ep, t):
    return (EPOCH + _dt.timedelta(days=int(ep["d0"]), minutes=15 * int(t))).strftime("%Y-%m-%dT%H:%M")


def make_obs(ep, t, X, last, fc, rng, plants):
    f = fc.latest(t)
    tp = max(t - 1, 0)
    zones = {}
    for z in ZONES:
        pl = plants[z]
        zones[z] = {"air_temp_c": float(X[z][pl.ia] + NOISE * rng.standard_normal()),
                    "slab_temp_c": float(X[z][pl.isens] + NOISE * rng.standard_normal()),
                    "return_temp_c": float(last["ret"][z] + NOISE * rng.standard_normal()),
                    "valve_duty": float(last["duty"][z])}
    return {
        "time": iso(ep, t),
        "outdoor_temp_c": float(ep["wx"]["Tout"][t] + 0.2 * rng.standard_normal()),
        "facade_irradiance_w_m2": {
            "west": float(max(0.0, ep["wx"]["Iw"][tp] * (1 + 0.03 * rng.standard_normal()))),
            "east": float(max(0.0, ep["wx"]["Ie"][tp] * (1 + 0.03 * rng.standard_normal())))},
        "supply_temp_c": float(last["sup"] + NOISE * rng.standard_normal()),
        "supply_setpoint_c": float(last["sp"]),
        "zones": zones,
        "forecast": {"issued": iso(ep, f["issued_step"]), "step_minutes": 15,
                     "outdoor_temp_c": f["Tout"].tolist(),
                     "facade_irradiance_w_m2": {"west": f["Iw"].tolist(), "east": f["Ie"].tolist()}},
    }


def make_plants():
    return {z: Plant(ZP[z]) for z in ZONES}


def run(ep, ctrl, X0, fc, t0=0, t1=None, plants=None, seed=0, logger=None, want_obs=True):
    """ctrl(obs, t, X_true) -> (supply setpoint, {zone: duty}). Returns per-week metrics, final states."""
    plants = plants or make_plants()
    t1 = ep["n"] if t1 is None else t1
    rng = np.random.default_rng(seed)
    X = {z: X0[z].copy() for z in ZONES}
    nweek = int(np.ceil((t1 - t0) / (7 * SPD)))
    W = {k: np.zeros(nweek) for k in ("cost", "elec", "qth")}
    for z in ZONES:
        for k in ("hot", "cold"):
            W[f"{k}_{z}"] = np.zeros(nweek)
    G = [plants[z].G for z in ZONES]
    mc = {z: ZP[z]["mdot"] * ZP[z]["cw"] for z in ZONES}
    area = ZP["west"]["area"]
    last = dict(sup=X["west"][plants["west"].ip], sp=20.0, ret={z: X[z][plants[z].ip] for z in ZONES},
                duty={z: 0.0 for z in ZONES})
    sch, wx = ep["sch"], ep["wx"]
    for t in range(t0, t1):
        obs = make_obs(ep, t, X, last, fc, rng, plants) if want_obs else {"time": iso(ep, t)}
        sp, duty = ctrl(obs, t, X)
        sp = float(sp)
        if not np.isfinite(sp):
            sp = TS_MAX
        sp = float(np.clip(sp, TS_MIN, TS_MAX))
        nopen = {}
        for z in ZONES:
            d = float(duty.get(z, 0.0)) if isinstance(duty, dict) else 0.0
            d = 0.0 if not np.isfinite(d) else min(max(d, 0.0), 1.0)
            nopen[z] = int(round(d * NSUB))
        wk = (t - t0) // (7 * SPD)
        Tout = wx["Tout"][t]
        sup_acc = 0.0
        ret_acc = {z: 0.0 for z in ZONES}
        for s in range(NSUB):
            opens = [s < nopen[z] for z in ZONES]
            Tp = [X[z][plants[z].ip] for z in ZONES]
            Ts = leaving_temp(sp, Tout, opens, G, Tp, area)
            sup_acc += Ts
            qsum = 0.0
            for i, z in enumerate(ZONES):
                pl = plants[z]
                x = X[z]
                pon = opens[i] and x[pl.ip] > Ts
                g = ep["g"][z]
                u = np.array([Ts, Tout, pl.p["Tdoas"], g["Qa"][t], g["Qm"][t], g["Qs"][t], g["Qg"][t]])
                Ad, Bd = pl.disc(pon, sch["doas"][t], pl.hc_now(x), DTS)
                xn = Ad @ x + Bd @ u
                if pon:
                    q = pl.G * (0.5 * (x[pl.ip] + xn[pl.ip]) - Ts)
                    qsum += q
                    ret_acc[z] += Ts + q / mc[z]
                else:
                    ret_acc[z] += xn[pl.ip]
                X[z] = xn
                if sch["occ"][t]:
                    top = pl.top(xn)
                    W[f"hot_{z}"][wk] += max(0.0, top - ep["hi"][t]) * DTS / 3600.0
                    W[f"cold_{z}"][wk] += max(0.0, ep["lo"][t] - top) * DTS / 3600.0
            if qsum > 0:
                e = qsum * area * DTS / 3.6e6
                el = e / float(cop(Ts, Tout))
                W["qth"][wk] += e; W["elec"][wk] += el; W["cost"][wk] += el * sch["price"][t]
        last = dict(sup=sup_acc / NSUB, sp=sp, ret={z: ret_acc[z] / NSUB for z in ZONES},
                    duty={z: nopen[z] / NSUB for z in ZONES})
        if logger is not None:
            logger(t, obs, sp, dict(last["duty"]), X, last)
    for z in ZONES:
        W[f"dev_{z}"] = W[f"hot_{z}"] + W[f"cold_{z}"]
    return W, X
