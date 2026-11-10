"""MS-VP physics: the pump-down of a vacuum chamber, V dp/dt = -S_eff p + Q(t), roughing through the roughing line to
the crossover pressure, then the high-vacuum pump through its port.

- Pump speeds from the pump curves (speed linear in log10 p between the table points, held beyond the ends).
- The roughing line's conductance by Knudsen's formula for air at 20 C (Leybold): C = 135 D^4 p / L +
  12.1 D^3 / L x (1 + 192 D p) / (1 + 237 D p), L/s with D and L in cm and p in mbar (the chamber pressure).
- S_eff = S C / (S + C).
- Gas load Q(t) = Q_L + sum A q1 (t / 1 h)^-alpha, t in hours from the start of roughing, held at its 3-minute value
  before 3 minutes."""
import math
import numpy as np
from scipy.integrate import solve_ivp

P_ATM = 1013.0
T_HOLD = 0.05                      # h

# pump curves: (pressure mbar, speed L/s); roughing pumps for air, turbo pumps for water vapor
ROUGH = {
    "DS-160": [(1e-3, 6.0), (1e-2, 24.0), (1e-1, 38.0), (1.0, 43.0), (1000.0, 44.0)],
    "DS-250": [(1e-3, 9.0), (1e-2, 38.0), (1e-1, 60.0), (1.0, 68.0), (1000.0, 69.0)],
    "DS-400": [(1e-3, 15.0), (1e-2, 60.0), (1e-1, 96.0), (1.0, 109.0), (1000.0, 111.0)],
    "RV-65": [(1e-3, 3.0), (1e-2, 11.0), (1e-1, 16.0), (1.0, 18.0), (1000.0, 18.0)],
}
TURBO = {
    "TMP-700": [(1e-7, 640.0), (1e-3, 640.0), (1e-2, 420.0), (5e-2, 160.0), (2e-1, 40.0)],
    "TMP-1100": [(1e-7, 1010.0), (1e-3, 1010.0), (1e-2, 640.0), (5e-2, 230.0), (2e-1, 55.0)],
    "TMP-1600": [(1e-7, 1480.0), (1e-3, 1480.0), (1e-2, 900.0), (5e-2, 310.0), (2e-1, 70.0)],
    "TMP-400": [(1e-7, 360.0), (1e-3, 360.0), (1e-2, 250.0), (5e-2, 100.0), (2e-1, 28.0)],
}


def curve(table, p):
    lp = math.log10(max(p, 1e-12))
    xs = [math.log10(a) for a, _ in table]
    ys = [b for _, b in table]
    return float(np.interp(lp, xs, ys))


def knudsen(D_cm, L_cm, p):
    return 135 * D_cm ** 4 * p / L_cm + 12.1 * D_cm ** 3 / L_cm * (1 + 192 * D_cm * p) / (1 + 237 * D_cm * p)


def series(S, C):
    return S * C / (S + C)


def gas_load(t_h, QL, surfaces):
    """surfaces: [(area cm2, q1 mbar L/(s cm2) at 1 h, alpha)]."""
    t = max(t_h, T_HOLD)
    return QL + sum(A * q1 * t ** -a for A, q1, a in surfaces)


def pumpdown(V, rough, D_cm, L_cm, turbo, C_hv, p_x, QL, surfaces, p_target=None, t_end_h=6.0, record=False):
    """Integrates the pump-down. Returns the time (min) to p_target, or with record=True the arrays (t s, p mbar)
    and the crossover time (s)."""
    def rhs_r(t, y):
        p = math.exp(y[0])
        S = series(curve(ROUGH[rough], p), knudsen(D_cm, L_cm, p))
        return [(-S * p + gas_load(t / 3600, QL, surfaces)) / (V * p)]

    def rhs_h(t, y):
        p = math.exp(y[0])
        S = series(curve(TURBO[turbo], p), C_hv)
        return [(-S * p + gas_load(t / 3600, QL, surfaces)) / (V * p)]

    def ev_x(t, y):
        return y[0] - math.log(p_x)
    ev_x.terminal = True
    ev_x.direction = -1
    r1 = solve_ivp(rhs_r, (0, t_end_h * 3600), [math.log(P_ATM)], events=ev_x, method="LSODA", rtol=1e-8,
                   atol=1e-10, max_step=5.0, dense_output=True)
    tx = r1.t_events[0][0]
    if p_target is not None and p_target >= p_x:
        raise ValueError("target above crossover")

    def ev_t(t, y):
        return y[0] - math.log(p_target)
    ev_t.terminal = True
    ev_t.direction = -1
    r2 = solve_ivp(rhs_h, (tx, t_end_h * 3600), [math.log(p_x)], events=ev_t if p_target else None, method="LSODA",
                   rtol=1e-8, atol=1e-10, max_step=20.0, dense_output=True)
    if record:
        return r1, r2, tx
    if not len(r2.t_events[0]):
        return None
    return r2.t_events[0][0] / 60
