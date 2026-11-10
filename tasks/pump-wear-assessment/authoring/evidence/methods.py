"""Engine for the evidence studies: each pump's head deficit at 900 m3/h from the records alone, with switches for
the shortcuts and the sound variations. The sealed module is imported only to score."""
import os
import sys
import numpy as np
import pandas as pd
from scipy.optimize import least_squares

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "provenance"))
import pumps as P

DATA = os.path.join(HERE, "..", "..", "environment", "data")
BANK = P.make_bank(7)
UNITS = P.UNITS
TOL = 0.3
T0 = pd.Timestamp("2026-09-21 08:00")
TR = {u: pd.read_csv(os.path.join(DATA, "trends", "%s.csv" % u.lower())) for u in UNITS}
HDR = pd.read_csv(os.path.join(DATA, "trends", "header.csv"))
DAY = np.arange(len(HDR)) / 24.0
CERT = pd.read_csv(os.path.join(DATA, "factory_tests.csv"))
OEM = pd.read_csv(os.path.join(DATA, "oem_type_test_rev_c.csv"))
RIG10 = pd.read_csv(os.path.join(DATA, "p10_rig_test_2026.csv"))
SURVEY = pd.read_csv(os.path.join(DATA, "flow_survey.csv"))
A_S, A_D = np.pi * 0.35 ** 2 / 4, np.pi * 0.25 ** 2 / 4
P10_CATALOGUE = (58.85, 1.0, 12.125)


def quad(Q, H):
    q = np.asarray(Q, float) / 900.0
    return tuple(np.linalg.lstsq(np.c_[np.ones_like(q), -q, -q * q], np.asarray(H, float), rcond=None)[0])


def affinity(c, r):
    """curve at speed ratio (or trim ratio) r: H(Q) = r^2 H0(Q / r)."""
    return c[0] * r * r, c[1] * r, c[2]


def cert_curve(u):
    c = CERT[CERT.pump == u]
    return quad(c.flow_m3h, c.head_m)


def base_curve(u, p3="affinity", p4_trim=True, p6="oem_trim", p10="rig"):
    if u == "P6":
        if p6 == "sister":
            return tuple(np.median([cert_curve(v) for v in ("P1", "P2", "P5", "P7", "P8", "P9")], axis=0))
        c = quad(OEM.flow_m3h, OEM.head_m)
        return affinity(c, 330.0 / 340.0) if p6 == "oem_trim" else c
    if u == "P10":
        if p10 == "catalogue":
            return P10_CATALOGUE
        c = quad(RIG10.flow_m3h, RIG10.head_m)
        return affinity(c, 1480.0 / 1490.0) if p10 == "rig" else c
    c = cert_curve(u)
    if u == "P3" and p3 == "affinity":
        c = affinity(c, 1480.0 / 1450.0)
    if u == "P4" and p4_trim:
        c = affinity(c, 315.0 / 330.0)
    return c


def hnew(c, Q):
    q = np.asarray(Q) / 900.0
    return c[0] - c[1] * q - c[2] * q * q


def vel(Q):
    return ((Q / 3600 / A_D) ** 2 - (Q / 3600 / A_S) ** 2) / (2 * P.G)


def gauge_head(u, dz=True, span=True, zero="split"):
    t = TR[u]
    pdis = t.discharge_kpa.values.astype(float).copy()
    if u == "P2" and span:
        m = (DAY >= P.SPAN_FROM) & (DAY < P.SPAN_TO)
        pdis[m] = pdis[m] * 1.6
    h = (pdis - t.suction_kpa.values) * 1000.0 / (P.RHO * P.G)
    if dz:                                         # from the stopped-pump readings
        off = (t.suction_kpa - t.discharge_kpa).values * 1000.0 / (P.RHO * P.G)
        st = (t.state != "run").values
        if u == P.ZERO_PUMP and zero == "split":   # PT-606 calibrated mid-window: one offset per side
            pre = DAY < P.ZERO_DAY
            return h + np.where(pre, np.median(off[st & pre]), np.median(off[st & ~pre]))
        if u == P.ZERO_PUMP and zero == "post":    # post-trim offset only, applied throughout (sheet-like)
            return h + np.median(off[st & (DAY >= P.ZERO_DAY)])
        return h + float(np.median(off[st]))
    return h + (2.10 if u == "P2" else 0.80)      # the installation sheet


def flow_from(c, k, H, s):
    a, b, cc = k * c[2], k * c[1] * s, H - k * c[0] * s * s
    return np.maximum((-b + np.sqrt(np.maximum(b * b - 4 * a * cc, 0))) / (2 * a), 0) * 900.0


def estimate(p3="affinity", p4_trim=True, p6="oem_trim", p10="rig", survey=True, cal=True, span=True, dz=True,
             velocity=True, speed=True, slope=False, from_day=None, until_day=None, loss="linear", survey_weight=1.0,
             dry="step", zero="split", survey_bore="lined"):
    curves = {u: base_curve(u, p3, p4_trim, p6, p10) for u in UNITS}
    F = HDR.header_flow_m3h.values.astype(float)
    if cal:
        F = np.where(DAY < P.CAL_DAY, F / (1 + P.CAL_ERR), F)
    run = {u: (TR[u].state == "run").values for u in UNITS}
    H = {u: gauge_head(u, dz, span, zero) for u in UNITS}
    S = {u: (np.where(run[u], TR[u].speed_rpm.values / 1480.0, 1.0) if (u == "P9" and speed) else np.ones(len(DAY))) for u in UNITS}
    keep = np.ones(len(DAY), bool)
    if from_day is not None:
        keep &= DAY >= from_day
    if until_day is not None:
        keep &= DAY < until_day
    sv_idx = [int(round((pd.Timestamp(ts) - T0).total_seconds() / 3600)) for ts in SURVEY.timestamp]
    sv_q = SURVEY.flow_m3h.values
    if survey_bore == "lined":                     # meter keyed for the unlined steel bore; the line is lined to 250 mm
        sv_q = sv_q / P.SURVEY_SCALE

    i1 = UNITS.index(P.DRY_PUMP)

    def kfun(x, i, t):
        k = x[2 * i] - (x[2 * i + 1] if slope else 0.0) * (P.T_TEST - t)
        if dry == "step" and i == i1:              # P1: its own ratio before the trip, x[-1]
            k = np.where(np.asarray(t) < P.DRY_DAY, x[-1], k)
        return k

    def flows(x, u):
        i = UNITS.index(u)
        k = kfun(x, i, DAY)
        Q = flow_from(curves[u], k, H[u], S[u])
        if velocity:
            for _ in range(3):
                Q = flow_from(curves[u], k, H[u] + vel(Q), S[u])
        return Q

    def resid(x):
        tot = np.zeros(len(DAY))
        q7 = None
        for u in UNITS:
            Q = flows(x, u)
            if u == "P7":
                q7 = Q
            tot = tot + np.where(run[u], Q, 0.0)
        r = list((tot - F)[keep] / 30.0)
        if survey:
            r += list(survey_weight * (q7[sv_idx] - sv_q) / 5.0)
        return np.array(r)

    x0 = np.r_[np.tile([0.9, 0.00002], len(UNITS)), 0.95]
    sol = least_squares(resid, x0, loss=loss, x_scale=np.r_[np.tile([0.01, 1e-4], len(UNITS)), 0.01], xtol=1e-12, ftol=1e-12, gtol=1e-12)
    est = {u: float((1 - kfun(sol.x, UNITS.index(u), P.T_TEST)) * hnew(curves[u], 900.0)) for u in UNITS}
    return est, sol


def grade(est, tol=None):
    res = P.grade(est, BANK, tol or TOL)
    worst = max(res, key=lambda u: abs(res[u][0]))
    return abs(res[worst][0]), worst, sorted(u for u in res if not res[u][1]), res
