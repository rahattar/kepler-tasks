"""Sealed definition for relief-valve-adequacy.

The truth for unit 400's nine pressure relief valves: for each one the governing contingency, the required effective
orifice area and whether the installed valve is adequate under plant standard RP-7. The agent never reads this file;
the generator writes the unit's records from it and the verifier grades against it.

Everything the records show is derived here. Where a record is an observation rather than a fact (a metered flow, a
logged travel, a tested head) the generator adds the scatter the instrument schedule states; the truth below is
computed from the parameters, not from the records.
"""
import hashlib
import math

# ----------------------------------------------------------------------------- grading
TOL = 0.01          # relative tolerance on the load and on the header pressure
BACK_FLOOR = 0.002  # bar: below this the header pressure is reported as nothing, so it is compared absolutely
CAUSES = ("fire", "blocked_outlet", "control_valve_failure", "cooling_failure")

# ----------------------------------------------------------------------------- constants of the standard
ATM = 1.013         # bar
RGAS = 8314.0       # J/(kmol K)
FIRE_C = 43.2       # kW, m2; adequate drainage and prompt firefighting
FIRE_H = 7.6        # m above grade
FIRE_EXP = 0.82
F_DARCY = 0.018
OVER_FIRE = 0.21
OVER_OTHER = 0.10
SIL_MIN = 2         # the lowest integrity a function may have and still be credited
PROOF_MAX = 18      # months, the longest proof test interval a credited function may have
K_FIT = {"elbow90": 0.30, "tee_run": 0.20, "ball": 0.10, "entrance": 0.50}


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
        (37.0, 86.0, 183.0, 44.0, 1.20, 0.62, 345.0, 0.07),
        (42.0, 93.0, 148.0, 44.0, 1.23, 0.57, 313.0, 0.06),
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
PUMP = dict(sheet_shutoff_m=590.0, now_shutoff_m=545.0, rated_m3h=96.0, rated_head_m=505.0,
            suction_barg=9.5, temp_C=95.0)


def pump_b():
    """The shape of the pump's head curve, h(q) = h0 * (1 - b q^2), from the data sheet."""
    return (1.0 - PUMP["rated_head_m"] / PUMP["sheet_shutoff_m"]) / PUMP["rated_m3h"] ** 2


def pump_head(shutoff_m, q_m3h):
    return shutoff_m * (1.0 - pump_b() * q_m3h * q_m3h)

# instrumented functions that would prevent a contingency
SIF = {
    "SIF-4011": dict(sil=1, proof=12, initiator="PT-4013",
                     prevents=("PSV-401", "control_valve_failure")),
    "SIF-4031": dict(sil=2, proof=12, initiator="PT-4031", prevents=("PSV-403", "cooling_failure")),
    "SIF-4061": dict(sil=3, proof=12, initiator="PT-4063", prevents=("PSV-406", "cooling_failure")),
    "SIF-4091": dict(sil=2, proof=24, initiator="PT-4022", prevents=("PSV-409", "control_valve_failure")),
}
# the measurement each regulatory control uses: a contingency caused by that control failing is not independent
# of a function that initiates on the same element
CONTROL_TAG = {
    ("PSV-401", "control_valve_failure"): ("PT-4012",),
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
                  trays=dict(first_m=8.30, spacing=0.65, n=24, liquid_band=0.105)),
    "E-402": dict(shape="horizontal", d=0.9, tt=6.0, bottom_m=1.00, level_m=0.90, heads=2,
                  insul=None, stream="bottoms_product"),
}
T402_RAISED = 0.90   # the 2024 modification re-set T-402 this much higher on an extended skirt

# the one shell-and-tube exchanger whose shell has its own relief
EXCH = {
    "E-402": dict(tube_id_mm=15.7, tubes=168, hi_barg=55.0, hi_stream="feed_liquid", hi_temp_C=30.0,
                  shell_mawp=20.0),
}

# ----------------------------------------------------------------------------- the flare system
# one header takes every relief device on the unit and runs to the stack. The tip and the header are sized
# below; the losses through both follow the same expression as any other pipe run.
FLARE = dict(header_bore_mm=457.2, header_length_m=380.0, tip_bore_mm=304.8, tip_k=1.80)
TIP_K_OLD = 1.55     # the tip the 2019 study was made on, replaced in 2025 by another vendor's unit

# The unit's test crew will run a booking of BUDGET field tests, ordered before any result is known. Two of the
# six reach a graded value: the replaced tip's loss coefficient, which is on no data sheet, and P-401's shutoff
# head, whose last performance test predates the renewal of its rotating element. The other four cannot: E-406's
# coefficient-area, because the credit for SIF-4061 sets T-402's loss of cooling aside; PV-4031's coefficient,
# because no device admits a cause it could create; E-404's duty, because a loss of cooling is total however
# capable the condenser is; and PSV-404's set pressure, which the shop record already gives.
BUDGET = 2
TESTS = ("tip-backpressure", "pump-shutoff", "reboiler-E406", "valve-PV4031",
         "condenser-E404", "popcheck-PSV404")
PURGE = dict(mw=28.01, k=1.40, z=1.00, t_C=22.0)        # nitrogen, what the tip test is run on
TIP_TEST_FLOWS = (12000.0, 18000.0, 24000.0, 30000.0, 36000.0)
PUMP_TEST_FLOWS = (0.0, 48.0, 96.0, 120.0)

# the header's fittings, by their distance from the stack base along the developed length
FITTINGS = (("elbow90", 22.0), ("tee_run", 47.0), ("tee_run", 73.0), ("elbow90", 119.0),
            ("elbow90", 160.0), ("elbow90", 240.0), ("tee_run", 251.0), ("elbow90", 302.0))

# where each device ties into the header, in m from the stack base. PSV-407 was moved out to the new
# lateral in 2026, after the isometrics were last issued, which is what TIE_IN_SHEET still shows.
TIE_IN = {"PSV-408": 41.0, "PSV-409": 58.0, "PSV-406": 128.0, "PSV-405": 196.0, "PSV-407": 206.0,
          "PSV-401": 262.0, "PSV-402": 295.0, "PSV-403": 338.0, "PSV-404": 372.0}
TIE_IN_SHEET = dict(TIE_IN, **{"PSV-407": 92.0})

FIRE_ZONE = {"V-401": "A", "V-402": "A", "E-402": "A",
             "T-401": "B", "V-403": "B",
             "T-402": "C", "V-404": "C", "V-405": "C"}

# the unit's driven equipment: what it serves, what drives it and which supply that driver is on. The essential
# supply rides through a loss of power; the normal supply does not.
DRIVEN = {
    "E-404": dict(serves="T-401 overhead condenser", medium="cooling water", supply="normal"),
    "E-407": dict(serves="T-402 overhead condenser", medium="air", supply="normal"),
    "P-401": dict(serves="T-402 bottoms product to storage", medium="", supply="normal"),
    "K-901": dict(serves="instrument air", medium="", supply="normal"),
    "SIS": dict(serves="safety instrumented system", medium="", supply="essential"),
}

# where each control valve goes when it loses instrument air, and what that does to the item it feeds
FAIL_POSITION = {"PV-4001": "open", "PV-4021": "open", "PV-4031": "closed",
                 "PV-4061": "closed", "PV-4071": "open", "FV-4051": "closed"}

# the unit-wide contingencies of the flare load study, and the cause each one puts on the items it reaches
CONTINGENCIES = ("power_failure", "cooling_water_failure", "instrument_air_failure",
                 "fire_zone_a", "fire_zone_b", "fire_zone_c")

# the nine valves
ITEMS = {
    "PSV-401": dict(item="V-401", p_norm=58.0, mawp=62.0, set_reg=62.0, set_now=62.0,
                    fluid="feed_gas", t_relief_C=38.0, cv="PV-4001", source_barg=72.0,
                    cases=("control_valve_failure", "fire")),
    "PSV-402": dict(item="E-402", p_norm=14.0, mawp=20.0, set_reg=20.0, set_now=20.0,
                    fluid="bottoms_product",
                    cases=("fire",)),
    "PSV-403": dict(item="T-401", p_norm=28.0, mawp=31.0, set_reg=31.0, set_now=29.5,
                    fluid="c2_overhead", reb="E-403", bot_stream="c3_product",
                    cases=("cooling_failure", "fire")),
    "PSV-404": dict(item="V-403", p_norm=27.0, mawp=29.0, set_reg=29.0, set_now=29.0,
                    fluid="c2_overhead",
                    cases=("fire",)),
    "PSV-405": dict(item="P-401", p_norm=32.0, mawp=42.0, set_reg=42.0, set_now=42.0,
                    fluid="bottoms_product", pump=True,
                    cases=("blocked_outlet",)),
    "PSV-406": dict(item="T-402", p_norm=10.0, mawp=16.0, set_reg=16.0, set_now=16.0,
                    fluid="c4_product", reb="E-406", bot_stream="c4_product",
                    cases=("cooling_failure", "fire")),
    "PSV-407": dict(item="V-405", p_norm=16.0, mawp=19.0, set_reg=19.0, set_now=19.0,
                    fluid="c3_product", cv="PV-4071", source_barg=26.0,
                    cases=("fire", "control_valve_failure")),
    "PSV-408": dict(item="V-404", p_norm=10.0, mawp=18.0, set_reg=18.0, set_now=18.0,
                    fluid="c4_product",
                    cases=("fire",)),
    "PSV-409": dict(item="V-402", p_norm=8.0, mawp=11.0, set_reg=11.0, set_now=9.5,
                    fluid="feed_gas", t_relief_C=38.0, cv="PV-4021", source_barg=62.0,
                    cases=("control_valve_failure", "fire")),
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


def relieving(set_barg, case):
    """Relieving pressure, bar absolute."""
    return set_barg * (1.0 + (OVER_FIRE if case == "fire" else OVER_OTHER)) + ATM


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
    # the mass the reboiler makes is its duty over the latent heat of the liquid it is boiling, which is the
    # liquid the column holds, not of the vapour that leaves the top
    return 3600.0 * q / sat(it["bot_stream"], p1, "latent")


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


# ----------------------------------------------------------------------------- the relieving fluid
def _vapour_at(it, p1):
    """The relieving vapour's properties at the relieving pressure."""
    f = it["fluid"]
    if f == "feed_gas":
        return feed_mw(), gas(f, p1, "k"), gas(f, p1, "z"), it["t_relief_C"] + 273.15
    return sat(f, p1, "mw"), sat(f, p1, "k"), sat(f, p1, "z"), sat(f, p1, "t") + 273.15


# ----------------------------------------------------------------------------- the flare load study
def air_lost(contingency):
    """Instrument air is lost on its own, and also with the power while its compressor is on the normal supply."""
    if contingency == "instrument_air_failure":
        return True
    return contingency == "power_failure" and DRIVEN["K-901"]["supply"] == "normal"


def cooling_lost(item, contingency):
    """Whether the overhead condenser of a column stops under this contingency."""
    cooler = {"T-401": "E-404", "T-402": "E-407"}.get(item)
    if cooler is None:
        return False
    d = DRIVEN[cooler]
    if contingency == "power_failure":
        return d["supply"] == "normal"
    if contingency == "cooling_water_failure":
        return d["medium"] == "cooling water"
    return False


def pump_runs(contingency):
    return not (contingency == "power_failure" and DRIVEN["P-401"]["supply"] == "normal")


def sis_holds(contingency):
    """A safety instrumented function can only act if its system still has power."""
    return not (contingency == "power_failure" and DRIVEN["SIS"]["supply"] == "normal")


def cause_of(vid, contingency):
    """The contingency's cause at this valve, or None where the valve does not relieve."""
    it = ITEMS[vid]
    item = it["item"]
    if contingency.startswith("fire_zone_"):
        if FIRE_ZONE.get(item) != contingency[-1].upper():
            return None
        return "fire" if "fire" in it["cases"] else None
    if cooling_lost(item, contingency) and "cooling_failure" in it["cases"]:
        return "cooling_failure"
    if air_lost(contingency):
        tag = it.get("cv")
        if tag and FAIL_POSITION.get(tag) == "open" and "control_valve_failure" in it["cases"]:
            return "control_valve_failure"
        if it.get("pump") and "blocked_outlet" in it["cases"] \
                and FAIL_POSITION.get("FV-4051") == "closed" and pump_runs(contingency):
            return "blocked_outlet"
    return None


def relieving_rate(vid, cause):
    """The mass flow the valve passes under that cause, kg/h, or None where the cause cannot raise the item to
    its relieving pressure."""
    it = ITEMS[vid]
    if credited(vid, cause) and sis_holds("instrument_air_failure"):
        return None
    if cause == "fire":
        w = rate_fire(vid)
    elif cause == "cooling_failure":
        w = rate_cooling(vid, reb_ua(it["reb"]))
    elif cause == "control_valve_failure":
        w = rate_cv_failure(vid, CV[it["cv"]]["actual"])
    elif cause == "blocked_outlet":
        q = rate_pump(vid, PUMP["now_shutoff_m"])
        if q is None:
            return None
        w = q * 60.0 / 1000.0 * liq("bottoms_product", PUMP["temp_C"], "rho")
    else:
        raise ValueError(cause)
    return w if (w is not None and w > 0.0) else None


def relieving_stream(vid, cause):
    """(molar mass, k, Z, temperature K) of what the valve puts into the header under that cause."""
    it = ITEMS[vid]
    p1 = relieving(it["set_now"], cause)
    if cause == "fire":
        stream = VESSEL[it["item"]]["stream"]
        return (sat(stream, p1, "mw"), sat(stream, p1, "k"), sat(stream, p1, "z"),
                sat(stream, p1, "t") + 273.15)
    if cause == "blocked_outlet":
        return (86.0, 1.05, 1.0, PUMP["temp_C"] + 273.15)      # a liquid, carried on its mass alone
    return _vapour_at(it, p1)


def relieving_set(contingency, cv_rated=None, ua=None, raised=None, shutoff=None):
    """The valves that relieve under the contingency, with the mass flow and stream of each."""
    out = {}
    for vid in IDS:
        cause = cause_of(vid, contingency)
        if cause is None:
            continue
        if credited(vid, cause) and sis_holds(contingency):
            continue
        it = ITEMS[vid]
        if cause == "fire":
            w = rate_fire(vid, raised)
        elif cause == "cooling_failure":
            w = rate_cooling(vid, reb_ua(it["reb"]) if ua is None else ua)
        elif cause == "control_valve_failure":
            w = rate_cv_failure(vid, CV[it["cv"]]["actual"] if cv_rated is None else cv_rated)
        elif cause == "blocked_outlet":
            q = rate_pump(vid, PUMP["now_shutoff_m"] if shutoff is None else shutoff)
            if q is None:
                continue
            w = q * 60.0 / 1000.0 * liq("bottoms_product", PUMP["temp_C"], "rho")
        if w is None or w <= 0.0:
            continue
        out[vid] = (w, cause)
    return out


def mixed_stream(parts):
    """The molar mass, ratio of specific heats, compressibility and temperature of what arrives at the header."""
    total = sum(w for w, _ in parts.values())
    if total <= 0.0:
        return None
    moles, k_mix, z_mix, t_mix = 0.0, 0.0, 0.0, 0.0
    for vid, (w, cause) in parts.items():
        mw, k, z, t_K = relieving_stream(vid, cause)
        moles += w / mw
        k_mix += w * k
        z_mix += w * z
        t_mix += w * t_K
    return total / moles, k_mix / total, z_mix / total, t_mix / total


def header_pressure(parts):
    """The pressure at the header's blinded end, bar gauge, at the load the contingency puts on it.

    Worked from the tip outwards so that nothing has to be iterated: each length of header between two
    tie-ins carries only the devices that tie in beyond it, and carries their mixture, not the whole load.
    """
    total = sum(w for w, _ in parts.values())
    if total <= 0.0:
        return 0.0
    d_tip = FLARE["tip_bore_mm"] / 1000.0
    a_tip = math.pi / 4.0 * d_tip * d_tip
    mw, k, z, t_K = mixed_stream(parts)
    rho = gas_density(ATM, t_K, mw, z)
    v = total / 3600.0 / (rho * a_tip)
    p = ATM + FLARE["tip_k"] * rho * v * v / 2.0 / 1.0e5
    d = FLARE["header_bore_mm"] / 1000.0
    a = math.pi / 4.0 * d * d
    cuts = sorted(set([0.0, FLARE["header_length_m"]] + list(TIE_IN.values())))
    for lo, hi in zip(cuts, cuts[1:]):
        carried = {v_: wc for v_, wc in parts.items() if TIE_IN[v_] >= hi - 1.0e-9}
        w = sum(wc[0] for wc in carried.values())
        if w <= 0.0:
            continue
        mw, k, z, t_K = mixed_stream(carried)
        rho = gas_density(p, t_K, mw, z)
        v = w / 3600.0 / (rho * a)
        kt = F_DARCY * (hi - lo) / d + sum(K_FIT[f] for f, x in FITTINGS if lo < x <= hi)
        p += kt * rho * v * v / 2.0 / 1.0e5
    return p - ATM


_TRUTH = None


def truth():
    global _TRUTH
    if _TRUTH is None:
        t = {}
        for c in CONTINGENCIES:
            parts = relieving_set(c)
            t[c] = dict(valves=tuple(sorted(parts)),
                        load=sum(w for w, _ in parts.values()),
                        back=header_pressure(parts),
                        parts={v: (round(w, 1), cause) for v, (w, cause) in parts.items()})
        _TRUTH = t
    return _TRUTH


def row_ok(contingency, valves, load, back):
    """Grade one submitted row: the set of valves exactly, and the load and back pressure inside TOL relative.
    The comparison carries its own small allowance so a value at the edge of the band is not decided by binary
    rounding."""
    t = truth()[contingency]
    ok_set = tuple(sorted(valves)) == t["valves"]
    rel_load = (load - t["load"]) / t["load"] if t["load"] else 0.0
    ok_load = abs(rel_load) <= TOL + 1.0e-12
    # a header pressure below the floor is no pressure worth reporting, so it is compared against the floor
    # rather than relatively: a hundredth of a millibar has no relative meaning
    if t["back"] < BACK_FLOOR:
        rel_back, ok_back = back - t["back"], back < BACK_FLOOR
    else:
        rel_back = (back - t["back"]) / t["back"]
        ok_back = abs(rel_back) <= TOL + 1.0e-12
    return (ok_set and ok_load and ok_back), dict(valves=1.0 if ok_set else 0.0, load=rel_load, back=rel_back)


# --------------------------------------------------------------------------- the field tests
def _noise(seed, test, i, sigma):
    """Deterministic scatter, so a test gives the same reading however often the sealed model is reloaded."""
    h = hashlib.sha256(("%d/%s/%d" % (seed, test, i)).encode()).digest()
    u1 = (int.from_bytes(h[0:4], "big") + 1) / (2 ** 32 + 1)
    u2 = int.from_bytes(h[4:8], "big") / 2 ** 32
    return sigma * math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)


def test_tip_backpressure(seed):
    """Nitrogen through the tip from a temporary compressor, against the pressure at the stack base.

    The loss follows the expression RP-7 gives for the tip, with the density of what flows at atmospheric
    pressure, so the coefficient of the tip as installed is the slope of the measured rise against rho v^2 / 2.
    """
    d = FLARE["tip_bore_mm"] / 1000.0
    a = math.pi / 4.0 * d * d
    t_K = PURGE["t_C"] + 273.15
    rho = gas_density(ATM, t_K, PURGE["mw"], PURGE["z"])
    rows = []
    for i, w in enumerate(TIP_TEST_FLOWS):
        v = w / 3600.0 / (rho * a)
        rise = FLARE["tip_k"] * rho * v * v / 2.0 / 1.0e5
        rows.append(["%.0f" % w, "%.1f" % PURGE["t_C"], "%.5f" % (rise * (1.0 + _noise(seed, "tip", i, 0.002)))])
    return (["nitrogen_flow_kg_per_h", "nitrogen_temp_C", "stack_base_gauge_bar"], rows,
            "tip back pressure test, temporary compressor on the purge connection, stack base tapping")


def test_pump_shutoff(seed):
    """P-401 on its present rotating element, four points as the works test takes them."""
    rows = []
    for i, q in enumerate(PUMP_TEST_FLOWS):
        h = pump_head(PUMP["now_shutoff_m"], q) + _noise(seed, "pump", i, 0.8)
        rows.append(["%.1f" % q, "%.1f" % h, "2975"])
    return (["flow_m3h", "head_m", "speed_rpm"],
            rows, "P-401 performance test after the renewal of the rotating element")


def test_reboiler_e406(seed):
    """E-406 on test: the steam it condenses and the temperatures either side of it."""
    ua = reb_ua("E-406")
    r = REB["E-406"]
    p = r["steam_barg"] + ATM
    rows = []
    for i, load in enumerate((0.80, 0.90, 1.00)):
        dt = (sat("steam", p, "t") - r["bot_normal_C"]) * load
        q = ua * dt
        w = 3600.0 * q / sat("steam", p, "latent")
        rows.append(["%.2f" % r["steam_barg"], "%.0f" % (w * (1.0 + _noise(seed, "reb", i, 0.004))),
                     "%.1f" % sat("steam", p, "t"), "%.1f" % (sat("steam", p, "t") - dt)])
    return (["steam_barg", "steam_kg_per_h", "steam_temp_C", "bottoms_temp_C"], rows,
            "E-406 performance test at three reboil rates")


def test_valve_pv4031(seed):
    """PV-4031 stroked against flow: the coefficient at full travel, by the same route as a trend."""
    c = CV["PV-4031"]
    rows = []
    for i, travel in enumerate((0.40, 0.55, 0.70, 0.85, 1.00)):
        kv = c["actual"] * c["r"] ** (travel - 1.0) / 1.156
        mw, k, z = sat(c["stream"], c["p_up"], "mw"), sat(c["stream"], c["p_up"], "k"), \
            sat(c["stream"], c["p_up"], "z")
        rho = gas_density(c["p_up"], c["t_up"] + 273.15, mw, z)
        w = valve_flow(kv, c["xt"], c["fp"], k, c["p_up"], c["p_dn"], rho)
        rows.append(["%.0f" % (travel * 100.0), "%.2f" % c["p_up"], "%.2f" % c["p_dn"],
                     "%.1f" % c["t_up"], "%.0f" % (w * (1.0 + _noise(seed, "cv", i, 0.003)))])
    return (["travel_pct", "upstream_bara", "downstream_bara", "upstream_temp_C", "flow_kgh"], rows,
            "PV-4031 stroked against measured flow, five travels")


def test_condenser_e404(seed):
    """E-404 on test: the duty it carries and the approach it holds on the day."""
    q = REB["E-403"]["design_kw"] * (FEED_NOW / FEED_DESIGN) * 0.96
    rows = []
    for i, (water_in, water_out) in enumerate(((27.0, 38.5), (29.0, 40.8), (31.0, 43.1))):
        duty = q * (1.0 - 0.01 * i) * (1.0 + _noise(seed, "cond", i, 0.005))
        rows.append(["%.1f" % water_in, "%.1f" % water_out, "%.0f" % duty,
                     "%.1f" % (sat("c2_overhead", ITEMS["PSV-403"]["p_norm"] + ATM, "t"))])
    return (["cooling_water_in_C", "cooling_water_out_C", "duty_kw", "condensing_temp_C"], rows,
            "E-404 performance test over three cooling water temperatures")


def test_popcheck_psv404(seed):
    """PSV-404 lifted on the stand, three pops."""
    setp = ITEMS["PSV-404"]["set_now"]
    rows = [["%d" % (i + 1), "%.2f" % (setp * (1.0 + _noise(seed, "pop", i, 0.004)))] for i in range(3)]
    return (["pop", "lift_pressure_barg"], rows, "PSV-404 lifted on the test stand, three pops, as found")


TEST_RUNNERS = {
    "tip-backpressure": test_tip_backpressure,
    "pump-shutoff": test_pump_shutoff,
    "reboiler-E406": test_reboiler_e406,
    "valve-PV4031": test_valve_pv4031,
    "condenser-E404": test_condenser_e404,
    "popcheck-PSV404": test_popcheck_psv404,
}


def run_test(name, seed):
    return TEST_RUNNERS[name](seed)
