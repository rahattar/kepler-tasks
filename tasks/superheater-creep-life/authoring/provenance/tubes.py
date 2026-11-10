"""Sealed definition for superheater-creep-life (prototype): the secondary superheater outlet elements E1..E10 of
boiler B2. Units: degC, K, MPa, mm, um, h, kW/m2.

Each day the boiler is on line it carries load L (fraction of 600 MW). Element e's crown (the hottest point, furnace
side of the outlet leg) sees heat flux q = Q0 x f_e(t) x phi(t) x L, f_e the element's flux factor (OEM map, changed
for E3/E4 by the 2022 burner modification), phi the fuel factor (1.08 after the 2024 coal switch).
Outlet steam: T_out,e = T_in + DT0 x f_e x phi; the penthouse pad thermocouple reads T_out,e + PAD_K.
Crown mid-wall temperature (the plant standard, docs):
    T_mw = T_out + q (Do/Di)(1/h_i + x/k_ox) + q h / (2 k_m),  h_i = HI0 L^0.8
Steam-side oxide x (um): d(x^2)/dt = A_g exp(-Q/(R T_ox)), T_ox = T_out + q (Do/Di)(1/h_i + x/(2 k_ox)), on-line hours;
reset to 0 by the May 2023 chemical clean and on replacement.
Hoop stress (mean diameter): sigma = P (Do - h) / (2 h), P in MPa, h current wall.
Rupture: log10 sigma = a_g - b_g LMP/1000, LMP = T(K) (20 + log10 t_r).  Damage: sum of on-line hours / t_r.
"""
import numpy as np
import pandas as pd

ELEMENTS = ["E%d" % i for i in range(1, 11)]
GRADE = {e: ("T22" if i < 6 else "T91") for i, e in enumerate(ELEMENTS)}
START, END = pd.Timestamp("2015-01-01"), pd.Timestamp("2026-10-31")
DO = 50.8
H0 = {"T22": 7.6, "T91": 6.4}
H0_E6 = 5.9                    # E6 was built with thinner-wall tube than the register says (7.6)
H0_E9_NEW = 8.0                # the spare fitted to E9 in 2023 is a heavier-wall tube
Q0 = 70.0                      # kW/m2 at f = 1, phi = 1, full load
DT0 = 62.0                     # K steam pickup at f = 1
HI0 = 6000.0                   # W/m2K at full load
K_OX, K_M = 0.6, 33.0
PAD_K = 3.0
P_MPA = 17.2
A_OX = {"T22": 4.4e12, "T91": 3.0e11}   # um^2/h
Q_OX = 200e3
RG = 8.314
LMP = {"T22": (6.128, 0.215), "T91": (7.325, 0.251)}
F_MAP = {"E1": 1.00, "E2": 0.96, "E3": 1.04, "E4": 1.02, "E5": 0.93, "E6": 0.95, "E7": 0.96, "E8": 1.15, "E9": 1.00,
         "E10": 0.92}
BURNER_MOD = pd.Timestamp("2022-09-12")
F_MOD = {"E3": 1.30, "E4": 1.12}         # flux factor after the burner modification
FUEL_SWITCH, PHI_NEW = pd.Timestamp("2024-07-01"), 1.08
CLEAN = pd.Timestamp("2023-05-15")
REPLACED = {"E2": pd.Timestamp("2021-06-20"), "E9": pd.Timestamp("2023-11-08")}
THIN = {e: 0.02 for e in ELEMENTS}       # mm/yr fireside wastage
THIN.update({"E10": 0.20})
EROSION = {"E1": (pd.Timestamp("2021-04-01"), 0.60)}   # soot-blower erosion from IK-14 in service, mm/yr
TIN_MEAN = {"A": 428.0, "B": 498.0}     # inlet headers: A feeds E1-E6 (primary pass), B feeds E7-E10
HEADER = {e: ("A" if GRADE[e] == "T22" else "B") for e in ELEMENTS}


def days():
    return pd.date_range(START, END, freq="D")


def operation(seed=1):
    """Daily load fraction (0 = off line) and inlet steam temperature."""
    rng = np.random.default_rng(seed)
    d = days()
    n = len(d)
    L = np.clip(0.78 + 0.12 * np.sin(2 * np.pi * (d.dayofyear / 365.25) * 2) + rng.normal(0, 0.08, n), 0.45, 1.0)
    off = np.zeros(n, bool)
    for y in range(2015, 2027):     # an outage each spring plus forced outages
        s = pd.Timestamp("%d-04-01" % y) + pd.Timedelta(days=int(rng.integers(0, 30)))
        off |= (d >= s) & (d < s + pd.Timedelta(days=int(rng.integers(18, 32))))
    for _ in range(40):
        i = int(rng.integers(0, n - 6))
        off[i:i + int(rng.integers(1, 6))] = True
    off |= d > pd.Timestamp("2026-10-20")          # the outage now
    L = np.where(off, 0.0, np.round(L, 3))
    return pd.DataFrame(dict(date=d, L=L, tinA=TIN_MEAN["A"] + rng.normal(0, 2.0, n),
                             tinB=TIN_MEAN["B"] + rng.normal(0, 2.0, n)))


def flux_factor(e, d):
    f = np.full(len(d), F_MAP[e])
    if e in F_MOD:
        f = np.where(d >= BURNER_MOD, F_MOD[e], f)
    return f


def phi(d):
    return np.where(d >= FUEL_SWITCH, PHI_NEW, 1.0)


def wall(e, d):
    """Wall thickness (mm) by date."""
    t0 = REPLACED.get(e, START)
    t0 = np.where(d >= t0, np.datetime64(t0), np.datetime64(START))     # the old tube before a replacement
    yrs = np.maximum((d.values - t0).astype("timedelta64[D]").astype(float), 0) / 365.25
    h = H0[GRADE[e]] - THIN[e] * yrs
    if e == "E6":
        h = H0_E6 - THIN[e] * yrs
    if e == "E9":
        h = np.where(d >= REPLACED["E9"], H0_E9_NEW - THIN[e] * yrs, h)
    if e in EROSION:
        s, r = EROSION[e]
        h = h - r * np.maximum((d - s).days.values, 0) / 365.25
    return h


def history(e, op):
    """Daily T_out, T_mw, oxide, stress, damage for element e (true)."""
    d = pd.DatetimeIndex(op.date)
    L = op.L.values
    f = flux_factor(e, d) * phi(d)
    tout = op["tin" + HEADER[e]].values + DT0 * f
    q = Q0 * f * L * 1e3                 # W/m2
    h = wall(e, d)
    di = DO - 2 * h
    g = GRADE[e]
    a, b = LMP[g]
    x = 0.0
    T_mw = np.zeros(len(d)); X = np.zeros(len(d)); D = np.zeros(len(d)); S = np.zeros(len(d))
    t0 = REPLACED.get(e)
    for i in range(len(d)):
        if (t0 is not None and d[i] == t0) or d[i] == CLEAN:
            x = 0.0
        if t0 is not None and d[i] < t0:
            continue                      # the old tube's life is not this tube's
        if L[i] <= 0:
            X[i] = x; continue
        hi = HI0 * L[i] ** 0.8
        r = DO / di[i]
        Tox = tout[i] + q[i] * r * (1 / hi + x * 1e-6 / (2 * K_OX)) + 273.15
        x = np.sqrt(x * x + A_OX[g] * np.exp(-Q_OX / (RG * Tox)) * 24.0)
        Tm = tout[i] + q[i] * r * (1 / hi + x * 1e-6 / K_OX) + q[i] * h[i] * 1e-3 / (2 * K_M)
        sig = P_MPA * (DO - h[i]) / (2 * h[i])
        lmp = (a - np.log10(sig)) / b * 1000.0
        tr = 10 ** (lmp / (Tm + 273.15) - 20.0)
        T_mw[i], X[i], S[i], D[i] = Tm, x, sig, 24.0 / tr
    return pd.DataFrame(dict(date=d, L=L, tout=tout, tmw=T_mw, oxide=X, sigma=S, dmg=D))


def truth(op=None):
    op = operation() if op is None else op
    return {e: float(history(e, op).dmg.sum()) for e in ELEMENTS}


# ---- what the records show (gen.py) ----
TC_FAIL = {"E3": pd.Timestamp("2022-03-01"), "E4": pd.Timestamp("2025-08-04"), "E6": pd.Timestamp("2025-01-20")}
DETACHED = ("none", pd.Timestamp("2022-03-01"), 9.0, 180)   # pad lifting off from then: reads as if the flux had not
                                                          # changed, and low by up to 9 K, reached over 180 days
DRIFT = ("E5", pd.Timestamp("2022-10-01"), 0.035)         # pad TC reading low by 0.035 K per day from then
SWAP = (("E7", "E8"), pd.Timestamp("2024-03-12"))            # historian migration swapped the two tags
E2_PAD_OFFSET = 7.0                                         # refitted pad on the new E2 tube reads 7 K high
E7_PAD = (pd.Timestamp("2020-02-10"), -10.0)                # renewed E7 pad reads 10 K low
UNIT_CHANGE = pd.Timestamp("2019-07-01")                    # DCS upgrade: degF before, degC from then
LOST_YEAR = 2018                                            # historian archive lost; monthly summary only
UT_SURVEYS = [pd.Timestamp("2019-04-16"), pd.Timestamp("2023-04-18")]
UT_MISSING = set()


def records(seed=7):
    """Historian (daily) with its faults, the 2018 monthly summary, and the UT wall surveys."""
    op = operation()
    rng = np.random.default_rng(seed)
    d = pd.DatetimeIndex(op.date)
    n = len(d)
    on = op.L.values > 0
    cols = dict(date=d, load_MW=np.round(op.L.values * 600.0, 1),
                ms_press_bar=np.where(on, np.round(P_MPA * 10 + rng.normal(0, 0.8, n), 1), 0.0),
                hdrA_in=np.round(op.tinA.values, 1), hdrB_in=np.round(op.tinB.values, 1))
    for e in ELEMENTS:
        f = flux_factor(e, d) * phi(d)
        t = op["tin" + HEADER[e]].values + DT0 * f + PAD_K + rng.normal(0, 1.0, n)
        if e == DETACHED[0]:
            ramp = np.clip((d - DETACHED[1]).days.values / DETACHED[3], 0, 1)
            t_bad = op["tin" + HEADER[e]].values + DT0 * F_MAP[e] * phi(d) + PAD_K - DETACHED[2] * ramp + rng.normal(0, 1.0, n)
            t = np.where(d >= DETACHED[1], t_bad, t)
        if e == "E2":
            t = np.where(d >= REPLACED["E2"], t + E2_PAD_OFFSET, t)
        if e == "E7":
            t = np.where(d >= E7_PAD[0], t + E7_PAD[1], t)
        if e == DRIFT[0]:
            t = t - DRIFT[2] * np.maximum((d - DRIFT[1]).days.values, 0)
        if e in TC_FAIL:
            t = np.where(d >= TC_FAIL[e], np.nan, t)
        if e == "E9":
            t = np.where(d >= REPLACED["E9"], np.nan, t)     # thermocouple not refitted on the new tube
        cols["TMT_" + e] = t
    h = pd.DataFrame(cols)
    # off-line days: metal near ambient, headers too
    for c in ["hdrA_in", "hdrB_in"] + ["TMT_" + e for e in ELEMENTS]:
        h.loc[~on, c] = np.round(35 + rng.normal(0, 5, (~on).sum()), 1)
        h.loc[h[c].isna() & False, c] = np.nan
    for e in TC_FAIL:
        h.loc[h.date >= TC_FAIL[e], "TMT_" + e] = np.nan
    h.loc[h.date >= REPLACED["E9"], "TMT_E9"] = np.nan
    a, b = SWAP[0]
    m = h.date >= SWAP[1]
    h.loc[m, ["TMT_" + a, "TMT_" + b]] = h.loc[m, ["TMT_" + b, "TMT_" + a]].values
    # monthly summary of the lost year (from the daily truth), then drop it
    y = h[h.date.dt.year == LOST_YEAR].copy()
    y["month"] = y.date.dt.strftime("%Y-%m")
    y["on"] = y.load_MW > 0
    summ = []
    for mth, g in y.groupby("month"):
        o = g[g.on]
        row = dict(month=mth, hours_on_line=int(24 * len(o)), mean_load_MW=round(float(o.load_MW.mean()), 1))
        for e in ELEMENTS:
            row["mean_TMT_" + e] = round(float(o["TMT_" + e].mean()), 1)
        summ.append(row)
    h = h[h.date.dt.year != LOST_YEAR]
    temp_cols = ["hdrA_in", "hdrB_in"] + ["TMT_" + e for e in ELEMENTS]
    early = h.date < UNIT_CHANGE
    h.loc[early, temp_cols] = h.loc[early, temp_cols] * 9 / 5 + 32
    h[temp_cols] = h[temp_cols].round(1)
    summ = pd.DataFrame(summ)
    for e in ELEMENTS:                          # the summary was kept in degF like the old historian
        summ["mean_TMT_" + e] = (summ["mean_TMT_" + e] * 9 / 5 + 32).round(1)
    ut = []
    for s in UT_SURVEYS:
        for e in ELEMENTS:
            if (e, s) in UT_MISSING or s < REPLACED.get(e, START) and False:
                continue
            ut.append(dict(survey=s.strftime("%Y-%m-%d"), element=e,
                           min_wall_mm=round(float(wall(e, pd.DatetimeIndex([s]))[0] + rng.normal(0, 0.04)), 2)))
    return h, summ, pd.DataFrame(ut)


def measure(e, test, rng):
    """Outage measurement at the crown, 2026-10-31."""
    op = operation()
    if test == "oxide-ut":
        x = history(e, op).oxide.iloc[-1]
        return dict(element=e, test=test, oxide_um=round(float(x + rng.normal(0, 2.0)), 0))
    h = wall(e, pd.DatetimeIndex([END]))[0]
    return dict(element=e, test=test, min_wall_mm=round(float(h + rng.normal(0, 0.04)), 2))
