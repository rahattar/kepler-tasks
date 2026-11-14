"""CS-4 closed holding of a nitrogen tank: the prototype of the standard's method."""
import csv, math
import numpy as np
TAB = np.array([[float(x) for x in r] for r in list(csv.reader(open(__file__.replace("cs4.py", "n2_sat.csv"))))[1:]])
T, P, RL, RV, HL, HV = TAB.T
ATM = 1.01325; T_NBP = 77.355
def sat(t):
    return (np.interp(t, T, P), np.interp(t, T, RL), np.interp(t, T, RV), np.interp(t, T, HL), np.interp(t, T, HV))
def t_of_p(p):
    return float(np.interp(p, P, T))
def vent_per_J(t):
    p, rl, rv, hl, hv = sat(t); return (1 - rv / rl) / ((hv - hl) * 1e3)   # kg per J at constant pressure
def ua_from_ner(ner_pct, cap_m3, t_test_C):
    p, rl, rv, hl, hv = sat(T_NBP)
    mdot = ner_pct / 100 * cap_m3 * rl / 86400.0          # kg/s
    q = mdot / vent_per_J(T_NBP)                          # W
    return q / (t_test_C + 273.15 - T_NBP)
def u_mix(t, v):
    p, rl, rv, hl, hv = sat(t); vl, vv = 1 / rl, 1 / rv
    ul, uv = hl - p * 100 * vl, hv - p * 100 * vv
    x = (v - vl) / (vv - vl)
    return ul + x * (uv - ul), x
def state(v, u):
    lo, hi = 77.0, 115.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if u_mix(mid, v)[0] < u: lo = mid
        else: hi = mid
    t = 0.5 * (lo + hi); return t, u_mix(t, v)[1]
def t_full(m, cap):
    """the temperature at which the liquid alone would fill the tank, or None above the table"""
    rho = m / cap
    if rho > RL[0] or rho < RL[-1]: return None
    return float(np.interp(-rho, -RL, T))
def hold(cap, m0, p0, relief, ua, tamb, days):
    t = t_of_p(p0 + ATM); v = cap / m0; u = u_mix(t, v)[0]; m = m0
    tset = t_of_p(relief + ATM); vented = 0.0; st = "closed"; out = []
    for d in range(1, days + 1):
        if st == "full": out.append((d,) + out[-1][1:]); continue
        q = ua * (tamb[d - 1] + 273.15 - t) * 86400.0
        if st == "closed":
            un = u + q / (m * 1e3); tf = t_full(m, cap)
            if tf is not None and tf < tset and un >= u_mix(tf, v)[0]:
                t = tf; st = "full"
            elif un <= u_mix(tset, v)[0]:
                t, x = state(v, un); u = un
            else:
                qr = (un - u_mix(tset, v)[0]) * m * 1e3; t = tset; st = "venting"
                dm = qr * vent_per_J(tset); vented += dm; m -= dm; v = cap / m; u = u_mix(t, v)[0]
        else:
            dm = q * vent_per_J(tset); vented += dm; m -= dm; v = cap / m; u = u_mix(t, v)[0]
        out.append((d, float(sat(t)[0]) - ATM, vented, st))
    return out
