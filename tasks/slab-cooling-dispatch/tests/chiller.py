"""Dedicated air-cooled chiller for the TABS group; its leaving water is the slab supply.

COP falls as the leaving water gets colder and the outdoor air hotter (fraction of Carnot on the
lift between evaporating and condensing temperatures). Capacity grows with leaving temperature and
falls with outdoor temperature. If the open valves ask for more than the capacity, the leaving
temperature floats up until supply meets demand.
"""
import numpy as np

ETA, APPR_E, APPR_C, MIN_LIFT, COP_MAX = 0.40, 4.0, 8.0, 10.0, 8.0
TS_MIN, TS_MAX = 15.0, 22.0
CAP_KW_NOM = 7.2            # at 16 C leaving, 30 C outdoor
CAP_DTS, CAP_DTOUT = 0.03, -0.012
AREA_TOTAL = 240.0


def cop(Ts, Tout):
    Te = np.asarray(Ts, float) - APPR_E
    Tc = np.maximum(np.asarray(Tout, float) + APPR_C, Te + MIN_LIFT)
    return np.minimum(ETA * (Te + 273.15) / (Tc - Te), COP_MAX)


def cap_kw(Ts, Tout):
    return CAP_KW_NOM * (1 + CAP_DTS * (np.asarray(Ts, float) - 16.0)) * (1 + CAP_DTOUT * (np.asarray(Tout, float) - 30.0))


def cap_w_per_zone_m2(Ts, Tout, area=120.0):
    """Capacity expressed in the sum of per-m2 zone heat flows (each zone 120 m2)."""
    return cap_kw(Ts, Tout) * 1000.0 / area


def leaving_temp(setpoint, Tout, opens, G, Tp, area=120.0):
    """Actual leaving temperature for this sub-step given open valves (bools), pipe conductances G
    (W/m2 K per zone) and pipe-plane temperatures Tp."""
    Ts = float(np.clip(setpoint, TS_MIN, TS_MAX))
    gs = sum(g for o, g in zip(opens, G) if o)
    if gs == 0:
        return Ts
    demand = sum(g * max(t - Ts, 0.0) for o, g, t in zip(opens, G, Tp) if o)
    cap = cap_w_per_zone_m2(Ts, Tout, area)
    if demand <= cap:
        return Ts
    # cap(Ts) = a + b Ts in W per zone-m2 sum; solve sum g (Tp - Ts) = a + b Ts
    k = CAP_KW_NOM * 1000.0 / area * (1 + CAP_DTOUT * (Tout - 30.0))
    a = k * (1 - CAP_DTS * 16.0); b = k * CAP_DTS
    gt = sum(g * t for o, g, t in zip(opens, G, Tp) if o)
    return float((gt - a) / (gs + b))
