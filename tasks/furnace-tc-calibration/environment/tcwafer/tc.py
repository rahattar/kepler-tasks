"""Sealed truth for diffusion bay 2: eight vertical furnaces, five heater zones each, their profile thermocouples and
the instrumented (TC) wafers.

Controller (all furnaces): the corrected profile reading is raw + c(T), with c linear between its 850 C and 1050 C
points and held constant outside them; the controller holds the corrected reading at the setpoint T.

Truth in each zone, with Tj the temperature at the profile junction (C):
    raw profile reading = Tj * (1 - k),   k = d1000 / 1000     (a drifted Pt-Rh junction reads low, by k * Tj)
    wafer temperature   = Tj + G * r(Tj), r(T) = ((T+273)^4 - 873^4) / (1323^4 - 873^4)
The offset term is radiative and zero in the isothermal 600 C soak. With correction c loaded the controller holds
raw = T - c, so Tj = (T - c) / (1 - k) and the wafer error is Tj + G r(Tj) - T; the exact correction solves
Tj + G r(Tj) = T. Spike thermocouples (in the heater, outside the tube) read Tj + gradient * r(Tj) + certificate
error; in an isothermal 600 C soak the gradient term is zero, so spike - raw = k * Tj + certificate error.

Heater-to-load difference (gradient, at 1050 C): set by the model's heater, tube and load, much the same zone by zone
on furnaces of one model (GRAD_T200, GRAD_VX, +-0.25 K). SiC liner (2026, F2, F3, F7): an extra radiation shield
between heater and load. Its shielding s (per furnace and zone; slip-cast wall thickness varies along the liner and
from piece to piece) raises the heater-to-load difference by DGRAD_SIC * s and shifts the wafer-to-junction offset
by DG_SIC * s, so in a given zone the two changes keep one ratio on every furnace.

Time: days from 2026-09-14 00:00 (start of the trends). The calibration (TC-wafer runs, corrections loaded, grading)
is at T_CAL, 2026-10-12 08:00. Drift d1000 is given at T_CAL; a profile assembly in phosphorus service keeps
drifting, linearly in time at d1000_rate (K per day at 1000 C): F6 fast (sheath cracked, 2026-09-08), F3 slowly.
"""
import numpy as np

FURN = ["F%d" % i for i in range(1, 9)]
ZONES = ["Z1", "Z2", "Z3", "Z4", "Z5"]           # Z1 top (exhaust end) ... Z5 bottom (door end)
TOL = 2.0                                       # K, wafer temperature at 850 C and 1050 C, every zone
T_LO, T_HI = 850.0, 1050.0
T_CAL = 28.0 + 8.0 / 24.0                       # 2026-10-12 08:00, days from 2026-09-14 00:00
CAL_DATE = "2026-10-12"
T_HOLD = 1.0 + 7.0 / 24.0                       # F6 hold 2026-09-15 02:00-12:00, mid-point
MONTH = 30.4


def r(T):
    return ((T + 273.0) ** 4 - 873.0 ** 4) / (1323.0 ** 4 - 873.0 ** 4)


# wafer-to-junction offset at 1050 C, by zone
G_T200 = np.array([2.6, 1.1, 0.6, 1.3, -3.2])         # model T-200, quartz liner
DG_SIC = np.array([4.2, 3.0, 2.6, 3.3, 5.4])          # offset change for a liner of nominal shielding (s = 1)
DGRAD_SIC = DG_SIC / 0.65                             # heater-to-load change for s = 1 (one ratio in every zone)
GRAD_T200 = np.array([9.5, 7.0, 6.0, 7.0, 12.0])      # heater-to-load difference at 1050 C, model T-200, quartz
GRAD_VX = np.array([8.0, 6.5, 6.0, 6.5, 10.0])        # model VX-300
SHIELD = {"F2": np.array([0.90, 1.00, 1.15, 1.35, 1.60]),     # liner shielding by zone (slip-cast wall thickness)
          "F3": np.array([1.20, 1.15, 1.10, 1.15, 1.25]),
          "F7": np.array([0.30, 0.45, 0.65, 0.75, 0.55])}
G_VX = np.array([-1.8, 3.6, 4.1, 3.2, -6.0])          # model VX-300 (F8)
G_FAT_ERR = np.array([2.6, -1.4, -2.1, -1.0, 3.1])    # F8 factory acceptance (vendor tube and boat) minus site truth
D_TUBE = np.array([-2.9, 3.0, -2.6, 2.8, 3.7])       # F5: new process tube (Aug 2026) moves the junctions


def make_bay(seed=7):
    rng = np.random.default_rng(seed)
    bay = {}
    spec = {   # model, process, liner, standby in the trend window
        "F1": ("T-200", "dry oxidation", "quartz", True),
        "F2": ("T-200", "anneal", "SiC", True),
        "F3": ("T-200", "POCl3 doping", "SiC", False),
        "F4": ("T-200", "wet oxidation", "quartz", True),
        "F5": ("T-200", "anneal", "quartz", True),
        "F6": ("T-200", "POCl3 doping", "quartz", False),
        "F7": ("T-200", "dry oxidation", "SiC", True),
        "F8": ("VX-300", "anneal", "quartz", True),
    }
    for f in FURN:
        model, proc, liner, standby = spec[f]
        g_old = (G_VX if model == "VX-300" else G_T200) + rng.normal(0, 0.35, 5)
        dg = DG_SIC + rng.normal(0, 0.15, 5) if liner == "SiC" else np.zeros(5)
        d1000 = rng.uniform(0.3, 1.2, 5) * np.array([0.8, 1.0, 1.1, 1.0, 0.7])
        bay[f] = dict(model=model, process=proc, liner=liner, standby=standby, G_old=g_old, G=g_old + dg,
                      d1000=d1000, spike_err=rng.normal(0, 0.12, 5),
                      gradient=rng.uniform(4.0, 16.0, 5),         # heater-to-junction at 1050 C, per zone
                      cal2025_err=rng.normal(0, 0.12, 5))
    # F4: new profile assembly January 2026, little drift
    bay["F4"]["d1000"] = rng.uniform(0.05, 0.25, 5)
    # F1: cracked profile sheath (work order), contamination in the middle zones
    bay["F1"]["d1000"] = np.array([1.1, 5.6, 6.4, 5.1, 0.9]) + rng.normal(0, 0.2, 5)
    # phosphorus-bearing furnaces: large drift that does not follow the hours model, different per assembly
    bay["F3"]["d1000"] = np.array([9.6, 12.4, 13.5, 11.0, 6.9]) + rng.normal(0, 0.3, 5)
    bay["F6"]["d1000"] = np.array([2.2, 3.1, 3.6, 2.9, 1.8]) + rng.normal(0, 0.3, 5)    # at the hold (T_HOLD)
    # F5: process tube replaced Aug 2026, assembly refitted in the new tube's well: the offset changes per zone
    bay["F5"]["G"] = bay["F5"]["G_old"] + D_TUBE + rng.normal(0, 0.2, 5)
    # F8: installed 2026, new assembly
    bay["F8"]["d1000"] = rng.uniform(0.05, 0.2, 5)
    # heater-to-load difference by model, and the SiC liners' shielding (own stream, so the draws above are kept)
    rl = np.random.default_rng(seed + 500)
    for f in FURN:
        b = bay[f]
        b["gradient"] = (GRAD_VX if b["model"] == "VX-300" else GRAD_T200) + rl.normal(0, 0.25, 5)
        if b["liner"] == "SiC":
            s = SHIELD[f] * (1.0 + rl.normal(0, 0.04, 5))
            b["shield"] = s
            b["G"] = b["G_old"] + DG_SIC * s + rl.normal(0, 0.08, 5)
            b["gradient"] = b["gradient"] + DGRAD_SIC * s + rl.normal(0, 0.10, 5)
    # drift growth in phosphorus service, K per day at 1000 C; zero elsewhere. d1000 is then the value at T_CAL.
    for f in FURN:
        bay[f]["d1000_rate"] = np.zeros(5)
    bay["F3"]["d1000_rate"] = np.array([0.20, 0.30, 0.35, 0.25, 0.15]) / MONTH
    bay["F6"]["d1000_rate"] = np.array([1.8, 3.2, 4.0, 2.8, 1.4]) / MONTH      # cracked sheath near Z3
    bay["F6"]["d1000"] = bay["F6"]["d1000"] + bay["F6"]["d1000_rate"] * (T_CAL - T_HOLD)
    return bay


def k(b, t=None):
    """Drift coefficient at time t (days); at the calibration when t is None."""
    if t is None:
        return b["d1000"] / 1000.0
    return (b["d1000"] - b["d1000_rate"] * (T_CAL - t)) / 1000.0


def d(b, T):
    """Drift (reading low) at junction temperature T."""
    return k(b) * T


def g(b, T, old=False):
    return (b["G_old"] if old else b["G"]) * r(T)


def junction(b, raw, t=None):
    return raw / (1.0 - k(b, t))


def wafer_temp(b, raw, old=False):
    tj = junction(b, raw)
    return tj + g(b, tj, old)


def needed(b, T):
    """The correction that puts the wafer exactly on the setpoint T (Newton on Tj + G r(Tj) = T)."""
    tj = np.full(5, float(T))
    for _ in range(30):
        f = tj + g(b, tj) - T
        df = 1.0 + b["G"] * 4.0 * (tj + 273.0) ** 3 / (1323.0 ** 4 - 873.0 ** 4)
        tj = tj - f / df
    return T - tj * (1.0 - k(b))


def correction_at(c_lo, c_hi, T):
    if T <= T_LO:
        return c_lo
    if T >= T_HI:
        return c_hi
    return c_lo + (c_hi - c_lo) * (T - T_LO) / (T_HI - T_LO)


def wafer_error(b, c_lo, c_hi, T):
    """Wafer temperature minus setpoint, per zone, with corrections (c_lo, c_hi) loaded."""
    c = correction_at(np.asarray(c_lo, float), np.asarray(c_hi, float), T)
    return wafer_temp(b, T - c) - T


def grade(cal, bay):
    """cal: {(furnace, zone): (c850, c1050)}. Returns {(f, z): worst |wafer - setpoint|} and pass flags."""
    out = {}
    for f in FURN:
        b = bay[f]
        for i, z in enumerate(ZONES):
            if (f, z) not in cal:
                out[(f, z)] = dict(err=float("inf"), ok=False)
                continue
            lo, hi = cal[(f, z)]
            c_lo = np.full(5, lo); c_hi = np.full(5, hi)
            e = max(abs(float(wafer_error(b, c_lo, c_hi, T)[i])) for T in (T_LO, T_HI))
            out[(f, z)] = dict(err=e, ok=e <= TOL)
    return out


STEPS = (600.0, 850.0, 1050.0)


def tc_wafer_run(b, k, f, want=STEPS):
    """TC-wafer run number k on furnace f, corrections disabled (raw profile control), at the requested steps among
    600 C soak, 850 C and 1050 C. Per zone: raw profile, spike, and the mean of the instrumented wafers in that zone
    (certificate +-0.2 K). The noise draws do not depend on which steps are requested."""
    rng = np.random.default_rng(9000 + 31 * k + FURN.index(f))
    wafer_cert = rng.normal(0, 0.12, 5)
    steps = []
    for T in STEPS:
        prof = T + rng.normal(0, 0.03, 5)                     # the controller holds the raw profile on setpoint
        tj = junction(b, prof)
        spike = tj + (b["gradient"] * r(tj) if T > 600.0 else 0.0) + b["spike_err"] + rng.normal(0, 0.05, 5)
        wafer = tj + g(b, tj) + wafer_cert + rng.normal(0, 0.06, 5)
        if T not in want:
            continue
        steps.append(dict(setpoint_c=T, zones=[dict(zone=z, profile_raw_c=round(float(prof[i]), 2),
                                                     spike_c=round(float(spike[i]), 2),
                                                     wafer_tc_c=round(float(wafer[i]), 2)) for i, z in enumerate(ZONES)]))
    return steps
