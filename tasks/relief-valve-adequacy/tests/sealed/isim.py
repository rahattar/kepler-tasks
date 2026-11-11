"""Sealed definition for relief-valve-adequacy.

The truth for unit 400's nine pressure relief valves: for each one the governing contingency, the required effective
orifice area and whether the installed valve is adequate under plant standard RP-7. The agent never reads this file;
the generator writes the unit's records from it and the verifier grades against it.

Everything the records show is derived here. Where a record is an observation rather than a fact (a metered flow, a
logged travel, a tested head) the generator adds the scatter the instrument schedule states; the truth below is
computed from the parameters, not from the records.
"""
import math

# ----------------------------------------------------------------------------- grading
TOL = 0.01          # relative tolerance on required_area_mm2
CASES = ("fire", "blocked_outlet", "control_valve_failure", "cooling_failure", "tube_rupture", "thermal_expansion")
VERDICTS = ("adequate", "inadequate")

# ----------------------------------------------------------------------------- constants of the standard
ATM = 1.013         # bar
RGAS = 8314.0       # J/(kmol K)
KD_VAP = 0.975
KD_LIQ = 0.65
KC_DISC = 0.90
CD_TUBE = 0.62      # orifice coefficient, ruptured tube
TWO_THIRDS = 0.70   # low-side/high-side design pressure at or above which tube rupture need not be considered
FIRE_C = 43.2       # kW, m2; adequate drainage and prompt firefighting
FIRE_H = 7.6        # m above grade
FIRE_EXP = 0.82
F_DARCY = 0.018
INLET_LIMIT = 0.03  # of set pressure
CONV_BP_LIMIT = 0.10  # of set pressure, conventional valves
SOLAR = 0.80        # kW/m2 of projected area
OVER_FIRE = 0.21
OVER_OTHER = 0.10
SIL_MIN = 2
PROOF_MAX = 18      # months
K_FIT = {"elbow90": 0.30, "tee_run": 0.20, "ball": 0.10, "entrance": 0.50}

ORIFICE = {"D": 71.0, "E": 126.0, "F": 198.0, "G": 325.0, "H": 506.0, "J": 830.0,
           "K": 1186.0, "L": 1841.0, "M": 2323.0, "N": 2800.0, "P": 4116.0}

# back-pressure correction, balanced bellows: back pressure over relieving pressure (vapour) or over set
# pressure (liquid). Below the first ratio the factor is 1.
KB_TABLE = [(0.30, 1.00), (0.35, 0.99), (0.40, 0.97), (0.45, 0.95), (0.50, 0.93)]
KW_TABLE = [(0.10, 1.00), (0.15, 0.99), (0.20, 0.97), (0.25, 0.95), (0.30, 0.93), (0.40, 0.88)]

# ----------------------------------------------------------------------------- fluid properties
# saturated streams: p_bara, sat_temp_C, latent_kJ/kg, vapour mw, k, z, liquid density, liquid viscosity cP
SAT = {
    "sep_liquid": [
        (30.0, 55.0, 245.0, 40.0, 1.17, 0.83, 505.0, 0.26),
        (50.0, 88.0, 205.0, 40.0, 1.16, 0.76, 465.0, 0.21),
        (64.0, 105.0, 178.0, 40.0, 1.15, 0.72, 436.0, 0.19),
        (78.0, 119.0, 152.0, 40.0, 1.15, 0.69, 408.0, 0.17),
    ],
    "c2_overhead": [
        (24.0, -7.0, 292.0, 31.0, 1.19, 0.81, 402.0, 0.09),
        (30.0, 2.0, 266.0, 31.0, 1.20, 0.77, 383.0, 0.08),
        (36.0, 10.0, 238.0, 31.0, 1.21, 0.74, 362.0, 0.08),
        (42.0, 18.0, 208.0, 31.0, 1.22, 0.70, 339.0, 0.07),
    ],
    "c3_product": [
        (10.0, 27.0, 325.0, 44.0, 1.13, 0.82, 480.0, 0.10),
        (14.0, 40.0, 304.0, 44.0, 1.14, 0.79, 461.0, 0.09),
        (18.0, 51.0, 283.0, 44.0, 1.15, 0.76, 442.0, 0.09),
        (22.0, 61.0, 261.0, 44.0, 1.16, 0.73, 421.0, 0.08),
        (26.0, 70.0, 239.0, 44.0, 1.17, 0.70, 399.0, 0.08),
        (32.0, 78.0, 212.0, 44.0, 1.18, 0.66, 372.0, 0.07),
    ],
    "c4_product": [
        (6.0, 58.0, 320.0, 58.0, 1.08, 0.88, 521.0, 0.14),
        (10.0, 79.0, 295.0, 58.0, 1.09, 0.85, 501.0, 0.13),
        (14.0, 95.0, 272.0, 58.0, 1.10, 0.82, 481.0, 0.12),
        (18.0, 108.0, 252.0, 58.0, 1.11, 0.79, 462.0, 0.11),
        (22.0, 119.0, 233.0, 58.0, 1.12, 0.76, 444.0, 0.10),
        (26.0, 128.0, 214.0, 58.0, 1.13, 0.73, 426.0, 0.09),
    ],
    "bottoms_product": [
        (16.0, 203.0, 272.0, 86.0, 1.05, 0.86, 620.0, 0.95),
        (20.0, 215.0, 260.0, 86.0, 1.05, 0.85, 610.0, 0.90),
        (25.0, 232.0, 243.0, 86.0, 1.06, 0.83, 596.0, 0.85),
        (30.0, 245.0, 228.0, 86.0, 1.06, 0.82, 585.0, 0.80),
    ],
    "steam": [
        (11.0, 184.0, 2000.0, 18.0, 1.30, 0.95, 884.0, 0.15),
        (14.0, 195.0, 1958.0, 18.0, 1.30, 0.94, 871.0, 0.14),
        (17.0, 204.0, 1922.0, 18.0, 1.30, 0.93, 859.0, 0.14),
        (22.0, 217.0, 1868.0, 18.0, 1.30, 0.92, 840.0, 0.13),
        (26.0, 226.0, 1826.0, 18.0, 1.30, 0.91, 824.0, 0.13),
    ],
}

# non-condensing gas: p_bara, k, z. The molar mass comes from the current feed analysis.
GAS = {"feed_gas": [(10.0, 1.26, 0.97), (40.0, 1.26, 0.90), (55.0, 1.27, 0.87),
                    (70.0, 1.28, 0.84), (80.0, 1.29, 0.82)]}

# subcooled liquids: temperature_C, density, viscosity cP, cubical expansion 1/C, specific heat kJ/kgK
LIQ = {
    "bottoms_product": [(60.0, 672.0, 2.9, 0.00086, 2.12), (95.0, 648.0, 1.8, 0.00092, 2.26),
                        (130.0, 622.0, 1.2, 0.00099, 2.41)],
    "feed_liquid": [(30.0, 512.0, 0.28, 0.00142, 2.48), (60.0, 481.0, 0.22, 0.00158, 2.63)],
    "c3_liquid": [(20.0, 500.0, 0.11, 0.00301, 2.52), (50.0, 445.0, 0.09, 0.00372, 2.78)],
}

# ----------------------------------------------------------------------------- the unit as it stands
FEED_DESIGN = 310.0     # t/d, the 2019 relief study basis
FEED_NOW = 366.0        # t/d, what the unit actually runs
RD_CONFIG = 0.780       # relative density configured in the FE-4011 flow computer at commissioning
MW_AIR = 28.96

# the feed analyses the laboratory reports, mol fraction. The gas has got richer since commissioning; the current
# molar mass follows from the latest one, and the flow computer still holds RD_CONFIG.
COMP_M = {"n2": 28.01, "co2": 44.01, "c1": 16.04, "c2": 30.07, "c3": 44.10,
          "ic4": 58.12, "nc4": 58.12, "c5plus": 72.15}
COMP_FIRST = dict(n2=0.012, co2=0.008, c1=0.749, c2=0.105, c3=0.065, ic4=0.020, nc4=0.020, c5plus=0.021)
COMP_LAST = dict(n2=0.012, co2=0.008, c1=0.703, c2=0.112, c3=0.075, ic4=0.026, nc4=0.026, c5plus=0.038)


def comp_mw(comp):
    return sum(comp[k] * COMP_M[k] for k in COMP_M)


RD_NOW = comp_mw(COMP_LAST) / MW_AIR   # current feed relative density
METER_BIAS = "FE-4011"  # the one meter whose indication moves with the density its flow computer holds

# control valves: data sheet Cv, the Cv the valve actually has at full travel, rangeability, xT, Fp, and the
# conditions the unit runs them at
CV = {
    "PV-4001": dict(sheet=64.0, actual=55.0, r=50.0, xt=0.70, fp=1.00, stream="feed_gas",
                    p_up=73.0, p_dn=59.0, t_up=38.0, travel=0.72, meter="FE-4011"),
    "PV-4021": dict(sheet=2.50, actual=3.08, r=50.0, xt=0.66, fp=1.00, stream="feed_gas",
                    p_up=59.0, p_dn=9.0, t_up=38.0, travel=0.69, meter="FE-4021"),
    "PV-4031": dict(sheet=48.0, actual=48.0, r=50.0, xt=0.68, fp=1.00, stream="c2_overhead",
                    p_up=29.4, p_dn=28.2, t_up=1.0, travel=0.55, meter="FE-4031"),
    "PV-4061": dict(sheet=36.0, actual=36.0, r=50.0, xt=0.72, fp=1.00, stream="c4_product",
                    p_up=11.4, p_dn=10.2, t_up=80.0, travel=0.62, meter="FE-4061"),
    "PV-4071": dict(sheet=27.0, actual=37.8, r=50.0, xt=0.70, fp=1.00, stream="c3_product",
                    p_up=27.0, p_dn=17.0, t_up=70.0, travel=0.64, meter="FE-4071"),
}

# reboilers: steam supply barg, the duty on the 2019 data sheet at FEED_DESIGN, the bottoms temperature the
# operating record shows
REB = {
    "E-403": dict(tower="T-401", steam_barg=13.0, design_kw=2650.0, bot_normal_C=78.0),
    "E-406": dict(tower="T-402", steam_barg=13.0, design_kw=4200.0, bot_normal_C=79.0),
}

# P-401, bottoms product pump
PUMP = dict(sheet_shutoff_m=590.0, worn_shutoff_m=545.0, rated_m3h=96.0, rated_head_m=505.0,
            suction_barg=9.5, temp_C=95.0)


def pump_b():
    """The shape of the pump's head curve, h(q) = h0 * (1 - b q^2), from the data sheet."""
    return (1.0 - PUMP["rated_head_m"] / PUMP["sheet_shutoff_m"]) / PUMP["rated_m3h"] ** 2


def pump_head(shutoff_m, q_m3h):
    return shutoff_m * (1.0 - pump_b() * q_m3h * q_m3h)

# instrumented functions that would prevent a contingency
SIF = {
    "SIF-4011": dict(sil=1, proof=12, initiator="PT-4012", prevents=("PSV-401", "blocked_outlet")),
    "SIF-4031": dict(sil=2, proof=12, initiator="PT-4031", prevents=("PSV-403", "cooling_failure")),
    "SIF-4061": dict(sil=3, proof=12, initiator="PT-4063", prevents=("PSV-406", "cooling_failure")),
    "SIF-4091": dict(sil=2, proof=24, initiator="PT-4022", prevents=("PSV-409", "control_valve_failure")),
}
# the measurement each regulatory control uses: a contingency caused by that control failing is not independent
# of a function that initiates on the same element
CONTROL_TAG = {
    ("PSV-401", "blocked_outlet"): (),
    ("PSV-403", "cooling_failure"): ("PT-4031",),
    ("PSV-406", "cooling_failure"): ("PT-4061",),
    ("PSV-409", "control_valve_failure"): ("PT-4021",),
}

# vessels, for the fire case
VESSEL = {
    "V-401": dict(shape="vertical", d=2.4, tt=7.0, bottom_m=1.50, level_m=1.10, heads=2,
                  insul=dict(k=0.062, t=0.060, fire_rated=False), stream="sep_liquid"),
    "V-402": dict(shape="horizontal", d=1.6, tt=4.2, bottom_m=1.00, level_m=0.70, heads=2,
                  insul=None, stream="c3_product"),
    "V-403": dict(shape="horizontal", d=2.0, tt=5.5, bottom_m=6.60, level_m=0.85, heads=2,
                  insul=dict(k=0.055, t=0.075, fire_rated=True), stream="c2_overhead"),
    "V-404": dict(shape="horizontal", d=2.2, tt=6.5, bottom_m=2.00, level_m=0.95, heads=2,
                  insul=None, stream="c4_product"),
    "V-405": dict(shape="horizontal", d=2.4, tt=10.0, bottom_m=1.20, level_m=1.45, heads=2,
                  insul=None, stream="c3_product"),
    "T-401": dict(shape="column", d=1.8, tt=24.0, bottom_m=1.80, level_m=2.60, heads=2,
                  insul=dict(k=0.055, t=0.075, fire_rated=True), stream="c3_product",
                  trays=dict(first_m=5.60, spacing=0.60, n=28, liquid_band=0.090)),
    "T-402": dict(shape="column", d=3.2, tt=21.0, bottom_m=3.60, level_m=3.60, heads=2,
                  insul=None, stream="c4_product",
                  trays=dict(first_m=5.80, spacing=0.65, n=24, liquid_band=0.105)),
    "E-402": dict(shape="horizontal", d=0.9, tt=6.0, bottom_m=1.00, level_m=0.90, heads=2,
                  insul=None, stream="bottoms_product"),
}
T402_RAISED = 0.90   # the 2024 modification re-set T-402 this much higher on an extended skirt

# the one shell-and-tube exchanger whose shell has its own relief
EXCH = {
    "E-402": dict(tube_id_mm=15.7, tubes=168, hi_barg=55.0, hi_stream="feed_liquid", hi_temp_C=30.0,
                  shell_mawp=20.0),
}

# the nine valves
ITEMS = {
    "PSV-401": dict(item="V-401", p_norm=58.0, mawp=62.0, set_reg=62.0, set_now=62.0,
                    orifice_reg="J", orifice_now="J", kind="bellows", disc=False, backp=1.10,
                    fluid="feed_gas", t_relief_C=38.0, liquid=False,
                    cases=("blocked_outlet", "control_valve_failure", "fire"),
                    inlet_kgh=15250.0, inlet_tag="FE-4011", cv="PV-4001", source_barg=72.0,
                    inlet=dict(id_mm=97.2, length_m=3.5, elbow90=2, tee_run=0, ball=1, entrance=1)),
    "PSV-402": dict(item="E-402", p_norm=14.0, mawp=20.0, set_reg=20.0, set_now=20.0,
                    orifice_reg="G", orifice_now="G", kind="conventional", disc=True, backp=1.20,
                    fluid="bottoms_product", liquid=True,
                    cases=("tube_rupture", "fire", "thermal_expansion"),
                    thermal=dict(area_m2=12.0, stream="bottoms_product", temp_C=95.0),
                    inlet=dict(id_mm=73.7, length_m=2.4, elbow90=1, tee_run=0, ball=1, entrance=1)),
    "PSV-403": dict(item="T-401", p_norm=28.0, mawp=31.0, set_reg=31.0, set_now=31.0,
                    orifice_reg="K", orifice_now="K", kind="bellows", disc=False, backp=1.10,
                    fluid="c2_overhead", liquid=False,
                    cases=("cooling_failure", "fire", "blocked_outlet"),
                    inlet_kgh=15250.0, inlet_tag="FE-4011", reb="E-403", bot_stream="c3_product",
                    inlet=dict(id_mm=97.2, length_m=5.2, elbow90=2, tee_run=1, ball=1, entrance=1)),
    "PSV-404": dict(item="V-403", p_norm=27.0, mawp=29.0, set_reg=29.0, set_now=29.0,
                    orifice_reg="H", orifice_2019="G", orifice_now="H", kind="bellows", disc=False, backp=1.10,
                    fluid="c2_overhead", liquid=False,
                    cases=("blocked_outlet", "fire"),
                    inlet_kgh=6380.0, inlet_tag="FE-4033+FE-4034",
                    inlet=dict(id_mm=52.5, length_m=5.0, elbow90=3, tee_run=0, ball=1, entrance=1)),
    "PSV-405": dict(item="P-401", p_norm=32.0, mawp=42.0, set_reg=42.0, set_now=42.0,
                    orifice_reg="F", orifice_now="F", kind="conventional", disc=False, backp=0.00,
                    fluid="bottoms_product", liquid=True,
                    cases=("blocked_outlet", "thermal_expansion"), pump=True,
                    thermal=dict(area_m2=7.6, stream="bottoms_product", temp_C=95.0),
                    inlet=dict(id_mm=42.9, length_m=1.8, elbow90=1, tee_run=0, ball=1, entrance=1)),
    "PSV-406": dict(item="T-402", p_norm=10.0, mawp=16.0, set_reg=16.0, set_now=16.0,
                    orifice_reg="J", orifice_now="J", kind="conventional", disc=False, backp=1.40,
                    fluid="c4_product", liquid=False,
                    cases=("cooling_failure", "fire", "blocked_outlet"),
                    inlet_kgh=11550.0, inlet_tag="FE-4035", reb="E-406", bot_stream="c4_product",
                    inlet=dict(id_mm=146.3, length_m=4.6, elbow90=2, tee_run=0, ball=1, entrance=1)),
    "PSV-407": dict(item="V-405", p_norm=16.0, mawp=19.0, set_reg=19.0, set_now=19.0,
                    orifice_reg="J", orifice_now="H", kind="bellows", disc=False, backp=1.10,
                    fluid="c3_product", liquid=False,
                    cases=("fire", "control_valve_failure", "thermal_expansion"),
                    cv="PV-4071", source_barg=26.0,
                    thermal=dict(area_m2=14.0, stream="c3_liquid", temp_C=35.0),
                    inlet=dict(id_mm=122.3, length_m=3.0, elbow90=2, tee_run=0, ball=1, entrance=1)),
    "PSV-408": dict(item="V-404", p_norm=10.0, mawp=18.0, set_reg=18.0, set_now=18.0,
                    orifice_reg="H", orifice_now="H", kind="conventional", disc=False, backp=1.20,
                    fluid="c4_product", liquid=False,
                    cases=("blocked_outlet", "fire", "control_valve_failure"),
                    inlet_kgh=9490.0, inlet_tag="FE-4036+FE-4037", cv="PV-4061", source_barg=16.0,
                    inlet=dict(id_mm=73.7, length_m=2.8, elbow90=1, tee_run=0, ball=1, entrance=1)),
    "PSV-409": dict(item="V-402", p_norm=8.0, mawp=11.0, set_reg=11.0, set_now=9.5,
                    orifice_reg="G", orifice_now="G", kind="bellows", disc=False, backp=1.10,
                    fluid="feed_gas", t_relief_C=38.0, liquid=False,
                    cases=("control_valve_failure", "blocked_outlet", "fire"),
                    inlet_kgh=800.0, inlet_tag="FE-4021", cv="PV-4021", source_barg=62.0,
                    inlet=dict(id_mm=40.9, length_m=7.0, elbow90=4, tee_run=0, ball=1, entrance=1)),
}
IDS = tuple(sorted(ITEMS))


# ----------------------------------------------------------------------------- property lookups
def _interp(rows, x, col):
    """Linear interpolation on the first column, flat outside the table."""
    if x <= rows[0][0]:
        return rows[0][col]
    if x >= rows[-1][0]:
        return rows[-1][col]
    for a, b in zip(rows, rows[1:]):
        if a[0] <= x <= b[0]:
            f = (x - a[0]) / (b[0] - a[0])
            return a[col] + f * (b[col] - a[col])
    raise ValueError("off table")


def sat(stream, p_bara, what):
    return _interp(SAT[stream], p_bara, {"t": 1, "latent": 2, "mw": 3, "k": 4, "z": 5, "rho_l": 6, "visc": 7}[what])


def gas(stream, p_bara, what):
    return _interp(GAS[stream], p_bara, {"k": 1, "z": 2}[what])


def liq(stream, t_C, what):
    return _interp(LIQ[stream], t_C, {"rho": 1, "visc": 2, "exp": 3, "cp": 4}[what])


def feed_mw():
    return comp_mw(COMP_LAST)


# ----------------------------------------------------------------------------- sizing
def c_factor(k):
    return 0.03948 * math.sqrt(k * (2.0 / (k + 1.0)) ** ((k + 1.0) / (k - 1.0)))


def kb(ratio):
    return _interp([(a, 0, b) for a, b in KB_TABLE], ratio, 2) if ratio > KB_TABLE[0][0] else 1.0


def kw(ratio):
    return _interp([(a, 0, b) for a, b in KW_TABLE], ratio, 2) if ratio > KW_TABLE[0][0] else 1.0


def relieving(set_barg, case):
    """Relieving pressure, bar absolute."""
    return set_barg * (1.0 + (OVER_FIRE if case == "fire" else OVER_OTHER)) + ATM


def area_vapour(w_kgh, p1_bara, t_K, mw, k, z, kd=KD_VAP, kb_=1.0, kc=1.0):
    """Critical vapour flow, mm2."""
    return w_kgh / (c_factor(k) * kd * kb_ * kc * p1_bara * 100.0) * math.sqrt(t_K * z / mw)


def cap_vapour(area_mm2, p1_bara, t_K, mw, k, z, kd=KD_VAP, kb_=1.0, kc=1.0):
    """The mass flow an effective area passes at those conditions, kg/h."""
    return area_mm2 * c_factor(k) * kd * kb_ * kc * p1_bara * 100.0 / math.sqrt(t_K * z / mw)


def area_liquid(q_lmin, sg, p1_barg, pb_barg, kd=KD_LIQ, kw_=1.0, kc=1.0, kv=1.0):
    """Certified liquid flow, mm2."""
    return 11.78 * q_lmin * math.sqrt(sg / ((p1_barg - pb_barg) * 100.0)) / (kd * kw_ * kc * kv)


def kv_visc(area_mm2, q_lmin, rho, visc_cp):
    """Viscosity correction: the Reynolds number at the required area, then the standard's factor."""
    if area_mm2 <= 0.0:
        return 1.0
    re = 2800.0 * q_lmin * (rho / 1000.0) / (visc_cp * math.sqrt(area_mm2))
    if re >= 1.0e5:
        return 1.0
    return 1.0 / (0.9935 + 2.878 / re ** 0.5 + 342.75 / re ** 1.5) ** (1.0 / 1.5)


def area_liquid_visc(q_lmin, rho, visc_cp, p1_barg, pb_barg, kd=KD_LIQ, kw_=1.0, kc=1.0):
    """The liquid area with the viscosity correction, which depends on the area and so is iterated."""
    a = area_liquid(q_lmin, rho / 1000.0, p1_barg, pb_barg, kd, kw_, kc, 1.0)
    for _ in range(60):
        new = area_liquid(q_lmin, rho / 1000.0, p1_barg, pb_barg, kd, kw_, kc,
                          kv_visc(a, q_lmin, rho, visc_cp))
        if abs(new - a) < 1.0e-12:
            return new
        a = new
    return a


def valve_flow(kv_coef, xt, fp, k, p_up_bara, p_dn_bara, rho_up):
    """Mass flow through a control valve, kg/h."""
    if p_up_bara <= p_dn_bara:
        return 0.0
    xc = (k / 1.40) * xt
    x = min((p_up_bara - p_dn_bara) / p_up_bara, xc)
    return 3.16 * kv_coef * fp * (1.0 - x / (3.0 * xc)) * math.sqrt(x * p_up_bara * 100.0 * rho_up)


def gas_density(p_bara, t_K, mw, z):
    return p_bara * 1.0e5 * mw / (z * RGAS * t_K)


def cv_at_travel(cv_rated, r, travel):
    """Equal-percentage characteristic."""
    return cv_rated * r ** (travel - 1.0)


# ----------------------------------------------------------------------------- fire exposure
def raised_now(item):
    return T402_RAISED if item == "T-402" else 0.0


def _chord_fraction(d, level):
    """Fraction of a horizontal cylinder's circumference below a liquid level."""
    r = d / 2.0
    h = min(max(level, 0.0), d)
    return math.acos((r - h) / r) / math.pi


def wetted_area(item, raised=None):
    v = VESSEL[item]
    if raised is None:
        raised = raised_now(item)
    d, cut = v["d"], FIRE_H
    head = 1.084 * d * d
    bottom = v["bottom_m"] + raised
    if v["shape"] == "vertical":
        h = max(0.0, min(bottom + v["level_m"], cut) - bottom)
        return math.pi * d * h + (head if bottom < cut else 0.0)
    if v["shape"] == "horizontal":
        lv = min(v["level_m"], max(0.0, cut - bottom))
        if lv <= 0.0:
            return 0.0
        frac = _chord_fraction(d, lv)
        return math.pi * d * v["tt"] * frac + v["heads"] * head * frac
    # a column: the shell wetted by the bottoms liquid, plus a band at each tray below the cut
    a = 0.0
    top = min(bottom + v["level_m"], cut)
    if top > bottom:
        a += math.pi * d * (top - bottom) + head
    t = v["trays"]
    for i in range(t["n"]):
        if t["first_m"] + raised + i * t["spacing"] <= cut:
            a += math.pi * d * t["liquid_band"]
    return a


def f_insulated(ins, t_relief_C):
    return (ins["k"] / ins["t"]) * (904.0 - t_relief_C) / 21000.0


# ----------------------------------------------------------------------------- contingency rates
def indicated(tag, true_kgh):
    """What a meter shows: the one orifice meter moves with the density its flow computer holds."""
    return true_kgh * math.sqrt(RD_CONFIG / RD_NOW) if tag == METER_BIAS else true_kgh


def rate_blocked(vid):
    """The total normal inlet flow, which continues with the outlets isolated."""
    return ITEMS[vid].get("inlet_kgh")


def rate_pump(vid, shutoff_m):
    """The flow a centrifugal pump delivers at the relieving pressure, L/min; None if it cannot reach it."""
    it = ITEMS[vid]
    p1 = relieving(it["set_now"], "blocked_outlet")
    rho = liq("bottoms_product", PUMP["temp_C"], "rho")
    h_req = (p1 - (PUMP["suction_barg"] + ATM)) * 1.0e5 / (rho * 9.81)
    if h_req >= shutoff_m:
        return None
    return math.sqrt((1.0 - h_req / shutoff_m) / pump_b()) * 1000.0 / 60.0


def rate_cv_failure(vid, cv_rated):
    """The flow through a fully open control valve into the item at its relieving pressure."""
    it = ITEMS[vid]
    c = CV[it["cv"]]
    p1 = relieving(it["set_now"], "control_valve_failure")
    p_up = it["source_barg"] + ATM
    st = c["stream"]
    if st == "feed_gas":
        mw, k, z, t_up = feed_mw(), gas(st, p_up, "k"), gas(st, p_up, "z"), c["t_up"] + 273.15
    else:
        mw, k, z = sat(st, p_up, "mw"), sat(st, p_up, "k"), sat(st, p_up, "z")
        t_up = sat(st, p_up, "t") + 273.15
    return valve_flow(cv_rated / 1.156, c["xt"], c["fp"], k, p_up, p1, gas_density(p_up, t_up, mw, z))


def reb_ua(name):
    """The coefficient-area the unit has now: the data sheet duty scaled to the throughput it runs at, over the
    temperature difference the record shows. The data sheet duty is at the 2019 design feed."""
    r = REB[name]
    return r["design_kw"] * (FEED_NOW / FEED_DESIGN) / (
        sat("steam", r["steam_barg"] + ATM, "t") - r["bot_normal_C"])


def rate_cooling(vid, ua):
    """Total loss of overhead cooling: the vapour the reboiler makes at the relieving temperature."""
    it = ITEMS[vid]
    r = REB[it["reb"]]
    p1 = relieving(it["set_now"], "cooling_failure")
    q = ua * max(0.0, sat("steam", r["steam_barg"] + ATM, "t") - sat(it["bot_stream"], p1, "t"))
    return 3600.0 * q / sat(it["fluid"], p1, "latent")


def rate_tube_rupture(vid):
    """One tube severed, both ends flowing into the low-pressure side, kg/h."""
    it = ITEMS[vid]
    e = EXCH[it["item"]]
    if (e["shell_mawp"] / e["hi_barg"]) >= TWO_THIRDS or e["hi_stream"] not in LIQ:
        return None
    p1 = relieving(it["set_now"], "tube_rupture")
    a_t = math.pi / 4.0 * (e["tube_id_mm"] / 1000.0) ** 2
    dp = max(0.0, (e["hi_barg"] + ATM) - p1) * 1.0e5
    return 3600.0 * 2.0 * CD_TUBE * a_t * math.sqrt(2.0 * liq(e["hi_stream"], e["hi_temp_C"], "rho") * dp)


def rate_thermal(vid):
    """Blocked-in liquid taking heat: the volumetric rate of expansion, L/min."""
    th = ITEMS[vid]["thermal"]
    return 3600.0 * liq(th["stream"], th["temp_C"], "exp") * SOLAR * th["area_m2"] / (
        liq(th["stream"], th["temp_C"], "rho") * liq(th["stream"], th["temp_C"], "cp")) * 1000.0 / 60.0


def rate_fire(vid, raised=None):
    """Vapour generated by an external fire, kg/h."""
    it = ITEMS[vid]
    v = VESSEL[it["item"]]
    stream = v["stream"]
    p1 = relieving(it["set_now"], "fire")
    ins = v.get("insul")
    f = f_insulated(ins, sat(stream, p1, "t")) if (ins and ins["fire_rated"]) else 1.0
    a_w = wetted_area(it["item"], raised)
    if a_w <= 0.0:
        return 0.0
    return 3600.0 * FIRE_C * f * a_w ** FIRE_EXP / sat(stream, p1, "latent")


# ----------------------------------------------------------------------------- credit for instrumented protection
def credited(vid, case):
    for s in SIF.values():
        if s["prevents"] != (vid, case):
            continue
        if s["sil"] < SIL_MIN or s["proof"] > PROOF_MAX:
            return False
        return s["initiator"] not in CONTROL_TAG.get((vid, case), ())
    return False


# ----------------------------------------------------------------------------- area per case
def _vapour_at(it, p1):
    """The relieving vapour's properties at the relieving pressure."""
    f = it["fluid"]
    if f == "feed_gas":
        return feed_mw(), gas(f, p1, "k"), gas(f, p1, "z"), it["t_relief_C"] + 273.15
    return sat(f, p1, "mw"), sat(f, p1, "k"), sat(f, p1, "z"), sat(f, p1, "t") + 273.15


def case_area(vid, case, cv_rated=None, ua=None, raised=None, shutoff=None):
    """The required effective orifice area for one contingency, mm2, or None where the case cannot occur."""
    it = ITEMS[vid]
    if credited(vid, case):
        return None
    p1 = relieving(it["set_now"], case)
    kc = KC_DISC if it["disc"] else 1.0
    bellows = it["kind"] == "bellows"
    kw_ = kw(it["backp"] / it["set_now"]) if bellows else 1.0

    if case == "thermal_expansion":
        th = it["thermal"]
        return area_liquid_visc(rate_thermal(vid), liq(th["stream"], th["temp_C"], "rho"),
                                liq(th["stream"], th["temp_C"], "visc"), p1 - ATM, it["backp"], KD_LIQ, kw_, kc)

    if case == "blocked_outlet" and it.get("pump"):
        q = rate_pump(vid, PUMP["worn_shutoff_m"] if shutoff is None else shutoff)
        if q is None:
            return None
        return area_liquid_visc(q, liq("bottoms_product", PUMP["temp_C"], "rho"),
                                liq("bottoms_product", PUMP["temp_C"], "visc"),
                                p1 - ATM, it["backp"], KD_LIQ, kw_, kc)

    if case == "tube_rupture":
        w = rate_tube_rupture(vid)
        if w is None:
            return None
        e = EXCH[it["item"]]
        rho = liq(e["hi_stream"], e["hi_temp_C"], "rho")
        return area_liquid_visc(w / rho * 1000.0 / 60.0, rho, liq(e["hi_stream"], e["hi_temp_C"], "visc"),
                                p1 - ATM, it["backp"], KD_LIQ, kw_, kc)

    if case == "fire":
        w = rate_fire(vid, raised)
        stream = VESSEL[it["item"]]["stream"]
        mw, k, z = sat(stream, p1, "mw"), sat(stream, p1, "k"), sat(stream, p1, "z")
        t_K = sat(stream, p1, "t") + 273.15
    elif case == "blocked_outlet":
        w = rate_blocked(vid)
        mw, k, z, t_K = _vapour_at(it, p1)
    elif case == "control_valve_failure":
        w = rate_cv_failure(vid, CV[it["cv"]]["actual"] if cv_rated is None else cv_rated)
        mw, k, z, t_K = _vapour_at(it, p1)
    elif case == "cooling_failure":
        w = rate_cooling(vid, reb_ua(it["reb"]) if ua is None else ua)
        mw, k, z, t_K = _vapour_at(it, p1)
    else:
        raise ValueError(case)
    if w is None or w <= 0.0:
        return None
    return area_vapour(w, p1, t_K, mw, k, z, KD_VAP, kb(it["backp"] / p1) if bellows else 1.0, kc)


# ----------------------------------------------------------------------------- the installed valve
def governing(vid, cv_rated=None, ua=None, raised=None, shutoff=None):
    """The contingency that needs the largest area, and that area."""
    best, best_a = None, -1.0
    for c in ITEMS[vid]["cases"]:
        a = case_area(vid, c, cv_rated, ua, raised, shutoff)
        if a is not None and a > best_a:
            best, best_a = c, a
    return best, best_a


def inlet_drop(vid, case=None):
    """Non-recoverable inlet pressure loss at the installed valve's capacity, bar. Vapour service only."""
    it = ITEMS[vid]
    if it["liquid"]:
        return 0.0
    case = governing(vid)[0] if case is None else case
    p1 = relieving(it["set_now"], case)
    if case == "fire":
        stream = VESSEL[it["item"]]["stream"]
        mw, k, z = sat(stream, p1, "mw"), sat(stream, p1, "k"), sat(stream, p1, "z")
        t_K = sat(stream, p1, "t") + 273.15
    else:
        mw, k, z, t_K = _vapour_at(it, p1)
    bellows = it["kind"] == "bellows"
    w = cap_vapour(ORIFICE[it["orifice_now"]], p1, t_K, mw, k, z, KD_VAP,
                   kb(it["backp"] / p1) if bellows else 1.0, KC_DISC if it["disc"] else 1.0)
    rho = gas_density(p1, t_K, mw, z)
    d = it["inlet"]["id_mm"] / 1000.0
    v = w / 3600.0 / (rho * math.pi / 4.0 * d * d)
    kt = F_DARCY * it["inlet"]["length_m"] / d + sum(K_FIT[f] * it["inlet"][f] for f in K_FIT)
    return kt * rho * v * v / 2.0 / 1.0e5


def verdict(vid):
    it = ITEMS[vid]
    if ORIFICE[it["orifice_now"]] < governing(vid)[1]:
        return "inadequate"
    if it["kind"] == "conventional" and it["backp"] > CONV_BP_LIMIT * it["set_now"]:
        return "inadequate"
    if inlet_drop(vid) > INLET_LIMIT * it["set_now"]:
        return "inadequate"
    return "adequate"


_TRUTH = None


def truth():
    global _TRUTH
    if _TRUTH is None:
        t = {}
        for vid in IDS:
            case, need = governing(vid)
            t[vid] = dict(case=case, area=need, verdict=verdict(vid),
                          installed=ORIFICE[ITEMS[vid]["orifice_now"]], drop=inlet_drop(vid),
                          all_cases={c: case_area(vid, c) for c in ITEMS[vid]["cases"]})
        _TRUTH = t
    return _TRUTH


def row_ok(vid, case, area, verd):
    """Grade one submitted row. The area comparison carries a tolerance on the comparison itself, so that a
    value exactly at the edge of the band is not decided by binary rounding."""
    t = truth()[vid]
    rel = (area - t["area"]) / t["area"] if t["area"] else 0.0
    ok_case, ok_verd = case == t["case"], verd == t["verdict"]
    return (ok_case and abs(rel) <= TOL + 1.0e-12 and ok_verd), dict(
        case=1.0 if ok_case else 0.0, area=rel, verdict=1.0 if ok_verd else 0.0)
