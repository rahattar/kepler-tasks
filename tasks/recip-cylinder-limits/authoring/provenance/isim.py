"""Sealed definition: the lowest field pressure at which each cylinder of a three-stage reciprocating gas booster
may be run while the unit holds its contract flow, and the requirement of the plant's standard that governs it.

The deliverable for each cylinder is that pressure in bar absolute, to 0.01 bar, and the name of the governing
requirement. A cylinder is right when the pressure is within TOL of this definition, relatively, and the requirement
is the one named here.

The machine is one frame of six throws, two to a stage, taking suction from a declining field and discharging into a
pipeline whose pressure is held. Nothing about the duty is free except the field pressure:

- the pressures between the stages are not set by anyone. They settle where each stage passes the molar flow the
  stage before it delivers, less whatever the separator between them knocks out as condensate. That is two
  equations in the two interstage pressures;
- the speed is not set by anyone either. The unit has to hold the contract flow, so the speed is whatever the flow
  needs at the pressures that settle. As the field declines the suction density falls and the speed rises, which
  raises the inertia load of every throw by the square of it;
- the drive cannot be run above the rated speed, so the range of field pressures the unit can work at ends where
  the speed the contract flow needs reaches the rated speed.

Every cylinder is therefore coupled to every other: open a clearance pocket on one and the stage loses capacity, so
the interstage pressure above it rises, the speed the contract flow needs rises, and the inertia load of all six
throws rises with it.

Against that duty each cylinder is checked on six requirements of standard RC-4: the gas load alone against the
cylinder body's rating; the gas and inertia loads together, in compression and in tension, against the throw's rated
rod load; the discharge temperature; the cylinder power; and the angle through which the rod load reverses. The
answer is the lowest whole 0.01 bar of field pressure at which the cylinder meets every requirement at that pressure
and at every higher pressure in the range.

What the agent's records do not say as a conclusion:

- the interstage pressures and the speed of the operating record are today's. They are not constants: the records
  give the field pressure, the pipeline pressure and the contract flow, and the rest follows from the machine;
- the second-stage separator has been bypassed since 2026-08-19 (maintenance log), so it knocks nothing out and the
  third stage takes the gas the second stage discharges;
- the gas is not the data sheet's: the feed analysis of 2026-10-02 supersedes it, and each separator changes it;
- cylinder 2B's liner was re-bored to the first repair size: the as-bored record of the latest entry, not the
  nameplate bore;
- 2B took a new piston at the same overhaul, so its reciprocating weight is the data sheet's and the difference of
  the two piston weights on the register's shop ticket;
- throw 6 carries a spare running assembly, whose weight no record states: it has to be weighed;
- throw 2 carries the larger piston rod, which the cylinder schedule gives in one column;
- the clearance pockets of 2A and 3A were opened after the last performance run, so the clearance of the head end is
  the data sheet's fraction plus the pocket's volume over that end's swept volume;
- the second-stage after-cooler is fouled, so the suction temperature of the third stage is the operating record's
  and not the design value, and its element sits on the suction bottle, so the standard's correction applies;
- the rated rod load of every throw is the data sheet's less the reduction of the OEM's service bulletin, and the
  crosshead of throw 5 is de-rated below that after its repair;
- the isentropic exponent is taken at the mean of the suction and discharge temperatures, so it and the discharge
  temperature are found together.

Four facts need the laboratory and the allowance pays for two: the second stage's analysis, the third stage's
analysis, and the reciprocating weights of 2B and 3B. The third stage's analysis is the second stage's, the
separator being bypassed, and 2B's weight follows from the shop ticket, so the two readings go on the second-stage
analysis and the weighing of 3B.

The ratings of the cylinders were set by authoring/provenance/tune.py from the design rules it states; it checks them.
"""
import math

import numpy as np

REQ = ("gas_load", "rod_load_compression", "rod_load_tension", "discharge_temperature",
       "cylinder_power", "pin_reversal")

TOL = 0.005                # relative, on the lowest allowable field pressure
PS_STEP = 0.01             # bar, the standard's resolution
SURVEY_SEED = 61           # the plant's own records; fixed, so they do not move with the laboratory seed
NOISE_GC = 0.04            # mol per cent, one standard deviation of a gas chromatograph reading
NOISE_WEIGH = 0.15         # kg, one standard deviation of a weighing
BUDGET = 2                 # laboratory readings, in all
ROD_LENGTH_RATIO = 4.0     # connecting rod length / crank radius, from the frame data
DPS = 0.35                 # bar, the standard's suction valve loss
DPD = 0.70                 # bar, the standard's discharge valve loss
REV_MIN = 15               # degrees, the standard's least reversal
BOTTLE_OFFSET = 6.0        # K, the standard's correction from a bottle-mounted element to the valve flange
TD_LIMIT = 135.0           # C, the standard's allowable discharge temperature for the gas
TD_TOL = 0.001             # K, the standard's convergence test on the discharge temperature
RGAS = 8314.0              # J per kmol per K
BULLETIN = 0.92            # the service bulletin's factor on every throw's rated rod load

# the duty: the field pressure the unit runs at today, the pipeline pressure it discharges into, and the contract
# flow it has to hold, kmol per hour
FIELD_TODAY = 26.0
PIPE = 170.0
CONTRACT = 460.0
FIELD_FLOOR = 0.50         # of today's field pressure: the bottom of the standard's range

# the frame: stroke mm, rated speed as the data sheet gives it, and the rated rod load of each throw before the
# service bulletin's reduction
FRAME = dict(stroke=305.0, rpm_rated=380.0)
ROD_RATED = {1: 125.0, 2: 130.0, 3: 140.0, 4: 145.0, 5: 235.0, 6: 200.0}
DERATED = {"3A": 150.0}    # kN, the crosshead de-rated after its repair

# the separators: the molar fraction each knocks out as condensate, by the stage it stands after. The second is
# bypassed, so it knocks nothing out; its design figure is on the data sheet.
CONDENSATE = {1: 0.018, 2: 0.0}
CONDENSATE_DESIGN = {1: 0.018, 2: 0.011}
BYPASSED = 2

COMPONENTS = ("methane", "ethane", "propane", "butane", "nitrogen", "carbon_dioxide")
MW = dict(methane=16.04, ethane=30.07, propane=44.10, butane=58.12, nitrogen=28.01, carbon_dioxide=44.01)

# the plant's property table: the molar heat capacity of each component at four temperatures, C
CP_T = (25.0, 75.0, 125.0, 175.0)
CP_R = {
    "methane": (4.46, 4.84, 5.26, 5.70),
    "ethane": (6.32, 7.07, 7.82, 8.56),
    "propane": (9.08, 10.15, 11.20, 12.22),
    "butane": (11.90, 13.26, 14.60, 15.90),
    "nitrogen": (3.50, 3.51, 3.53, 3.56),
    "carbon_dioxide": (4.47, 4.75, 5.01, 5.25),
}

# the gas of each stage: the mol per cent of the components, after the separator of the stage before it. The feed is
# the analysis of 2026-10-02; the data sheet's analysis is superseded.
GAS_TRUE = {
    1: dict(methane=82.10, ethane=9.40, propane=4.20, butane=1.60, nitrogen=1.30, carbon_dioxide=1.40),
    2: dict(methane=86.40, ethane=8.30, propane=2.70, butane=0.45, nitrogen=0.75, carbon_dioxide=1.40),
}
GAS_SHEET = dict(methane=79.50, ethane=10.10, propane=5.30, butane=2.10, nitrogen=1.50, carbon_dioxide=1.50)

# the suction temperature of each stage at the valve flange: the reading of the operating record, and the design
# value. The third stage's element sits on the suction bottle, so the standard's correction applies to it.
TS_READ = {1: 38.0, 2: 45.0, 3: 70.0}
TS_DESIGN = {1: 38.0, 2: 45.0, 3: 45.0}
ON_BOTTLE = (3,)

_REPORTED = {}


def analysis(stage):
    """The analysis as the chromatograph reported it, mol per cent to 0.01. This is the number the records and the
    laboratory print, so it is the number the answer is built from. The separator after the second stage is
    bypassed, so the third stage sees the gas the second stage discharges and its sample stream is the second's.
    """
    if stage == 3:
        return analysis(2)
    if stage not in _REPORTED:
        rng = np.random.default_rng(SURVEY_SEED * 100 + stage)
        raw = {c: GAS_TRUE[stage][c] + float(rng.normal(0.0, NOISE_GC)) for c in COMPONENTS}
        total = sum(raw.values())
        _REPORTED[stage] = {c: round(100.0 * raw[c] / total, 2) for c in COMPONENTS}
    return _REPORTED[stage]


def _c(stage, throw, bore, bore_plate, rod, mrec, mrec_sheet, clear_he_sheet, clear_ce_sheet, pocket_cm3,
       double, kw, glim, desc):
    j = dict(stage=stage, throw=throw, bore=bore, bore_plate=bore_plate, rod=rod, mrec=mrec,
             mrec_sheet=mrec_sheet, clear_he_sheet=clear_he_sheet, clear_ce_sheet=clear_ce_sheet,
             pocket_cm3=pocket_cm3, double=double, kw=kw, glim=glim, desc=desc)
    sw_he, _ = swept(j)
    j["clear_he"] = clear_he_sheet + pocket_cm3 / (sw_he * 1e6)
    j["clear_ce"] = clear_ce_sheet
    return j


def areas(j):
    """the head end and crank end areas, m2"""
    a = math.pi / 4.0 * (j["bore"] / 1000.0) ** 2
    return a, a - math.pi / 4.0 * (j["rod"] / 1000.0) ** 2


def swept(j):
    """the swept volume of the head end and of the crank end, m3"""
    a_he, a_ce = areas(j)
    return a_he * FRAME["stroke"] / 1000.0, a_ce * FRAME["stroke"] / 1000.0


# the six cylinders. bore is the as-bored size and bore_plate the nameplate's; mrec the reciprocating weight of the
# assembly as it now stands and mrec_sheet the data sheet's; clear_he_sheet and clear_ce_sheet the data sheet's
# clearances with every pocket closed, each as a fraction of that end's own swept volume, and pocket_cm3 the volume
# of the head end pocket where one now stands open; kw the cylinder's rated power and glim its maximum allowable
# gas load, both from its data sheet.
CYL = {
    "1A": _c(1, 1, 205.0, 205.0, 65.0, 340.0, 340.0, 0.110, 0.130, 0.0, True, 130.0, 115.0,
             "first stage, throw 1"),
    "1B": _c(1, 2, 205.0, 205.0, 85.0, 346.0, 346.0, 0.110, 0.132, 0.0, True, 122.0, 120.0,
             "first stage, throw 2, larger piston rod"),
    "2A": _c(2, 3, 150.0, 150.0, 65.0, 300.0, 300.0, 0.140, 0.160, 200.0, True, 132.0, 130.0,
             "second stage, throw 3, clearance pocket open"),
    "2B": _c(2, 4, 154.0, 150.0, 65.0, 320.0, 302.0, 0.140, 0.160, 0.0, True, 140.0, 140.0,
             "second stage, throw 4, liner re-bored to the first repair size and a new piston fitted"),
    "3A": _c(3, 5, 112.0, 112.0, 55.0, 298.0, 298.0, 0.155, 0.175, 165.0, True, 224.0, 150.0,
             "third stage, throw 5, clearance pocket open, crosshead de-rated after repair"),
    "3B": _c(3, 6, 116.0, 116.0, 60.0, 331.0, 294.0, 0.160, 0.180, 0.0, True, 244.0, 160.0,
             "third stage, throw 6, spare running assembly fitted"),
}
STAGE_CYL = {st: tuple(c for c in sorted(CYL) if CYL[c]["stage"] == st) for st in (1, 2, 3)}

# the laboratory's readings, the facts that need one, and the facts the records already settle
LAB_CMDS = ("gc", "weigh")
NEEDED = ("gc 2", "gc 3", "weigh 2B", "weigh 3B")
RECOVERABLE = {"gc 3": "the separator after the second stage is bypassed, so the third stage's gas is the second's",
               "weigh 2B": "the overhaul register's shop ticket gives the piston fitted and the piston removed"}
PISTON = {"2B": (61.4, 43.4)}      # the shop ticket: the piston as fitted and the piston removed, kg

_DEG = np.arange(360)
_TH = np.radians(_DEG)
_HEAD_FIRST = _DEG < 180
_CACHE = {}


def mol_mass(stage):
    g = analysis(stage)
    return sum(g[c] * MW[c] for c in COMPONENTS) / 100.0


def cp_mix(stage):
    """the mol-average molar heat capacity of a stage's gas at each temperature of the property table"""
    g = analysis(stage)
    return [sum(g[c] * CP_R[c][i] for c in COMPONENTS) / 100.0 for i in range(len(CP_T))]


def kappa_at(stage, t):
    cp = np.interp(t, CP_T, cp_mix(stage))
    return cp / (cp - 1.0)


def suction_t(stage):
    """the suction temperature at the valve flange: the reading, corrected where the element sits on the bottle"""
    return TS_READ[stage] + (BOTTLE_OFFSET if stage in ON_BOTTLE else 0.0)


def ratio(ps, pd):
    """the pressure ratio across a cylinder, with the standard's valve losses"""
    return (pd + DPD) / (ps - DPS)


def kappa_td(stage, ps, pd):
    """The isentropic exponent and the discharge temperature together. The exponent is taken at the mean of the
    suction and discharge temperatures, so the two have to be found by iteration; the standard's test is that
    successive discharge temperatures differ by less than TD_TOL.
    """
    ts = suction_t(stage)
    r = ratio(ps, pd)
    td = np.full(np.shape(r), float(ts))
    k = kappa_at(stage, ts)
    for _ in range(300):
        k = kappa_at(stage, 0.5 * (ts + td))
        new = (ts + 273.15) * r ** ((k - 1.0) / k) - 273.15
        if np.max(np.abs(new - td)) < TD_TOL:
            return k, new
        td = new
    return k, td


def vol_eff(stage, ps, pd, j):
    """the volumetric efficiency of the head end and of the crank end of a cylinder"""
    k = kappa_td(stage, ps, pd)[0]
    g = ratio(ps, pd) ** (1.0 / k) - 1.0
    return 1.0 - j["clear_he"] * g, 1.0 - j["clear_ce"] * g


def stage_swept(stage, ps, pd):
    """the swept volume of the stage times the volumetric efficiency of each end, m3 per revolution"""
    tot = 0.0
    for cid in STAGE_CYL[stage]:
        j = CYL[cid]
        sw_he, sw_ce = swept(j)
        ve_he, ve_ce = vol_eff(stage, ps, pd, j)
        tot = tot + sw_he * ve_he + (sw_ce * ve_ce if j["double"] else 0.0)
    return tot


def molar_per_rev(stage, ps, pd):
    """the molar flow of the stage, kmol per revolution, from the density at its suction"""
    return (ps - DPS) * 1e5 * stage_swept(stage, ps, pd) / (RGAS * (suction_t(stage) + 273.15))


def _vbisect(f, lo, hi, n=70):
    lo = np.broadcast_to(np.asarray(lo, float), np.shape(hi)).astype(float).copy()
    hi = np.asarray(hi, float).copy()
    flo = f(lo)
    for _ in range(n):
        mid = 0.5 * (lo + hi)
        fm = f(mid)
        same = np.sign(fm) == np.sign(flo)
        lo = np.where(same, mid, lo)
        flo = np.where(same, fm, flo)
        hi = np.where(same, hi, mid)
    return 0.5 * (lo + hi)


def split(field, sweeps=16):
    """the two interstage pressures at which each stage passes the molar flow the stage before it delivers"""
    field = np.asarray(field, float)
    p12 = np.sqrt(field * PIPE)
    p23 = np.sqrt(p12 * PIPE)
    for _ in range(sweeps):
        p12 = _vbisect(lambda x: molar_per_rev(1, field, x) * (1.0 - CONDENSATE[1]) - molar_per_rev(2, x, p23),
                       field + 0.6, p23 - 0.6)
        p23 = _vbisect(lambda x: molar_per_rev(2, p12, x) * (1.0 - CONDENSATE[2]) - molar_per_rev(3, x, PIPE),
                       p12 + 0.6, np.broadcast_to(PIPE - 0.6, np.shape(p12)))
    return p12, p23


def duty(field):
    """The interstage pressures and the speed the contract flow needs, at each field pressure. The contract flow is
    measured at the export meter, so it is the molar flow the last stage delivers.
    """
    p12, p23 = split(field)
    per_rev = molar_per_rev(1, field, p12) * (1.0 - CONDENSATE[1]) * (1.0 - CONDENSATE[2])
    return p12, p23, CONTRACT / (60.0 * per_rev)


def grid():
    """the standard's range of field pressures, ascending"""
    return np.round(np.arange(round(FIELD_TODAY * FIELD_FLOOR, 2), FIELD_TODAY + PS_STEP / 2.0, PS_STEP), 2)


def table():
    """the duty at every field pressure of the range, worked out once"""
    if "t" not in _CACHE:
        g = grid()
        p12, p23, speed = duty(g)
        _CACHE["t"] = (g, p12, p23, speed, speed <= FRAME["rpm_rated"])
    return _CACHE["t"]


def rod_limit(cid):
    """the rated rod load of the throw: the data sheet's less the bulletin's reduction, or the de-rated figure"""
    base = ROD_RATED[CYL[cid]["throw"]] * BULLETIN
    return min(base, DERATED[cid]) if cid in DERATED else base


def margins(cid):
    """the relative margin of each requirement at every field pressure of the range (>= 0 passes)"""
    j = CYL[cid]
    g, p12, p23, speed, _ = table()
    ps, pd = {1: (g, p12), 2: (p12, p23), 3: (p23, np.full_like(g, PIPE))}[j["stage"]]
    a_he, a_ce = areas(j)
    head = np.where(_HEAD_FIRST, pd[:, None], ps[:, None])
    crank = np.where(_HEAD_FIRST, ps[:, None], pd[:, None]) * (1.0 if j["double"] else 0.0)
    gas = (head * a_he - crank * a_ce) * 1e2
    w = speed[:, None] * 2.0 * np.pi / 60.0
    inertia = -j["mrec"] * w * w * (FRAME["stroke"] / 2000.0) * (
        np.cos(_TH) + np.cos(2.0 * _TH) / ROD_LENGTH_RATIO) / 1e3
    comb = gas + inertia
    k, td = kappa_td(j["stage"], ps, pd)
    n = (k - 1.0) / k
    ve_he, ve_ce = vol_eff(j["stage"], ps, pd, j)
    sw_he, sw_ce = swept(j)
    ends = sw_he * ve_he + (sw_ce * ve_ce if j["double"] else 0.0)
    kw = (ps - DPS) * 1e5 * ends * speed / 60.0 / n * (ratio(ps, pd) ** n - 1.0) / 1e3
    lim = rod_limit(cid)
    return {
        "gas_load": j["glim"] / np.abs(gas).max(axis=1) - 1.0,
        "rod_load_compression": lim / comb.max(axis=1) - 1.0,
        "rod_load_tension": lim / np.maximum(-comb.min(axis=1), 1e-9) - 1.0,
        "discharge_temperature": TD_LIMIT / td - 1.0,
        "cylinder_power": j["kw"] / kw - 1.0,
        "pin_reversal": (comb < 0.0).sum(axis=1) / float(REV_MIN) - 1.0,
    }


def ps_min(cid, checked=REQ):
    """The lowest field pressure at which the cylinder meets every requirement at that pressure and at every higher
    one in the range, and the requirement with the least margin one step below it. The range ends where the speed
    the contract flow needs reaches the rated speed.
    """
    g, _, _, _, inside = table()
    m = margins(cid)
    ok = inside.copy()
    for q in checked:
        ok &= m[q] >= 0.0
    hold = np.cumprod(ok[::-1])[::-1].astype(bool)
    if not hold.any():
        return None, None
    i = int(np.argmax(hold))
    if i == 0:
        return float(g[0]), None
    return float(g[i]), min(REQ, key=lambda q: m[q][i - 1])


def bound(cid, req):
    """the lowest field pressure from which that requirement alone is met all the way up"""
    return ps_min(cid, checked=(req,))[0]


def truth():
    """{cylinder: (lowest field pressure bar, governing requirement)}"""
    return {cid: ps_min(cid) for cid in CYL}


def lab_gc(stage):
    """one gas analysis: the mol per cent of each component, to 0.01, as the chromatograph reports it"""
    return dict(analysis(stage))


def lab_weigh(cid, rng):
    """the shop weighing of a throw's reciprocating assembly, kg to 0.1"""
    return round(CYL[cid]["mrec"] + float(rng.normal(0.0, NOISE_WEIGH)), 1)
