"""Shared engine for the evidence studies: corrections for the bay from the shipped records and a step plan, with the
choices a sound method could make and the shortcuts a weak one takes, graded on the sealed definition.

Runs are emulated with tc.tc_wafer_run at the same seeds as the service (the seed depends on the run number and the
furnace), so a plan run here sees exactly the readings the service would return for that plan in that order. The
sealed definition (authoring/provenance/tc.py) is used only for that, for the calibration date and for grading
(tests/grade_tc.py logic: wafer within 2 K of the setpoint at 850 C and 1050 C in every zone).

Inference (first order: correction = drift + offset at the setpoint):
- drift at 600 C from isothermal 600 C soaks in the trends (spike - raw), or from a run's 600 C step (wafer - raw,
  the offset is zero there); carried by T / 600;
- drift growth from the trend of spike - raw at the furnace's process setpoint (the heater-to-load difference is
  fixed there), scaled to 600 C and carried from the soak to the calibration;
- the offset at one process temperature from the other through the ratio rho (850/1050);
- a furnace that never soaks, run at 1050 C: spike - raw at 850 C (its process trend, carried to the calibration)
  and at 1050 C (the run) separate drift (~T) from the heater-to-load difference (T^4 law zero at 600 C);
- a run at both 850 and 1050 C: drift ~ T and offset ~ rho give two equations per zone (wafer - raw);
- a retrofitted (SiC) furnace whose drift stays unknown: its offset is taken as the 2025 offset plus the liner
  change measured on another retrofitted furnace, and its drift is the rest;
- the liner change of a retrofitted furnace that is not run: the liner is one shield, so in each zone its offset
  change keeps one ratio to its rise of the heater-to-load difference. That difference (at 1050 C) comes from every
  furnace's process trend (spike - raw less the drift there, over the radiative shape; a split furnace's from its
  split); its rise is measured against the bare-quartz furnaces of the model, and the ratio on the retrofitted
  furnaces that were run ('proxy'). The shortcut carries the measured liner change over unchanged ('same').
"""
import functools, os, sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "authoring", "provenance"))
import tc

DATA = os.path.join(ROOT, "environment", "data")
BAY = tc.make_bay(7)
FURN, ZONES = tc.FURN, tc.ZONES
REG = pd.read_csv(os.path.join(DATA, "furnace_register.csv")).set_index("furnace")
LOG = pd.read_csv(os.path.join(DATA, "maintenance_log.csv"))
CAL = pd.read_csv(os.path.join(DATA, "tc_wafer_calibration_2025.csv"))
LOADED = pd.read_csv(os.path.join(DATA, "loaded_corrections.csv"))
SIC = [f for f in FURN if str(REG.loc[f, "liner"]).startswith("SiC")]
POCL3 = [f for f in FURN if "POCl3" in str(REG.loc[f, "process"])]
T_CAL = tc.T_CAL                                     # the procedure's run day, 2026-10-12 morning
TREND = {}
for _f in FURN:
    _t = pd.read_csv(os.path.join(DATA, "trends", "%s.csv" % _f.lower()))
    _t["day"] = np.arange(len(_t)) / 96.0
    TREND[_f] = _t
X, Y = CAL.wafer_minus_profile_1050_c.values, CAL.wafer_minus_profile_850_c.values
_m = np.abs(X) > 1.5
RHO = {"ls": float(X @ Y / (X @ X)), "median": float(np.median((Y / X)[_m])),
       "t4": float(tc.r(850.0)),                      # T^4 radiation law, zero at the 600 C soak
       "fat": 0.41,                                    # the F8 factory table
       "t4_no_reference": (1123.0 / 1323.0) ** 4,      # T^4 without the zero at 600 C
       "linear": 850.0 / 1050.0}                       # proportional to temperature


def _gap(rows, i):
    return (rows["spike_z%d" % i] - rows["profile_raw_z%d" % i]).values


@functools.lru_cache(maxsize=None)
def soak(f, stat="median", hold=True):
    t = TREND[f]
    states = ["standby", "hold"] if hold else ["standby"]
    iso = t[t.state.isin(states) & (t.setpoint_c == 600.0)]
    if len(iso) < 20:
        return None
    agg = np.median if stat == "median" else np.mean
    return np.array([agg(_gap(iso, i)) for i in range(1, 6)]), float(iso.day.median())


BOATS = "full"          # process rows used: 'full' (full boats only), 'regress' (all rows, load as a regressor,
                        # evaluated at a full boat) or 'all' (every row as if full: the shortcut)


def creep(f, how="fit"):
    return _creep(f, how, BOATS)


@functools.lru_cache(maxsize=None)
def _creep(f, how, boats):
    """spike - raw at the process setpoint: (value at T_CAL, slope per day, window mean, setpoint, mean raw).
    how: 'fit' (least-squares line) or 'ends' (last 48 h mean minus first 48 h mean over the time between)."""
    t = TREND[f]
    p = t[t.state == "process"]
    sp = float(p.setpoint_c.mode().iloc[0])
    p = p[p.setpoint_c == sp]
    if boats == "full":
        p = p[p.boat_wafers == p.boat_wafers.max()]
    G = np.array([_gap(p, i) for i in range(1, 6)])
    day = p.day.values
    if boats == "regress" and p.boat_wafers.nunique() > 1:
        full = float(p.boat_wafers.max())
        A = np.vstack([np.ones(len(p)), day, p.boat_wafers.values - full]).T
        c = np.linalg.lstsq(A, G.T, rcond=None)[0]
        G = G - np.outer(c[2], p.boat_wafers.values - full)      # rows referred to a full boat
    if how == "fit":
        A = np.vstack([np.ones(len(p)), day]).T
        c = np.linalg.lstsq(A, G.T, rcond=None)[0]
        now, slope = c[0] + c[1] * T_CAL, c[1]
    else:
        a, b = day <= day.min() + 2.0, day >= day.max() - 2.0
        slope = (G[:, b].mean(1) - G[:, a].mean(1)) / (day[b].mean() - day[a].mean())
        now = G[:, b].mean(1) + slope * (T_CAL - day[b].mean())
    raw = np.array([p["profile_raw_z%d" % i].mean() for i in range(1, 6)])
    return now, slope, G.mean(1), sp, raw


def g2025(f):
    c = CAL[CAL.furnace == f]
    if not len(c):
        return None
    c = c.set_index("zone").loc[ZONES]
    return np.array(c.wafer_minus_profile_850_c.values, float), np.array(c.wafer_minus_profile_1050_c.values, float)


def runs(plan):
    out = {}
    for k, (f, steps) in enumerate(plan, 1):
        rep = tc.tc_wafer_run(BAY[f], k, f, tuple(float(s) for s in steps))
        out[f] = {int(s["setpoint_c"]): {key: np.array([z[key] for z in s["zones"]])
                                         for key in ("profile_raw_c", "spike_c", "wafer_tc_c")} for s in rep}
    return out


def _wr(m):
    return m["wafer_tc_c"] - m["profile_raw_c"]


def spike_split(f, m1050, gap_how="fit", junction=True, p=None):
    """(k, h) per zone from spike - raw at the process setpoint (trend) and at 1050 C (run): drift coefficient and
    heater-to-load difference at 1050 C."""
    now, slope, mean, sp, raw_p = creep(f, "fit" if gap_how == "mean" else gap_how)
    g_p = mean if gap_how == "mean" else now
    g_r, raw_r = m1050["spike_c"] - m1050["profile_raw_c"], m1050["profile_raw_c"]
    if not junction:                                   # evaluated at the setpoints, heater term shaped like rho
        rp = tc.r(sp) if p is None else p
        sol = [np.linalg.solve([[sp, rp], [1050.0, 1.0]], [g_p[i], g_r[i]]) for i in range(5)]
        return np.array([x[0] for x in sol]), np.array([x[1] for x in sol])
    k, h = np.zeros(5), np.zeros(5)
    for _ in range(50):
        for i in range(5):
            A = np.array([[raw_p[i], tc.r(raw_p[i] / (1 - k[i]))], [raw_r[i], tc.r(raw_r[i] / (1 - k[i]))]])
            x = np.linalg.solve(A, [g_p[i], g_r[i]])
            k[i], h[i] = x[0] / (1 + x[0]), x[1]
    return k, h


def heater_load(f, d600, how="fit", junction=True):
    """Heater-to-load difference at 1050 C from the process trend: (spike - raw less the drift there) / r."""
    now, slope, mean, sp, raw_p = creep(f, how)
    if junction:
        tj = raw_p * (1 + d600 / 600.0)
        return (now - d600 / 600.0 * tj) / tc.r(tj)
    return (now - d600 * sp / 600.0) / tc.r(sp)


def _calibrate(plan, rho="ls", stat="median", hold=True, scale="C", use_liner=True, f8="fat", unknown="median",
              growth="fit", split="junction", split_gap="fit", f5="2025", liner_guess="none", liner="proxy",
              base_stat="median", base_set="quartz"):
    """plan: [(furnace, (steps...)), ...] in run order. Returns {(f, z): (c850, c1050)}.
    Shortcut switches: scale 'none' (drift at 600 C used at every temperature) or 'K' (scaled in kelvin);
    use_liner False (2025 offsets kept on the retrofitted furnaces); hold False (only 'standby' rows read);
    growth 'fit' or 'ends' (drift growth from the process spike - raw trend), 'none' (soak values used as they are)
    or 'unscaled' (the process-temperature growth added as if it were drift at 600 C); split 'junction' or
    'setpoint' (temperatures used in the spike split); split_gap 'fit', 'ends' (carried to the calibration) or
    'mean' (the four-week mean); f8 'fat' (factory values) or 'fleet' (mean 2025 T-200 offsets) when F8 is not run;
    f5 '2025' or 'fleet' when F5 is not run; unknown 'median' (bay median drift) or 'other' (the other doping
    furnace) for a furnace whose drift stays unknown."""
    p = RHO[rho]
    fac = {"C": lambda T: T / 600.0, "K": lambda T: (T + 273.0) / 873.0, "none": lambda T: 1.0}[scale]
    R = runs(plan)
    drift = {}
    for f in FURN:
        s = soak(f, stat, hold)
        if s is None:
            drift[f] = None
            continue
        d, tday = s
        if growth in ("fit", "ends", "unscaled"):
            _, slope, _, sp, _ = creep(f, "fit" if growth == "unscaled" else growth)
            d = d + slope * (1.0 if growth == "unscaled" else 600.0 / sp) * (T_CAL - tday)
        drift[f] = d
    for f, m in R.items():
        if 600 in m:
            drift[f] = _wr(m[600])
    corr, gnew = {}, {}

    def from_one_step(f, d):
        m = R[f]
        if 1050 in m:
            g1 = _wr(m[1050]) - d * fac(1050)
            return (d * fac(850) + p * g1, _wr(m[1050])), (p * g1, g1)
        g8 = _wr(m[850]) - d * fac(850)
        return (_wr(m[850]), d * fac(1050) + g8 / p), (g8, g8 / p)

    pending, heat_split = [], {}
    for f, m in R.items():
        steps = set(m) - {600}
        if not steps:
            continue
        d = drift[f]
        if d is None and steps == {850, 1050}:
            sol = np.linalg.solve(np.array([[fac(850), p], [fac(1050), 1.0]]), np.vstack([_wr(m[850]), _wr(m[1050])]))
            drift[f] = d = sol[0]
        elif d is None and 1050 in steps and f in TREND and split != "none":
            kk, hh = spike_split(f, m[1050], split_gap, split == "junction", p)
            drift[f] = d = kk * 600.0
            heat_split[f] = hh
        if d is None:
            pending.append(f)
            continue
        if steps == {850, 1050}:
            corr[f] = (_wr(m[850]), _wr(m[1050]))
            gnew[f] = (_wr(m[850]) - d * fac(850), _wr(m[1050]) - d * fac(1050))
        else:
            corr[f], gnew[f] = from_one_step(f, d)
    dg_src = [f for f in SIC if f in gnew and use_liner]
    dg = (np.mean([gnew[f][0] - g2025(f)[0] for f in dg_src], axis=0),
          np.mean([gnew[f][1] - g2025(f)[1] for f in dg_src], axis=0)) if dg_src else None
    dg_by = {}
    if liner == "proxy" and dg_src:
        heat = {}
        for f in FURN:
            if f in heat_split:
                heat[f] = heat_split[f]
            elif drift.get(f) is not None and f in TREND:
                heat[f] = heater_load(f, drift[f], "fit" if growth not in ("ends",) else "ends", split == "junction")
        model = REG.model
        qset = [f for f in FURN if f not in SIC and model[f] == model[SIC[0]] and f in heat]
        if base_set == "standby":
            qset = [f for f in qset if f not in POCL3]
        agg = np.median if base_stat == "median" else np.mean
        base = agg([heat[f] for f in qset], axis=0)
        rise = {f: heat[f] - base for f in SIC if f in heat}
        ratio = (np.mean([(gnew[f][0] - g2025(f)[0]) / rise[f] for f in dg_src], axis=0),
                 np.mean([(gnew[f][1] - g2025(f)[1]) / rise[f] for f in dg_src], axis=0))
        dg_by = {f: (ratio[0] * rise[f], ratio[1] * rise[f]) for f in rise}
    for f in pending:                                  # one process step, drift unknown
        m = R[f]
        if f in SIC and dg is not None:
            base = (g2025(f)[0] + dg[0], g2025(f)[1] + dg[1])
            T = 1050 if 1050 in m else 850
            drift[f] = (_wr(m[T]) - base[1 if T == 1050 else 0]) / fac(T)
        else:
            drift[f] = None
        if drift[f] is None:
            continue
        corr[f], gnew[f] = from_one_step(f, drift[f])
    med = np.median([v for v in drift.values() if v is not None], axis=0)
    for f in FURN:
        if f in corr:
            continue
        d = drift[f]
        if d is None:
            others = [drift[x] for x in POCL3 if x != f and drift[x] is not None]
            d = np.mean(others, axis=0) if (unknown == "other" and others) else med
        if f == "F8" and g2025(f) is None:
            if f8 == "fat":
                c = LOADED[LOADED.furnace == f].set_index("zone").loc[ZONES]
                base = (c.correction_850_c.values, c.correction_1050_c.values)
            else:
                t200 = [g2025(x) for x in FURN if x not in SIC and g2025(x) is not None]
                base = (np.mean([a for a, b in t200], axis=0), np.mean([b for a, b in t200], axis=0))
        elif f == "F5" and f5 == "fleet":
            t200 = [g2025(x) for x in FURN if x not in SIC and x != "F5" and g2025(x) is not None]
            base = (np.mean([a for a, b in t200], axis=0), np.mean([b for a, b in t200], axis=0))
        else:
            base = g2025(f)
            if f in SIC and dg is not None:
                dd = dg_by.get(f, dg)
                base = (base[0] + dd[0], base[1] + dd[1])
        corr[f] = (base[0] + d * fac(850), base[1] + d * fac(1050))
    return {(f, z): (float(corr[f][0][i]), float(corr[f][1][i])) for f in FURN for i, z in enumerate(ZONES)}


def calibrate(plan, boats="full", **kw):
    """_calibrate with the process rows chosen by boats ('full', 'regress' or 'all'; see BOATS)."""
    global BOATS
    old, BOATS = BOATS, boats
    try:
        return _calibrate(plan, **kw)
    finally:
        BOATS = old


def grade(cal):
    """(worst |wafer - setpoint| in K, worst zone, failing zones), as tests/grade_tc.py computes it."""
    res = tc.grade(cal, BAY)
    worst = max(res, key=lambda k: res[k]["err"])
    return res[worst]["err"], "%s%s" % worst, sorted("%s%s" % k for k, v in res.items() if not v["ok"])


REFERENCE_PLAN = [("F3", (1050,)), ("F5", (1050,)), ("F8", (1050,))]
