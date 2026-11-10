"""Sealed definition for the gas turbine performance test task: unit GT-1, a single-shaft heavy-duty gas turbine
driving a 13.8 kV, 60 Hz generator, at a site 310 m above sea level. Performance tests on 2026-10-13 (as found) and,
after an offline compressor wash and an inlet filter change on 2026-10-14, on 2026-10-15 (as left).

Truth: in each condition the machine's corrected output and heat rate at the contract reference conditions are
STATE[cond]. At any operating point, the generator output at reference power factor is
P_ref x prod(f_i(conditions)) and the heat rate (heat input / output at reference power factor) is
HR_ref x prod(g_i(conditions)), with the OEM correction curves below; the output at the terminals at the actual power
factor differs by the generator loss difference. Heat input = fuel mass flow x (LHV + cp_f (T_fuel - 15)).

The records differ from the truth (simulate()): see FAULTS.
"""
import numpy as np
import pandas as pd

ELEV_M = 310.0
REF = dict(cit=15.0, p_kpa=101.325, rh=60.0, dp_in=1.00, dp_ex=3.00, pf=0.85)
STATE = {"as_found": dict(p_mw=41.62, hr=10923.0), "as_left": dict(p_mw=42.81, hr=10702.0)}
CP_FUEL = 2.20          # kJ/kg K, natural gas, procedure value
GEN_L0, GEN_K, GEN_S = 410.0, 560.0, 56.0      # generator losses kW = L0 + K (S/GEN_S)^2, S in MVA

# ---- OEM correction curves (factor = value at the condition / value at reference) ----
def f_cit(t):
    d = t - 15.0
    return 1.0 - 0.00720 * d - 0.000035 * d * d


def g_cit(t):
    d = t - 15.0
    return 1.0 + 0.00210 * d + 0.000020 * d * d


def f_p(p_kpa):
    return p_kpa / 101.325


def f_hum(w):
    return 1.0 + 0.30 * (w - W_REF)


def g_hum(w):
    return 1.0 - 0.04 * (w - W_REF)


def f_in(dp):
    return 1.0 - 0.0145 * (dp - 1.00)


def g_in(dp):
    return 1.0 + 0.0050 * (dp - 1.00)


def f_ex(dp):
    return 1.0 - 0.0055 * (dp - 3.00)


def g_ex(dp):
    return 1.0 + 0.0050 * (dp - 3.00)


def psat_kpa(t):
    T = np.asarray(t, float) + 273.15
    return np.exp(-5.8002206e3 / T + 1.3914993 - 4.8640239e-2 * T + 4.1764768e-5 * T ** 2
                  - 1.4452093e-8 * T ** 3 + 6.5459673 * np.log(T)) / 1000.0


def spec_hum(t, rh, p_kpa):
    pv = rh / 100.0 * psat_kpa(t)
    return 0.621945 * pv / (p_kpa - pv)


W_REF = float(spec_hum(15.0, 60.0, 101.325))


def gen_loss_kw(p_kw, pf):
    s = p_kw / 1000.0 / pf
    return GEN_L0 + GEN_K * (s / GEN_S) ** 2


def qnh_from_station(p_kpa):
    return p_kpa / (1.0 - 2.25577e-5 * ELEV_M) ** 5.25588


# ---- fuel ----
COMP = ["CH4", "C2H6", "C3H8", "iC4H10", "nC4H10", "iC5H12", "nC5H12", "nC6H14", "N2", "CO2", "O2"]
MOLAR_MASS = dict(CH4=16.043, C2H6=30.069, C3H8=44.096, iC4H10=58.122, nC4H10=58.122, iC5H12=72.149, nC5H12=72.149,
                  nC6H14=86.175, N2=28.0135, CO2=44.010, O2=31.9988)
HN_MOLAR = dict(CH4=802.69, C2H6=1428.84, C3H8=2043.37, iC4H10=2648.42, nC4H10=2657.60, iC5H12=3265.08,
                nC5H12=3272.00, nC6H14=3887.21, N2=0.0, CO2=0.0, O2=0.0)            # kJ/mol, net, 15 C
HS_MOLAR = dict(CH4=891.51, C2H6=1562.14, C3H8=2221.10, iC4H10=2870.58, nC4H10=2879.76, iC5H12=3531.68,
                nC5H12=3538.60, nC6H14=4198.24, N2=0.0, CO2=0.0, O2=0.0)            # kJ/mol, gross, 15 C
GAS = {"2026-10-13": dict(CH4=0.9342, C2H6=0.0361, C3H8=0.0079, iC4H10=0.0014, nC4H10=0.0016, iC5H12=0.0004,
                          nC5H12=0.0003, nC6H14=0.0003, N2=0.0118, CO2=0.0060, O2=0.0),
       "2026-10-15": dict(CH4=0.9297, C2H6=0.0392, C3H8=0.0088, iC4H10=0.0016, nC4H10=0.0018, iC5H12=0.0005,
                          nC5H12=0.0004, nC6H14=0.0003, N2=0.0115, CO2=0.0062, O2=0.0)}


def lhv_mass(x):
    return sum(x[c] * HN_MOLAR[c] for c in COMP) / sum(x[c] * MOLAR_MASS[c] for c in COMP)       # kJ/g = MJ/kg


# ---- the test days ----
DAYS = {"2026-10-13": "as_found", "2026-10-15": "as_left"}
RUNS = [("A1", "2026-10-13 09:00", "2026-10-13 10:00"), ("A2", "2026-10-13 10:30", "2026-10-13 11:30"),
        ("L1", "2026-10-15 09:00", "2026-10-15 10:00"), ("L2", "2026-10-15 10:30", "2026-10-15 11:30"),
        ("L3", "2026-10-15 13:00", "2026-10-15 14:00")]
FAULTS = dict(
    pt_ratio=(14400.0, 13800.0),           # test wattmeter programmed 14400:120; the PTs are 13800:120
    qnh_from="2026-10-14",                 # met logger replaced 10-14: the new one reports QNH, not station pressure
    cit_bias={"2026-10-13": 0.0, "2026-10-15": 1.20},   # inlet RTD array reads high on day 2 (shared DAS card reference)
    pt102_zero=-0.60,                      # PT-102 reads 0.60 kPa low, both days (seen at standstill against the barometer)
    dcs_mw_gain=0.985,                     # DCS generator MW transducer reads 1.5 % low
    fuel_zero={"2026-10-13": 0.0010, "2026-10-15": 0.0340},   # Coriolis zero error, seen in each day's pre-start readings
    gc_air=("2026-10-15 10:15", 0.040),   # one as-left gas sample contaminated with 4 % air
    a2_freq_event=("2026-10-13 10:30", 20, 0.060),   # grid frequency event: A2 output 6 % low for its first 20 min
    l3_part_load=True,                     # L3 held at 38 MW by dispatch: not on temperature control, IGVs closed
)
DP_IN = {"as_found": 1.31, "as_left": 0.94}            # true total inlet loss, kPa (filters replaced 10-14)
DP_FILT = {"as_found": 0.62, "as_left": 0.27}          # filter-stage dp only (PDT-101)
DP_EX = 3.42


def truth_table():
    return {k: dict(v) for k, v in STATE.items()}


def minutes(day):
    return pd.date_range(day + " 06:00", day + " 15:00", freq="min")


def simulate(seed=21):
    rng = np.random.default_rng(seed)
    das, dcs, gc, spot = [], [], [], {}
    for day, cond in DAYS.items():
        t = minutes(day); n = len(t)
        hr_of_day = (t.hour + t.minute / 60.0).values
        base_t = {"2026-10-13": 11.0, "2026-10-15": 13.5}[day]
        tamb = base_t + 7.0 * np.sin(np.pi * (hr_of_day - 6.0) / 14.0) + np.cumsum(rng.normal(0, 0.02, n))
        rh = np.clip(82 - 3.2 * (tamb - base_t) + rng.normal(0, 0.6, n), 30, 98)
        p = {"2026-10-13": 97.72, "2026-10-15": 97.41}[day] + 0.0006 * np.arange(n) * (1 if day.endswith("13") else -1) \
            + rng.normal(0, 0.004, n)
        cit = tamb + 0.30
        w = spec_hum(tamb, rh, p)
        dp_in = DP_IN[cond] * (1 + rng.normal(0, 0.01, n))
        dp_ex = DP_EX * (1 + rng.normal(0, 0.01, n))
        pf = np.clip(0.985 + rng.normal(0, 0.002, n), 0.97, 1.0)
        st = STATE[cond]
        p_ref = st["p_mw"] * 1000 * f_cit(cit) * f_p(p) * f_hum(w) * f_in(dp_in) * f_ex(dp_ex)    # kW at ref PF
        hr = st["hr"] * g_cit(cit) * g_hum(w) * g_in(dp_in) * g_ex(dp_ex)
        on_tc = np.ones(n, bool)
        load = np.ones(n)
        tt = pd.DatetimeIndex(t)
        # A2: grid frequency event, output held low while the governor recovers
        if day == "2026-10-13":
            s = pd.Timestamp(FAULTS["a2_freq_event"][0])
            ev = (tt >= s) & (tt < s + pd.Timedelta(minutes=FAULTS["a2_freq_event"][1]))
            load = np.where(ev, 1 - FAULTS["a2_freq_event"][2], load)
            on_tc = on_tc & ~ev
        # L3 at 38 MW by dispatch from 12:40 to 14:20
        if day == "2026-10-15":
            pl = (tt >= pd.Timestamp("2026-10-15 12:40")) & (tt < pd.Timestamp("2026-10-15 14:20"))
            load = np.where(pl, 38000.0 / p_ref, load)
            on_tc = on_tc & ~pl
        p_ref_actual = p_ref * load
        # part load raises the heat rate (approximate part-load curve, not a correction the procedure applies)
        hr_actual = hr * (1 + 0.55 * (1 - load) ** 1.3)
        hi_kw = hr_actual * p_ref_actual / 3600.0
        # terminal output at the actual power factor
        p_term = p_ref_actual.copy()
        for _ in range(4):
            p_term = p_ref_actual + gen_loss_kw(p_term, REF["pf"]) - gen_loss_kw(p_term, pf)
        q_kvar = p_term * np.tan(np.arccos(pf))
        x = GAS[day]
        lhv = lhv_mass(x) * 1000.0                         # kJ/kg
        t_fuel = 210.0 + rng.normal(0, 0.4, n)            # after the fuel heater (TE-305)
        m_fuel = hi_kw / (lhv + CP_FUEL * (t_fuel - 15.0))    # kg/s
        # zero check before the test: fuel isolated 06:40-06:55, nothing burnt (unit not yet started)
        running = (tt >= pd.Timestamp(day + " 07:30"))
        zc = (tt >= pd.Timestamp(day + " 06:40")) & (tt < pd.Timestamp(day + " 06:55"))
        m_true = np.where(running, m_fuel, 0.0)
        # start-up ramp 07:30-08:15
        ramp = np.clip((tt - pd.Timestamp(day + " 07:30")) / pd.Timedelta(minutes=45), 0, 1)
        ramp = np.asarray(ramp, float)
        p_term = np.where(running, p_term * ramp, 0.0)
        q_kvar = np.where(running, q_kvar * ramp, 0.0)
        m_true = m_true * np.where(running, 0.25 + 0.75 * ramp, 0.0)
        on_tc = on_tc & (ramp >= 1)
        lr = np.clip(load * ramp, 0, 1)
        flowfrac = np.where(running, 0.3 + 0.7 * ramp, 0.0)          # compressor air flow relative to base load
        cit_now = tamb + 0.30 * flowfrac
        noon = int(np.flatnonzero(tt == pd.Timestamp(day + " 12:00"))[0])
        spot[day] = round(float(cit_now[noon] + rng.normal(0, 0.03)), 1)
        igv = np.where(on_tc, 86.0, np.where(running, 57.0 + 29.0 * lr ** 3, 34.0)) + rng.normal(0, 0.05, n)
        ttrf = np.full(n, 548.0)
        texh = np.where(on_tc, ttrf + rng.normal(0, 0.6, n), np.where(running, ttrf - 200.0 * (1 - lr), 40.0))
        # ---- records (test DAS, 1-min averages) ----
        k_pt = FAULTS["pt_ratio"][0] / FAULTS["pt_ratio"][1]
        rec = dict(time=t.strftime("%Y-%m-%d %H:%M"))
        rec["gen_mw_jt001"] = np.round(p_term / 1000.0 * k_pt * (1 + rng.normal(0, 0.0008, n)), 3)
        rec["gen_mvar_jt001"] = np.round(q_kvar / 1000.0 * k_pt * (1 + rng.normal(0, 0.002, n)), 3)
        rec["freq_hz"] = np.round(np.where(running, 60.0 + rng.normal(0, 0.006, n), 0.0), 3)
        for i in range(1, 9):
            v = cit_now + rng.normal(0, 0.06, n) + FAULTS["cit_bias"][day]
            rec["cit_%d_c" % i] = np.round(v, 2)
        ff2 = flowfrac ** 2
        rec["pdt101_filter_dp_kpa"] = np.round(DP_FILT[cond] * (dp_in / DP_IN[cond]) * ff2 + rng.normal(0, 0.004, n), 3)
        rec["pt102_inlet_total_kpa_abs"] = np.round(p - dp_in * ff2 + FAULTS["pt102_zero"] + rng.normal(0, 0.005, n), 3)
        rec["pdt201_exhaust_kpa_g"] = np.round(dp_ex * ff2 + rng.normal(0, 0.006, n), 3)
        rec["fuel_coriolis_kg_s"] = np.round(m_true * (1 + rng.normal(0, 0.0015, n)) + FAULTS["fuel_zero"][day] + rng.normal(0, 0.0004, n), 4)
        rec["te301_fuel_meter_c"] = np.round(24.0 + rng.normal(0, 0.2, n), 1)
        rec["te305_fuel_skid_c"] = np.round(np.where(running, t_fuel, 24.0), 1)
        rec["igv_deg"] = np.round(igv, 1)
        rec["texh_avg_c"] = np.round(texh, 1)
        rec["ttrf_c"] = np.round(ttrf + rng.normal(0, 0.1, n), 1)
        das.append(pd.DataFrame(rec))
        # ---- DCS (1-min) and met ----
        met_p = qnh_from_station(p) if day >= FAULTS["qnh_from"] else p
        aux = np.where(running, 610.0 + rng.normal(0, 8, n), 180.0)
        dcs.append(pd.DataFrame(dict(time=t.strftime("%Y-%m-%d %H:%M"),
                                     gen_mw_dcs=np.round(p_term / 1000.0 * FAULTS["dcs_mw_gain"] * (1 + rng.normal(0, 0.004, n)), 2),
                                     unit_net_mw=np.round((p_term - aux) / 1000.0 * (1 + rng.normal(0, 0.002, n)), 2),
                                     gen_kv_dcs=np.round(np.where(running, 13.80 * (1 + rng.normal(0, 0.002, n)), 0.0), 2),
                                     met_dry_bulb_c=np.round(tamb + rng.normal(0, 0.05, n), 2),
                                     met_rh_pct=np.round(rh + rng.normal(0, 0.3, n), 1),
                                     met_baro_hpa=np.round(met_p * 10.0 + rng.normal(0, 0.03, n), 1))))
        # ---- gas samples ----
        for hhmm in ("08:30", "10:15", "11:45"):
            xx = dict(x)
            stamp = day + " " + hhmm
            if stamp == FAULTS["gc_air"][0]:
                a = FAULTS["gc_air"][1]
                xx = {c: v * (1 - a) for c, v in xx.items()}
                xx["N2"] += a * 0.7809 + a * 0.0093       # argon reported with nitrogen
                xx["O2"] += a * 0.2095
            xx = {c: v + rng.normal(0, 0.00003) if v > 0 else v for c, v in xx.items()}
            s = sum(xx.values()); xx = {c: v / s for c, v in xx.items()}
            hs = sum(xx[c] * HS_MOLAR[c] for c in COMP) * 101.325 / (8.314462618 * 288.15) / 0.9976   # MJ/m3 approx
            row = dict(sample_time=stamp, **{c: round(xx[c] * 100, 4) for c in COMP})
            row["gross_cv_mj_m3_15_15"] = round(hs, 2)
            gc.append(row)
    return pd.concat(das, ignore_index=True), pd.concat(dcs, ignore_index=True), pd.DataFrame(gc), spot
