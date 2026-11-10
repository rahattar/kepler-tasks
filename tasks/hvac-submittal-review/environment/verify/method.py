"""The review method an HVAC engineer applies, in the sealed definition: psychrometrics (ASHRAE Handbook of
Fundamentals 2017, Ch. 1, Hyland-Wexler saturation pressure), ventilation by ASHRAE 62.1-2019 (Ventilation Rate
Procedure, multiple-zone recirculating system, Normative Appendix A), coil entering conditions from adiabatic
mixing, and the manufacturer's extended performance tables (gross capacities, entering-dry-bulb correction with
the bypass factor, indoor fan motor heat for a draw-through arrangement). The shipped standard names these methods;
it does not spell them out."""
import math

# ---------------------------------------------------------------- design data (stated in the owner's standard)
P_STATION = 98.9            # kPa, Chicago O'Hare, about 200 m
T_ROOM, RH_ROOM = 24.0, 0.50
T_OA_DESIGN, WB_OA_DESIGN = 33.0, 23.5      # 0.4 % cooling DB / MCWB
T_SUPPLY = 13.0             # zone supply air temperature for scheduled zone airflows
CP_AIR, CL_AIR = 1.23, 3010.0   # standard-air relations, W per (L/s K) and W per (L/s kg/kg)
ESP_PA = 125                # external static pressure on the submittal
MIN_ZONE_AIR = 2.0          # L/s per m2, minimum zone supply airflow (District practice)


# ---------------------------------------------------------------- psychrometrics
def pws(t):
    """Saturation pressure over liquid water, kPa (Hyland-Wexler)."""
    T = t + 273.15
    c8, c9, c10, c11, c12, c13 = -5.8002206e3, 1.3914993, -4.8640239e-2, 4.1764768e-5, -1.4452093e-8, 6.5459673
    return math.exp(c8 / T + c9 + c10 * T + c11 * T * T + c12 * T ** 3 + c13 * math.log(T)) / 1000.0


def w_from_pw(pw, p=P_STATION):
    return 0.621945 * pw / (p - pw)


def w_from_rh(t, rh, p=P_STATION):
    return w_from_pw(rh * pws(t), p)


def w_from_wb(t, wb, p=P_STATION):
    wss = w_from_pw(pws(wb), p)
    return ((2501.0 - 2.326 * wb) * wss - 1.006 * (t - wb)) / (2501.0 + 1.86 * t - 4.186 * wb)


def wb_from_w(t, w, p=P_STATION):
    lo, hi = -10.0, t
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if w_from_wb(t, mid, p) > w: hi = mid
        else: lo = mid
    return 0.5 * (lo + hi)


def enthalpy(t, w):
    return 1.006 * t + w * (2501.0 + 1.86 * t)


def spec_volume(t, w, p=P_STATION):
    return 0.287042 * (t + 273.15) * (1 + 1.607858 * w) / p      # m3 per kg dry air


W_ROOM = w_from_rh(T_ROOM, RH_ROOM)
W_OA = w_from_wb(T_OA_DESIGN, WB_OA_DESIGN)


def mix(v_oa, v_total):
    """Adiabatic mixing of outdoor and return air by dry-air mass; v in L/s. Returns (t, w, wb)."""
    m_oa = v_oa / spec_volume(T_OA_DESIGN, W_OA)
    m_ra = (v_total - v_oa) / spec_volume(T_ROOM, W_ROOM)
    x = m_oa / (m_oa + m_ra)
    w = x * W_OA + (1 - x) * W_ROOM
    h = x * enthalpy(T_OA_DESIGN, W_OA) + (1 - x) * enthalpy(T_ROOM, W_ROOM)
    t = (h - 2501.0 * w) / (1.006 + 1.86 * w)
    return t, w, wb_from_w(t, w)


# ---------------------------------------------------------------- ventilation, ASHRAE 62.1-2019
def ventilation(zones, vps):
    """zones: list of dict(rp, ra, pz, az, vpz). Multiple-zone recirculating system, D = 1, Ez = 1 (ceiling supply
    of cool air), Appendix A: Xs = Vou/Vps, Zpz = Voz/Vpz, Evz = 1 + Xs - Zpz, Ev = min Evz, Vot = Vou/Ev.
    Vps = the unit's scheduled supply airflow; Vpz = each zone's scheduled airflow. Returns (Vot, Vou, Ev, critical index)."""
    vbz = [z["rp"] * z["pz"] + z["ra"] * z["az"] for z in zones]
    vou = sum(vbz)
    xs = vou / vps
    evz = [1 + xs - (v / z["vpz"]) for v, z in zip(vbz, zones)]
    ev = min(evz)
    return vou / ev, vou, ev, evz.index(ev)


# ---------------------------------------------------------------- catalogue: extended performance tables
EWB_COLS = [13.9, 16.7, 19.4, 22.2]          # 57, 62, 67, 72 F
ODB_ROWS = [29.4, 35.0, 40.6, 46.1]          # 85, 95, 105, 115 F
AIR_FRAC = [0.75, 1.00, 1.25]
EDB_RATED = 26.7                              # 80 F
# model: nominal tons, rated airflow L/s, AHRI gross total kW (35 C ODB, 19.4 C EWB, 26.7 C EDB, rated airflow),
# SHR at rated, bypass factor at rated airflow, indoor fan motor heat kW at rated airflow and 125 Pa
MODELS = {
    "RTX-030": (3, 600, 10.5, 0.79, 0.09, 0.49),
    "RTX-035": (3.5, 700, 12.3, 0.79, 0.09, 0.58),
    "RTX-040": (4, 800, 14.0, 0.79, 0.09, 0.66),
    "RTX-045": (4.5, 900, 15.8, 0.79, 0.09, 0.74),
    "RTX-050": (5, 1000, 17.5, 0.79, 0.09, 0.83),
    "RTX-055": (5.5, 1100, 19.3, 0.79, 0.09, 0.91),
    "RTX-060": (6, 1200, 21.0, 0.79, 0.10, 0.99),
    "RTX-070": (7, 1400, 24.5, 0.79, 0.10, 1.16),
    "RTX-080": (8, 1600, 28.0, 0.79, 0.10, 1.32),
    "RTX-090": (9, 1800, 31.5, 0.79, 0.10, 1.49),
    "RTX-100": (10, 2000, 35.0, 0.79, 0.11, 1.65),
    "RTX-110": (11, 2200, 38.5, 0.79, 0.11, 1.82),
    "RTX-125": (12.5, 2500, 43.8, 0.79, 0.11, 2.06),
    "RTX-140": (14, 2800, 49.0, 0.79, 0.11, 2.31),
    "RTX-150": (15, 3000, 52.5, 0.79, 0.11, 2.48),
}


def _gen(model):
    """The manufacturer's tables, rounded as printed: {airflow: dict(bf, fan, tc[odb][ewb], shc[odb][ewb], kw[odb][ewb])}."""
    tons, qr, tcr, shr_r, bfr, fanr = MODELS[model]
    out = {}
    for f in AIR_FRAC:
        q = int(round(qr * f / 5.0) * 5)
        bf = round(bfr * f ** 0.6, 3)
        fan = round(fanr * f ** 2.2, 2)
        tc, shc, kw = {}, {}, {}
        for odb in ODB_ROWS:
            tc[odb], shc[odb], kw[odb] = {}, {}, {}
            for ewb in EWB_COLS:
                t = tcr * (1 + 0.034 * (ewb - 19.4)) * (1 - 0.0092 * (odb - 35.0)) * f ** 0.12
                shr = shr_r - 0.060 * (ewb - 19.4) + 0.22 * (f - 1.0)
                s = min(t * shr, t)
                tc[odb][ewb] = round(t, 1)
                shc[odb][ewb] = round(s, 1)
                kw[odb][ewb] = round(tcr / 3.35 * (1 + 0.012 * (odb - 35.0)) * (1 + 0.004 * (ewb - 19.4)), 2)
        out[q] = dict(bf=bf, fan=fan, tc=tc, shc=shc, kw=kw)
    return out


CATALOG = {m: _gen(m) for m in MODELS}


def _interp1(x, xs, ys):
    if x < xs[0] - 1e-9 or x > xs[-1] + 1e-9:
        raise ValueError("outside the catalogue (no extrapolation): %s not in [%s, %s]" % (x, xs[0], xs[-1]))
    for i in range(len(xs) - 1):
        if xs[i] <= x <= xs[i + 1]:
            r = (x - xs[i]) / (xs[i + 1] - xs[i])
            return ys[i] + r * (ys[i + 1] - ys[i])
    return ys[-1]


def capacity(model, airflow, ewb, edb, odb=T_OA_DESIGN):
    """Gross and net capacities, kW, interpolated linearly in airflow, entering wet bulb and outdoor dry bulb.
    Sensible corrected to the actual entering dry bulb with the bypass factor; sensible capped at total (dry coil);
    net = gross - indoor fan motor heat (draw-through: the motor heat enters the supply air after the coil)."""
    tab = CATALOG[model]; qs = sorted(tab)
    def at_q(q):
        d = tab[q]
        tc = _interp1(odb, ODB_ROWS, [_interp1(ewb, EWB_COLS, [d["tc"][o][e] for e in EWB_COLS]) for o in ODB_ROWS])
        sc = _interp1(odb, ODB_ROWS, [_interp1(ewb, EWB_COLS, [d["shc"][o][e] for e in EWB_COLS]) for o in ODB_ROWS])
        return tc, sc, d["bf"], d["fan"]
    vals = [at_q(q) for q in qs]
    tc = _interp1(airflow, qs, [v[0] for v in vals])
    sc = _interp1(airflow, qs, [v[1] for v in vals])
    bf = _interp1(airflow, qs, [v[2] for v in vals])
    fan = _interp1(airflow, qs, [v[3] for v in vals])
    sc = sc + CP_AIR * (1 - bf) * airflow * (edb - EDB_RATED) / 1000.0
    sc = min(sc, tc)
    return dict(gross_total=tc, gross_sensible=sc, fan=fan, net_total=tc - fan, net_sensible=sc - fan,
                net_latent=tc - sc)


def ahri_rating(model):
    """The rated point the contractor quotes: 35 C ODB, 19.4 C EWB, 26.7 C EDB, rated airflow, gross."""
    tons, qr, *_ = MODELS[model]
    q = int(round(qr / 5.0) * 5)
    d = CATALOG[model][q]
    return d["tc"][35.0][19.4], d["shc"][35.0][19.4], q
