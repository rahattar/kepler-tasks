"""Sealed definition: the process flow and the tube-side fouling resistance of each bay of an air-cooled exchanger
bank, as a survey with a limited crew booking can establish them.

The deliverable for each bay is its process flow in kg/s and its tube-side fouling resistance in m2 K/W. A flow is
right when it is within TOL_FLOW of this definition, relatively, and a fouling resistance when it is within TOL_RF.

Six bays hang in parallel off one process header. The header's inlet temperature, the mixed return temperature, the
total flow and the common tube-side pressure drop are on the plant's instruments; the air side of each bay is known
from its fan. Each bay's fouling resistance is unknown, except the one re-tubed last month, which the standard takes
as clean. That leaves five unknowns.

Two of the plant's own readings carry information about them: the mixed return temperature, which fixes the sum of
the duties, and the common pressure drop, which the fouling layer raises. Those two can settle one unmeasured bay
between them and no more: left to carry two, they fix only a combination, and both come out at tens of per cent.
So a survey of four points - one on each of four of the five unknown bays - determines the bank, and a survey that
spends a point on the clean bay, on a point the plant already reads, on a tapping that cannot be reached, or twice
on one bay, leaves two bays unmeasured and nothing can recover it afterwards.

What the agent's records do not say as a conclusion:

- bay F was re-tubed at the last shutdown (maintenance log), so its tube side is clean;
- the flows are not equal and are not measured: they settle where every bay takes the same pressure drop, which
  the fouling itself changes, so the split and the fouling have to be found together;
- bay D's fan was rewired after a motor change and runs in reverse (log), so its air flow is down on the fan curve's
  figure and its air-side coefficient with it;
- bay B's louvres are stuck part open (log), which does the same to it;
- bay C was re-tubed two shutdowns ago to a heavier gauge (register), so its bore and its clean conductance are not
  the data sheet's;
- bay E's outlet tapping is plugged (log), so a process outlet temperature cannot be had there;
- bay B is a two-pass bundle where the others are four-pass (data sheet), which changes its correction factor and
  its pressure drop;
- the process stream is not the data sheet's: the analysis of 2026-10-02 supersedes it, and the specific heat comes
  from the property table at the mean temperature;
- the total flow on file is a volumetric reading and wants the density at the header temperature;
- the ambient drifts through the survey, and the crew's readings are timestamped;
- the air flow of a bay is not measured: it follows from the fan's power and its curve.

The geometry, the clean conductances and the fouling resistances were set by authoring/provenance/tune.py from the
design rules it states; it checks them.
"""
import math

import numpy as np

TOL_FLOW = 0.03            # relative, on a bay's process flow
TOL_RF = 0.10              # relative, on a bay's fouling resistance
BUDGET = 4                 # points the crew can survey
SURVEY_SEED = 73           # the plant's own instruments; fixed, so the records do not move with the crew's seed
NOISE_CREW = 0.05          # K, one reading of the crew's calibrated probe
REPEATS = 5                # readings the standard requires at a point, averaged
NOISE_PLANT_T = 0.05       # K, the plant's thermowells
NOISE_PLANT_DP = 0.0003    # bar, the header's differential gauge
NOISE_FLOW = 0.01          # relative, the crew's clamp-on meter

# the process stream and the air
M_TOTAL = 120.0            # kg/s through the header
T_IN = 95.0                # C at the header inlet
T_AIR = 28.0               # C, the ambient of the survey hour
CP_AIR = 1.006             # kJ/kg K
K_FOUL = 2.2               # W/m K, the conductivity the standard assigns to the fouling layer
RHO = 690.0                # kg/m3 at the header temperature
MU = 3.4e-4                # Pa s
LAMBDA = 0.110             # W/m K, the stream's conductivity

COMPONENTS = ("propane", "butane", "pentane", "hexane")
CP_T = (20.0, 60.0, 100.0)                 # C, the property table's temperatures
CP_R = {"propane": (1.67, 1.86, 2.06), "butane": (1.72, 1.91, 2.11),
        "pentane": (2.21, 2.38, 2.56), "hexane": (2.24, 2.40, 2.58)}   # kJ/kg K
STREAM = dict(propane=12.0, butane=31.0, pentane=38.0, hexane=19.0)    # mass per cent, 2026-10-02
STREAM_SHEET = dict(propane=20.0, butane=34.0, pentane=30.0, hexane=16.0)


def _b(bay, ntube, passes, length, bore, bore_plate, area_ratio, fan_kw, air, air_curve, rf, tapping, desc):
    return dict(bay=bay, ntube=ntube, passes=passes, length=length, bore=bore, bore_plate=bore_plate,
                area_ratio=area_ratio, fan_kw=fan_kw, air=air, air_curve=air_curve, rf=rf,
                tapping=tapping, desc=desc)


# the six bays. bore is the as-tubed size and bore_plate the data sheet's; air is the air flow the fan now delivers
# and air_curve the figure its curve gives at the rated power; rf is the tube-side fouling resistance, m2 K/W.
BAY = {
    "A": _b("A", 312, 4, 12.2, 21.2, 21.2, 21.0, 55.0, 116.0, 116.0, 0.00052, True, "as built"),
    "B": _b("B", 312, 2, 12.2, 21.2, 21.2, 21.0, 55.0, 98.0, 116.0, 0.00088, True,
            "two pass bundle; louvres stuck part open"),
    "C": _b("C", 280, 4, 12.2, 23.0, 21.2, 19.5, 55.0, 110.0, 110.0, 0.00041, True,
            "re-tubed two shutdowns ago to a heavier gauge"),
    "D": _b("D", 312, 4, 12.2, 21.2, 21.2, 21.0, 55.0, 70.0, 116.0, 0.00095, True,
            "fan running in reverse after the motor change"),
    "E": _b("E", 296, 4, 10.7, 21.2, 21.2, 20.0, 50.0, 104.0, 104.0, 0.00063, False,
            "outlet tapping plugged"),
    "F": _b("F", 272, 4, 10.7, 23.0, 23.0, 18.5, 50.0, 98.0, 98.0, 0.0, True,
            "re-tubed at the last shutdown, so clean"),
}
IDS = tuple(sorted(BAY))
CLEAN = "F"                                     # the bay the log shows re-tubed last month
UNKNOWN = tuple(c for c in IDS if c != CLEAN)

# the crew's survey: the kinds of point it can take, and the points the plant already reads
KINDS = ("t-out", "air-out", "flow")
ON_FILE = ("t-in-header", "t-out-header", "dp-header", "air-in")


def cp_stream(t):
    """the specific heat of the stream at a temperature, from the property table and the analysis of record"""
    return sum(STREAM[c] * float(np.interp(t, CP_T, CP_R[c])) for c in COMPONENTS) / 100.0


def tube_area(j):
    """tube-side heat transfer area, m2"""
    return j["ntube"] * j["passes"] * math.pi * (j["bore"] / 1000.0) * j["length"]


def layer_mm(j):
    """the thickness of the fouling layer the standard infers from its resistance"""
    return j["rf"] * K_FOUL * 1000.0


def bore_fouled(j):
    return j["bore"] / 1000.0 - 2.0 * layer_mm(j) / 1000.0


def dp_bay(m, j):
    """tube-side pressure drop of a bay, bar"""
    d = bore_fouled(j)
    a = j["ntube"] * math.pi / 4.0 * d * d
    v = m / (RHO * a)
    re = RHO * v * d / MU
    f = 0.3164 / re ** 0.25
    return f * (j["passes"] * j["length"] / d) * RHO * v * v / 2.0 / 1e5


def ua(m, j, cp):
    """the overall conductance of a bay, kW/K: the tube side, the fouling layer and the air side through the fins"""
    d = bore_fouled(j)
    a = j["ntube"] * math.pi / 4.0 * d * d
    v = m / (RHO * a)
    re = RHO * v * d / MU
    pr = cp * 1000.0 * MU / LAMBDA
    h_i = 0.023 * re ** 0.8 * pr ** 0.4 * LAMBDA / d
    at = tube_area(j)
    h_o = 38.0 * (j["air"] / 116.0) ** 0.6
    return 1.0 / (1.0 / (h_i * at) + j["rf"] / at + 1.0 / (h_o * at * j["area_ratio"])) / 1000.0


def duty(m, j, cp):
    """the duty of a bay, kW, with its process outlet and air outlet temperatures"""
    c_p = m * cp
    c_a = j["air"] * CP_AIR
    u = ua(m, j, cp)
    cmin, cmax = min(c_p, c_a), max(c_p, c_a)
    cr = cmin / cmax
    ntu = u / cmin
    eff = 1.0 - math.exp(-(1.0 - math.exp(-ntu * cr)) / cr)      # cross flow, one fluid mixed
    q = eff * cmin * (T_IN - T_AIR)
    return q, T_IN - q / c_p, T_AIR + q / c_a


def split():
    """the flows that make every bay take the same pressure drop and add to the total"""
    m = np.full(len(IDS), M_TOTAL / len(IDS))
    for _ in range(400):
        dps = np.array([dp_bay(m[i], BAY[c]) for i, c in enumerate(IDS)])
        m = m * (dps.mean() / dps) ** 0.5
        m = m * M_TOTAL / m.sum()
        if float(np.max(np.abs(dps / dps.mean() - 1.0))) < 1e-12:
            break
    return m


def state():
    """everything the plant and the crew could read, with the bank as it stands"""
    m = split()
    cp = cp_stream(0.5 * (T_IN + 40.0))
    q, t_out, a_out = [], [], []
    for i, c in enumerate(IDS):
        qq, tt, aa = duty(m[i], BAY[c], cp)
        q.append(qq)
        t_out.append(tt)
        a_out.append(aa)
    q = np.array(q)
    return dict(m=m, q=q, t_out=np.array(t_out), a_out=np.array(a_out),
                t_mix=T_IN - q.sum() / (M_TOTAL * cp),
                dp=float(np.mean([dp_bay(m[i], BAY[c]) for i, c in enumerate(IDS)])), cp=cp)


def truth():
    """{bay: (process flow kg/s, fouling resistance m2 K/W)}"""
    s = state()
    return {c: (float(s["m"][i]), BAY[c]["rf"]) for i, c in enumerate(IDS)}


def lab_probe(point, rng):
    """one point of the survey, as the crew reports it"""
    kind, bay = point.rsplit("-", 1)
    s = state()
    i = IDS.index(bay)
    if kind == "t-out":
        if not BAY[bay]["tapping"]:
            return None
        v = s["t_out"][i] + float(rng.normal(0.0, NOISE_CREW / math.sqrt(REPEATS)))
        return round(v, 2)
    if kind == "air-out":
        v = s["a_out"][i] + float(rng.normal(0.0, NOISE_CREW / math.sqrt(REPEATS)))
        return round(v, 2)
    v = s["m"][i] * (1.0 + float(rng.normal(0.0, NOISE_FLOW)))
    return round(v, 2)
