"""Sealed simulator for the turbine-tool task: GT-1 performance test record sets written from a test specification.

Truth: in each test the machine's corrected output and heat rate at the contract reference conditions are
spec["p_mw"], spec["hr"]. At any operating point the generator output at the reference power factor is
P_ref x prod(f_i(conditions)) and the heat rate is HR_ref x prod(g_i(conditions)), with the OEM correction functions
below (the OEM tables in the documents tabulate them). The instruments are sound; the record sets differ only in the
documented format variants (barometer and fuel flow units, missing minutes, a failed RTD channel, aborted runs,
optional gas components) and, in the hidden sets, instrument zero errors (pt102_zero, fuel_zero) and an RTD array bias
(rtd_bias) that the procedure's standstill verification reveals.
"""
import numpy as np
import pandas as pd

ELEV_M = 310.0
REF_PF = 0.85
CP_FUEL = 2.20
GEN_L0, GEN_K, GEN_S = 410.0, 560.0, 56.0


CIT_PTS = np.arange(-5.0, 40.1, 5.0)
CIT_F = np.round(1.0 - 0.00720 * (CIT_PTS - 15) - 0.000035 * (CIT_PTS - 15) ** 2, 4)    # the OEM table values
CIT_G = np.round(1.0 + 0.00210 * (CIT_PTS - 15) + 0.000020 * (CIT_PTS - 15) ** 2, 4)


def lin(x, xs, ys):
    """Piecewise-linear through the table, extrapolated linearly from the end segments."""
    x = np.asarray(x, float)
    y = np.interp(x, xs, ys)
    lo, hi = x < xs[0], x > xs[-1]
    y = np.where(lo, ys[0] + (x - xs[0]) * (ys[1] - ys[0]) / (xs[1] - xs[0]), y)
    y = np.where(hi, ys[-1] + (x - xs[-1]) * (ys[-1] - ys[-2]) / (xs[-1] - xs[-2]), y)
    return y


def f_cit(t):
    return lin(t, CIT_PTS, CIT_F)


def g_cit(t):
    return lin(t, CIT_PTS, CIT_G)


def psat_kpa(t):
    T = np.asarray(t, float) + 273.15
    return np.exp(-5.8002206e3 / T + 1.3914993 - 4.8640239e-2 * T + 4.1764768e-5 * T ** 2
                  - 1.4452093e-8 * T ** 3 + 6.5459673 * np.log(T)) / 1000.0


def spec_hum(t, rh, p_kpa):
    pv = rh / 100.0 * psat_kpa(t)
    return 0.621945 * pv / (p_kpa - pv)


W_REF = float(spec_hum(15.0, 60.0, 101.325))


def f_hum(w):
    return 1.0 + 0.30 * (np.asarray(w, float) - W_REF)


def g_hum(w):
    return 1.0 - 0.04 * (np.asarray(w, float) - W_REF)


def f_in(dp):
    return 1.0 - 0.0145 * (np.asarray(dp, float) - 1.00)


def g_in(dp):
    return 1.0 + 0.0050 * (np.asarray(dp, float) - 1.00)


def f_ex(dp):
    return 1.0 - 0.0055 * (np.asarray(dp, float) - 3.00)


def g_ex(dp):
    return 1.0 + 0.0050 * (np.asarray(dp, float) - 3.00)


def gen_loss_kw(p_kw, pf):
    return GEN_L0 + GEN_K * (np.asarray(p_kw, float) / 1000.0 / pf / GEN_S) ** 2


COMP = ["CH4", "C2H6", "C3H8", "iC4H10", "nC4H10", "neoC5H12", "iC5H12", "nC5H12", "nC6H14", "H2", "He", "N2", "CO2",
        "O2"]
HN = dict(CH4=802.69, C2H6=1428.84, C3H8=2043.37, iC4H10=2648.42, nC4H10=2657.60, neoC5H12=3250.48, iC5H12=3265.08,
          nC5H12=3272.00, nC6H14=3887.21, H2=241.72, He=0.0, N2=0.0, CO2=0.0, O2=0.0)
HS = dict(CH4=891.51, C2H6=1562.14, C3H8=2221.10, iC4H10=2870.58, nC4H10=2879.76, neoC5H12=3517.27, iC5H12=3531.68,
          nC5H12=3538.60, nC6H14=4198.24, H2=286.15, He=0.0, N2=0.0, CO2=0.0, O2=0.0)
MM = dict(CH4=16.043, C2H6=30.069, C3H8=44.096, iC4H10=58.122, nC4H10=58.122, neoC5H12=72.149, iC5H12=72.149,
          nC5H12=72.149, nC6H14=86.175, H2=2.016, He=4.0026, N2=28.0135, CO2=44.010, O2=31.9988)
BASE_GAS = dict(CH4=0.9342, C2H6=0.0361, C3H8=0.0079, iC4H10=0.0014, nC4H10=0.0016, iC5H12=0.0004, nC5H12=0.0003,
                nC6H14=0.0003, N2=0.0118, CO2=0.0060)


def lhv_mass(x):
    return sum(x.get(c, 0.0) * HN[c] for c in COMP) / sum(x.get(c, 0.0) * MM[c] for c in COMP)     # MJ/kg


def gas(**changes):
    """Base composition with the given mole fractions set; methane takes up the balance."""
    x = dict(BASE_GAS)
    x.update(changes)
    x["CH4"] = 0.0
    x["CH4"] = 1.0 - sum(x.values())
    return x


def simulate(spec, seed):
    """Records of one test day from its specification: das, dcs, gas analysis, log (DataFrames)."""
    rng = np.random.default_rng(seed)
    day = spec["date"]
    t = pd.date_range(day + " 07:00", day + " 15:00", freq="min")
    n = len(t)
    tt = pd.DatetimeIndex(t)
    hr_of_day = (tt.hour + tt.minute / 60.0).values
    tamb = spec["tamb"] + spec.get("tamb_amp", 5.0) * np.sin(np.pi * (hr_of_day - 6.0) / 14.0) \
        + np.cumsum(rng.normal(0, 0.015, n))
    rh = np.clip(spec.get("rh", 65.0) - 2.5 * (tamb - spec["tamb"]) + rng.normal(0, 0.5, n), 8, 99)
    p = spec["p_kpa"] + 0.0004 * np.arange(n) * spec.get("p_trend", 1) + rng.normal(0, 0.004, n)
    # operating schedule: (start, stop) pairs, "HH:MM" or None (before the record / after it)
    running = np.zeros(n, bool)
    ramp = np.zeros(n)
    coast = np.zeros(n)                                    # rotor speed fraction after a stop
    mins = ((tt - pd.Timestamp(day + " 00:00")) / pd.Timedelta(minutes=1)).values
    for a, b in spec.get("schedule", [("07:30", None)]):
        ta = -1e9 if a is None else float(int(a[:2]) * 60 + int(a[3:]))
        tb = 1e9 if b is None else float(int(b[:2]) * 60 + int(b[3:]))
        on = (mins > ta) & (mins <= tb)                    # interval-end stamps: the minute after the start
        running |= on
        ramp = np.where(on, np.clip((mins - ta) / 45.0, 0, 1), ramp)
        after = mins > tb
        coast = np.where(after & ~running, np.maximum(coast, np.exp(-np.clip(mins - tb, 0, 1e4) / 8.0)), coast)
    speed = np.where(running, np.clip(ramp * 3.0, 0, 1) * 100.0, np.maximum(coast * 100.0, 0.2))
    flowfrac = np.where(running, 0.3 + 0.7 * ramp, coast)
    cit = tamb + 0.30 * flowfrac
    w = spec_hum(tamb, rh, p)
    dp_in = spec["dp_in"] * (1 + rng.normal(0, 0.01, n))
    dp_ex = spec["dp_ex"] * (1 + rng.normal(0, 0.01, n))
    pf = np.clip(spec["pf"] + rng.normal(0, 0.002, n), 0.80, 0.9999)
    p_ref = spec["p_mw"] * 1000 * f_cit(cit) * (p / 101.325) * f_hum(w) * f_in(dp_in) * f_ex(dp_ex)
    hr = spec["hr"] * g_cit(cit) * g_hum(w) * g_in(dp_in) * g_ex(dp_ex)
    load = np.ones(n)
    on_tc = np.ones(n, bool)
    igv_open = np.zeros(n, bool)
    for kind, a, b, frac in spec.get("events", []):
        sel = (tt >= pd.Timestamp(day + " " + a)) & (tt < pd.Timestamp(day + " " + b))
        load = np.where(sel, frac, load)
        on_tc &= ~sel
        if kind == "limit":                     # held on a fuel supply pressure limit: IGVs stay open
            igv_open |= sel
    pr = p_ref * load
    hra = hr * (1 + 0.55 * (1 - load) ** 1.3)
    hi = hra * pr / 3600.0
    p_term = pr.copy()
    for _ in range(4):
        p_term = pr + gen_loss_kw(p_term, REF_PF) - gen_loss_kw(p_term, pf)
    sign = -1.0 if spec.get("leading") else 1.0
    q = sign * p_term * np.tan(np.arccos(pf))
    x = spec["gas"]
    lhv = lhv_mass(x) * 1000.0
    t_fuel = spec.get("t_fuel", 210.0) + rng.normal(0, 0.4, n)
    m = hi / (lhv + CP_FUEL * (t_fuel - 15.0))
    p_term = np.where(running, p_term * ramp, 0.0)
    q = np.where(running, q * ramp, 0.0)
    m = np.where(running, m * (0.25 + 0.75 * ramp), 0.0)
    on_tc &= ramp >= 1
    lr = np.clip(load * ramp, 0, 1)
    igv = np.where(on_tc | igv_open, 86.0, np.where(running, 57.0 + 29.0 * lr ** 3, 34.0)) + rng.normal(0, 0.05, n)
    ttrf = np.full(n, 548.0)
    texh = np.where(on_tc, ttrf + rng.normal(0, 0.6, n), np.where(running, ttrf - 200.0 * (1 - lr), 40.0))
    ff2 = flowfrac ** 2
    das = dict(time=tt.strftime("%Y-%m-%d %H:%M"))
    das["gen_mw_jt001"] = np.round(p_term / 1000.0 * (1 + rng.normal(0, 0.0008, n)), 3)
    das["gen_mvar_jt001"] = np.round(q / 1000.0 * (1 + rng.normal(0, 0.002, n)), 3)
    das["freq_hz"] = np.round(np.where(running, 60.0 + rng.normal(0, 0.006, n), 0.0), 3)
    das["speed_pct"] = np.round(speed + np.where(speed > 1, rng.normal(0, 0.02, n), 0.0), 2)
    bad = spec.get("failed_rtd")
    for i in range(1, 9):
        v = np.round(cit + spec.get("rtd_bias", 0.0) + spec.get("rtd_chan_bias", {}).get(i, 0.0)
                     + rng.normal(0, 0.06, n), 2)
        stuck = spec.get("stuck_rtd")               # transmitter frozen at an earlier reading: not flagged by the DAS
        if stuck and stuck[0] == i:
            v = np.full(n, stuck[1])
        if bad and bad[0] == i:
            v = np.where(tt >= pd.Timestamp(day + " " + bad[1]), -999.0, v)
        das["cit_%d_c" % i] = v
    das["pdt101_filter_dp_kpa"] = np.round(0.45 * dp_in / spec["dp_in"] * ff2 + rng.normal(0, 0.004, n), 3)
    das["pt102_inlet_total_kpa_abs"] = np.round(p - dp_in * ff2 + spec.get("pt102_zero", 0.0) + rng.normal(0, 0.005, n), 3)
    das["pdt201_exhaust_kpa_g"] = np.round(dp_ex * ff2 + rng.normal(0, 0.006, n), 3)
    mf = m * (1 + rng.normal(0, 0.0015, n)) + rng.normal(0, 0.0003, n) + spec.get("fuel_zero", 0.0)
    if spec.get("line_pack", 0.4):             # fuel lines downstream of FT-301 purged and packed before each start
        for a, b in spec.get("schedule", [("07:30", None)]):
            if a is not None:
                ta = float(int(a[:2]) * 60 + int(a[3:]))
                pk = (mins >= ta - 3) & (mins < ta - 1)
                mf = mf + np.where(pk, spec.get("line_pack", 0.4) * (1 + rng.normal(0, 0.05, n)), 0.0)
    for a, b, k in spec.get("fuel_bias", []):          # a meter alarm that got a run aborted
        mf = np.where((tt >= pd.Timestamp(day + " " + a)) & (tt < pd.Timestamp(day + " " + b)), mf * k, mf)
    if spec.get("fuel_unit") == "kg_h":
        das["fuel_coriolis_kg_h"] = np.round(mf * 3600.0, 1)
    else:
        das["fuel_coriolis_kg_s"] = np.round(mf, 4)
    das["te301_fuel_meter_c"] = np.round(spec.get("t_meter", 22.0) + rng.normal(0, 0.2, n), 1)
    das["te305_fuel_skid_c"] = np.round(np.where(running, t_fuel, spec.get("t_meter", 22.0)), 1)
    das["igv_deg"] = np.round(igv, 1)
    das["texh_avg_c"] = np.round(texh, 1)
    das["ttrf_c"] = np.round(ttrf + rng.normal(0, 0.1, n), 1)
    das = pd.DataFrame(das)
    dcs = dict(time=tt.strftime("%Y-%m-%d %H:%M"),
               gen_mw_dcs=np.round(p_term / 1000.0 * (1 + rng.normal(0, 0.004, n)), 2),
               met_dry_bulb_c=np.round(tamb + rng.normal(0, 0.05, n), 2),
               met_rh_pct=np.round(rh + rng.normal(0, 0.3, n), 1))
    if spec.get("baro_unit") == "kpa":
        dcs["met_baro_kpa"] = np.round(p + rng.normal(0, 0.003, n), 3)
    else:
        dcs["met_baro_hpa"] = np.round(p * 10.0 + rng.normal(0, 0.03, n), 1)
    dcs = pd.DataFrame(dcs)
    keep = np.ones(n, bool)
    for a, b in spec.get("gaps", []):
        keep &= ~((tt >= pd.Timestamp(day + " " + a)) & (tt < pd.Timestamp(day + " " + b)))
    das = das[keep].reset_index(drop=True)
    comps = [c for c in COMP if c in x or c in ("O2",)]
    rows = []
    for stamp, xprev in spec.get("prior_samples", []):           # retained samples of an earlier day in the file
        xx = {c: xprev.get(c, 0.0) for c in comps}
        s = sum(xx.values())
        xx = {c: v / s for c, v in xx.items()}
        hs = sum(xx[c] * HS[c] for c in comps) * 101.325 / (8.314462618 * 288.15) / 0.9976
        rows.append(dict(sample_time=stamp, **{c: round(xx[c] * 100, 4) for c in comps}, gross_cv_mj_m3_15_15=round(hs, 2)))
    for hhmm in spec.get("samples", ("08:30", "10:15", "11:45")):
        xx = {c: max(0.0, x.get(c, 0.0) + (rng.normal(0, 0.00003) if x.get(c, 0.0) > 0 else 0.0)) for c in comps}
        s = sum(xx.values())
        xx = {c: v / s for c, v in xx.items()}
        hs = sum(xx[c] * HS[c] for c in comps) * 101.325 / (8.314462618 * 288.15) / 0.9976
        row = dict(sample_time=day + " " + hhmm, **{c: round(xx[c] * 100, 4) for c in comps})
        row["gross_cv_mj_m3_15_15"] = round(hs, 2)
        rows.append(row)
    log = []
    for a, b in spec.get("schedule", [("07:30", None)]):
        if a is None:
            log.append((day + " 07:00", "GT-1 in service at base load from the night shift"))
        else:
            log.append((day + " " + a, "GT-1 start"))
            h, mm = int(a[:2]), int(a[3:]) + 45
            log.append((day + " %02d:%02d" % (h + mm // 60, mm % 60), "GT-1 at base load"))
        if b is not None:
            log.append((day + " " + b, "GT-1 tripped (fuel gas supply pressure low)"))
    for name, a, b, status in spec["runs"]:
        log.append((day + " " + a, "Run %s start" % name))
        if status == "aborted":
            log.append((day + " " + b, "Run %s aborted" % name))
        else:
            log.append((day + " " + b, "Run %s end" % name))
    for hhmm in spec.get("samples", ("08:30", "10:15", "11:45")):
        log.append((day + " " + hhmm, "Gas sample drawn at the fuel skid sample point"))
    log.append((day + " 15:00", "Data acquisition stopped"))
    log.sort(key=lambda r: r[0])
    return das, dcs, pd.DataFrame(rows), pd.DataFrame(log, columns=["time", "entry"])


R3 = [("1", "09:00", "10:00", "ok"), ("2", "10:30", "11:30", "ok"), ("3", "12:30", "13:30", "ok")]

TESTS = {
    # shipped examples
    "example_2025-04-09": dict(date="2025-04-09", p_mw=42.37, hr=10811.0, tamb=11.0, p_kpa=97.85, dp_in=1.05,
                               dp_ex=3.30, pf=0.985, gas=gas(), runs=R3, seed=101),
    "example_2026-03-18": dict(date="2026-03-18", p_mw=41.93, hr=10874.0, tamb=7.5, p_kpa=98.21, dp_in=1.18,
                               dp_ex=3.35, pf=0.96, gas=gas(C2H6=0.042), runs=R3, seed=102),
    # hidden
    "h1": dict(date="2025-01-22", p_mw=42.64, hr=10763.0, tamb=-12.5, tamb_amp=3.0, rh=78, p_kpa=98.65, dp_in=0.98,
               dp_ex=3.10, pf=0.975, gas=gas(), runs=R3, baro_unit="kpa", schedule=[(None, None)], seed=201),
    "h2": dict(date="2025-07-15", p_mw=41.28, hr=10992.0, tamb=24.0, tamb_amp=4.0, rh=55, p_kpa=97.55, dp_in=1.22,
               dp_ex=3.45, pf=0.99, gas=gas(), runs=R3, gaps=[("09:12", "09:15"), ("10:44", "10:46")],
               events=[("limit", "10:25", "10:47", 0.95)], rtd_bias=0.9, seed=202),
    "h3": dict(date="2025-10-02", p_mw=41.87, hr=10871.0, tamb=14.0, p_kpa=97.70, dp_in=1.10, dp_ex=3.25, pf=0.98,
               gas=gas(H2=0.080), runs=R3, fuel_unit="kg_h",
               prior_samples=[("2025-10-01 09:00", gas()), ("2025-10-01 12:00", gas()), ("2025-10-01 15:00", gas())],
               fuel_zero=0.028, seed=203),
    "h4": dict(date="2025-11-19", p_mw=41.55, hr=10930.0, tamb=6.0, p_kpa=98.05, dp_in=1.15, dp_ex=3.30, pf=0.97,
               gas=gas(), runs=[("1", "09:00", "10:00", "ok"), ("2", "10:30", "11:10", "aborted"),
                                ("3", "12:30", "13:30", "ok")],
               fuel_bias=[("10:25", "11:10", 1.03)], failed_rtd=(3, "08:40"), rtd_chan_bias={3: 6.0}, pt102_zero=0.35,
               seed=204),
    "h5": dict(date="2026-02-11", p_mw=42.12, hr=10842.0, tamb=3.0, p_kpa=98.40, dp_in=1.02, dp_ex=3.20, pf=0.90,
               gas=gas(C2H6=0.092, C3H8=0.018), schedule=[(None, "11:50"), ("12:50", None)],
               runs=[("1", "08:00", "09:00", "ok"), ("2", "09:30", "10:30", "ok"), ("3", "13:40", "14:40", "ok")],
               rtd_bias=-1.0, fuel_zero=-0.022, seed=205),
    "h6": dict(date="2026-05-06", p_mw=42.95, hr=10688.0, tamb=16.0, p_kpa=97.60, dp_in=0.92, dp_ex=3.15, pf=0.97,
               leading=True, gas=gas(), runs=R3, events=[("limit", "08:50", "09:40", 0.95)], pt102_zero=-0.5,
               rtd_bias=0.7, seed=206),
    "h7": dict(date="2026-08-04", p_mw=41.02, hr=11047.0, tamb=27.0, tamb_amp=8.0, rh=45, p_kpa=97.45, dp_in=1.30,
               dp_ex=3.55, pf=0.99, gas=gas(), runs=R3, gaps=[("09:20", "09:22")], baro_unit="kpa", fuel_zero=0.035,
               stuck_rtd=(5, 22.41),
               seed=207),
    "h8": dict(date="2026-09-23", p_mw=42.48, hr=10790.0, tamb=19.0, p_kpa=97.80, dp_in=1.05, dp_ex=3.25, pf=0.98,
               gas=gas(H2=0.040, He=0.005, neoC5H12=0.0002), runs=R3, fuel_unit="kg_h", failed_rtd=(7, "07:00"),
               rtd_bias=0.8, seed=208),
}
EXAMPLES = [k for k in TESTS if k.startswith("example")]
HIDDEN = [k for k in TESTS if not k.startswith("example")]


def truth(name):
    s = TESTS[name]
    return dict(output_mw=s["p_mw"], heat_rate=s["hr"])
