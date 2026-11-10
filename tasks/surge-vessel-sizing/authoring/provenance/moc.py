"""Method of characteristics for a pumping main: pump trip with rundown, ideal non-return valve closure, air vessel
with a differential orifice, quasi-steady Darcy-Weisbach friction, and a longitudinal profile (MS-SV clause 2)."""
import math
import numpy as np
from scipy.optimize import brentq

G = 9.81
HB = 10.2      # atmospheric pressure head, m water


def build(sections, dt):
    """Each section gets an integer number of reaches at the common dt; its wave speed is adjusted to fit."""
    x, D, a, f = [], [], [], []
    xs = 0.0
    for s in sections:
        n = max(1, int(round(s["L"] / (s["a"] * dt))))
        for i in range(n):
            x.append(xs + i * s["L"] / n); D.append(s["D"]); a.append(s["L"] / (n * dt)); f.append(s["f"])
        xs += s["L"]
    x.append(xs); D.append(sections[-1]["D"]); a.append(a[-1]); f.append(f[-1])
    return np.array(x), np.array(D), np.array(a), np.array(f)


def pump_fns(pu):
    def head(alpha, q):
        v = q / pu["QR"]
        return pu["HR"] * (pu["a0"] * alpha ** 2 + pu["a1"] * alpha * v + pu["a2"] * v ** 2)
    def dhead_dq(alpha, q):
        return pu["HR"] * (pu["a1"] * alpha / pu["QR"] + 2 * pu["a2"] * q / pu["QR"] ** 2)
    def torque(alpha, q):
        v = q / pu["QR"]
        return pu["b0"] * alpha ** 2 + pu["b1"] * alpha * v + pu["b2"] * v ** 2
    return head, dhead_dq, torque


def steady(P):
    x, D, a, f = build(P["sections"], P["dt"])
    head, _, _ = pump_fns(P["pump"])
    npump = P["pump"]["n"]
    seg = np.diff(x); Dm = 0.5 * (D[:-1] + D[1:]); fm = 0.5 * (f[:-1] + f[1:]); Am = math.pi * Dm ** 2 / 4
    loss = lambda Q: np.sum(fm * seg / Dm * (Q / Am) ** 2 / (2 * G))
    lo, hi = 1e-5, 10.0
    for _ in range(100):
        Q = 0.5 * (lo + hi)
        if P["Hs"] + head(1.0, Q / npump) > P["Ht"] + loss(Q): lo = Q
        else: hi = Q
    Q0 = 0.5 * (lo + hi)
    H = np.empty(len(x)); H[0] = P["Hs"] + head(1.0, Q0 / npump)
    H[1:] = H[0] - np.cumsum(fm * seg / Dm * (Q0 / Am) ** 2 / (2 * G))
    return x, D, a, f, Q0, H


def run(P, T=150.0, record=()):
    dt = P["dt"]
    x, D, a, f, Q0, H = steady(P)
    N = len(x) - 1
    A = math.pi * D ** 2 / 4
    B = a / (G * A)
    Rf = f * a * dt / (2 * G * D * A ** 2)
    zp = np.interp(x, P["profile"][0], P["profile"][1])
    pu = P["pump"]; npump = pu["n"]
    head, dhead, torque = pump_fns(pu)
    omegaR = pu["NR"] * 2 * math.pi / 60.0
    TR = 1000 * G * pu["QR"] * pu["HR"] / (pu["eta"] * omegaR)
    Q = np.full(N + 1, Q0)
    ves = P.get("vessel")
    if ves:
        Vg = ves["Vg0"]; Cg = (H[0] + HB - ves["zw"]) * Vg ** ves["n"]
    alpha, qp, nrv, qv_prev = 1.0, Q0 / npump, True, 0.0
    Hmin, Hmax = H.copy(), H.copy(); Vgmax = Vg if ves else 0.0
    rec = {k: [] for k in record}; ts = []
    for step in range(int(T / dt)):
        Hn = np.empty_like(H); Qn = np.empty_like(Q)
        CP = H[:-2] + B[1:-1] * Q[:-2] - Rf[1:-1] * Q[:-2] * np.abs(Q[:-2])
        CM = H[2:] - B[1:-1] * Q[2:] + Rf[1:-1] * Q[2:] * np.abs(Q[2:])
        Hn[1:-1] = 0.5 * (CP + CM); Qn[1:-1] = (CP - CM) / (2 * B[1:-1])
        CPd = H[-2] + B[-1] * Q[-2] - Rf[-1] * Q[-2] * abs(Q[-2])
        Hn[-1] = P["Ht"]; Qn[-1] = (CPd - P["Ht"]) / B[-1]
        CM0 = H[1] - B[0] * Q[1] + Rf[0] * Q[1] * abs(Q[1])
        if nrv:
            alpha = max(alpha - torque(alpha, qp) * TR / (pu["I"] * omegaR) * dt, 0.0)
        c2 = -pu["HR"] * pu["a2"] / pu["QR"] ** 2      # > 0; pump head = Hs + HR a0 alpha^2 - c2 qp^2 (a1 = 0)
        def qpump(qv):
            c0 = P["Hs"] + pu["HR"] * pu["a0"] * alpha ** 2 - CM0 - B[0] * qv
            if c0 <= 0: return 0.0
            bn = B[0] * npump
            return (-bn + math.sqrt(bn * bn + 4 * c2 * c0)) / (2 * c2)
        def g(qv, with_pump):
            qpp = qpump(qv) if with_pump else 0.0
            H0 = CM0 + B[0] * (npump * qpp + qv)
            Vn = Vg + 0.5 * dt * (qv + qv_prev)
            if Vn <= 1e-9: return 1e9, qpp
            Rv = ves["R_out"] if qv >= 0 else ves["R_in"]
            return (Cg / Vn ** ves["n"] - HB + ves["zw"]) - H0 - Rv * qv * abs(qv), qpp
        def solve(with_pump):
            # g is strictly decreasing in the vessel outflow: bracket around the last value, then Brent
            w = 0.05
            lo, hi = qv_prev - w, qv_prev + w
            while g(lo, with_pump)[0] < 0: lo -= w; w *= 2
            w = 0.05
            while g(hi, with_pump)[0] > 0: hi += w; w *= 2
            return brentq(lambda q: g(q, with_pump)[0], lo, hi, xtol=1e-12, rtol=1e-12)
        if ves:
            qv = solve(nrv)
            qp = qpump(qv) if nrv else 0.0
            if nrv and qp <= 0.0:
                nrv = False; qp = 0.0; qv = solve(False)
            Vg = Vg + 0.5 * dt * (qv + qv_prev); qv_prev = qv; Vgmax = max(Vgmax, Vg)
        else:
            qv = 0.0
            qp = qpump(0.0) if nrv else 0.0
            if nrv and qp <= 0.0: nrv = False; qp = 0.0
        Hn[0] = CM0 + B[0] * (npump * qp + qv); Qn[0] = npump * qp + qv
        H, Q = Hn, Qn
        np.minimum(Hmin, H, out=Hmin); np.maximum(Hmax, H, out=Hmax)
        if record:
            for k in record: rec[k].append(H[k])
            ts.append((step + 1) * dt)
    return dict(x=x, z=zp, Q0=Q0, Hss=None, Hmin=Hmin, Hmax=Hmax, pmin=Hmin - zp, pmax=Hmax - zp, Vgmax=Vgmax,
                rec={k: np.array(v) for k, v in rec.items()}, t=np.array(ts))
