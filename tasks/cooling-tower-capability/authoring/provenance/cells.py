"""Sealed definition for cooling-tower-capability: cooling tower CT-2, eight induced-draft counterflow cells C1..C8
in a row, west (C1) to east (C8). Hourly records 2026-04-01 00:00 to 2026-09-30 23:00 (plant time).

Each cell's fill follows KaV/L = C (L/G)^-N; its thermal capability is 100 C / C_DESIGN (percent). The graded value
of a cell is its capability at END (CAP; C7's fill scales and its capability falls linearly over the season; C3's
fill is replaced, REFILL_C3). Water mass flow L = riser flow x RHO_W; air mass flow G = rho_in Q, with
Q = Q_DESIGN x A_CELL x speed/100 (fan law), and the fan power P = P_DESIGN x (rho_in/RHO_DESIGN) x
(A_CELL speed/100)^3, so that G = G_DESIGN (P/P_DESIGN)^(1/3) (rho_in/RHO_DESIGN)^(2/3) exactly. The inlet air is the
ambient air, except C8 in westerly wind until its stack was extended (recirculation, RECIRC_K, STACK_C8). Above WIND_LIMIT the cells lose performance
(WIND_LOSS on KaV/L). Cold water from the Merkel integral at the met station's pressure.

What the records show differently from the truth (simulate()): met station in UTC, the DCS in plant time; C1-C4 riser
flows in US gpm; C1's freeze bypass (BYPASS) tees off the header downstream of the header meter and upstream of C1's
riser meter and discharges into C1's basin ahead of the weir, so the header meter counts it, C1's riser meter does not,
and C1's weir temperature is the mix; C3's riser meter reads C3_ZERO high (seen while C3 is isolated, C3_OUT); C6's
riser meter reads C6_FLOW high from its date; C2's replacement hot-water thermocouple reads C2_TH high; C4's replacement
motor's power reading is C4_POWER of the truth; C5's cold-water sensor reads the common flume, the flow-weighted mean of
all eight weirs.
"""
import numpy as np
import pandas as pd
import psy

CELLS = ["C%d" % i for i in range(1, 9)]
START, END = pd.Timestamp("2026-04-01 00:00"), pd.Timestamp("2026-09-30 23:00")
N_EXP = 0.65
RHO_W = 994.0
Q_DESIGN_M3H = 2000.0
LG_DESIGN = 1.30
L_DESIGN = Q_DESIGN_M3H * RHO_W / 3600.0
G_DESIGN = L_DESIGN / LG_DESIGN
P_DESIGN = 160.0                       # kW at 100 % speed and design density
P_DESIGN_PA = 92000.0
DESIGN = dict(th=40.0, tc=30.0, wb=24.0)
KAVL_DESIGN = psy.merkel(40.0, 30.0, LG_DESIGN, psy.hsat(24.0, P_DESIGN_PA), P_DESIGN_PA)
C_DESIGN = KAVL_DESIGN * LG_DESIGN ** N_EXP
RHO_DESIGN = psy.density(24.0, psy.wsat(24.0, P_DESIGN_PA), P_DESIGN_PA)   # saturated inlet at 24 degC

CAP = {"C1": 96.5, "C2": 88.0, "C3": 101.0, "C4": 92.5, "C5": 72.0, "C6": 97.5, "C7": 79.0, "C8": 90.5}   # at END
C3_OLD_CAP, REFILL_C3 = 65.0, pd.Timestamp("2026-07-20")
A_CELL = {"C1": 1.00, "C2": 0.97, "C3": 1.02, "C4": 0.99, "C5": 0.95, "C6": 1.01, "C7": 0.98, "C8": 1.00}
RECIRC_K = 2.0                          # C8 inlet wet bulb above ambient in westerly wind (225-315 deg)
STACK_C8 = pd.Timestamp("2026-06-24 15:00")   # C8 fan stack extended: no recirculation from then
WIND_LIMIT = 4.5                        # m/s; above it the cells lose performance (WIND_LOSS on KaV/L)
WIND_LOSS = 0.75
BYPASS = ("C1", pd.Timestamp("2026-04-14"), 600.0, 240.0)   # C1 freeze bypass (tee on the header upstream of C1's riser meter,
                                                             # discharging into C1's basin above the weir): m3/h open to 04-14, then passing
C3_ZERO = 150.0                         # C3 riser meter reads this many m3/h high (zero shift), whole record
C3_OUT = (pd.Timestamp("2026-07-06 08:00"), pd.Timestamp("2026-07-20 14:00"))   # C3 isolated (riser blanked, fan off)
C7_TREND = (90.0, 79.0)                 # C7 fill scaling: capability falls linearly from START to END
C2_TH = (pd.Timestamp("2026-06-20"), 2.0)                      # replacement C2 hot-water thermocouple reads high
C4_POWER = (pd.Timestamp("2026-06-15"), 0.80)                  # replacement motor: power transducer reads x0.8
C6_FLOW = (pd.Timestamp("2026-06-01"), 1.15)                   # fouled riser meter reads 15 % high from then
GPM_CELLS = ("C1", "C2", "C3", "C4")
FLUME_TC = "C5"                         # C5's cold-water sensor sits in the common outlet flume: it reads the mix of all cells
RISER_BIAS = {"C1": 0.10, "C2": -0.15, "C3": 0.05, "C4": -0.05, "C5": 0.20, "C6": -0.10, "C7": 0.0, "C8": 0.15}   # degC, true
MET_UTC_OFFSET_H = 5                    # met logger keeps UTC; the DCS keeps US Central plant time (CDT, UTC-5, all season)
GPM_PER_M3H = 4.402868


def cap(c, t):
    if c == "C7":
        f = (t - START) / (END - START)
        return C7_TREND[0] + (C7_TREND[1] - C7_TREND[0]) * np.asarray(f, float)
    if c == "C3":
        return np.where(t >= REFILL_C3, CAP["C3"], C3_OLD_CAP)
    return np.full(len(t), CAP[c])


def hours():
    return pd.date_range(START, END, freq="h")


def weather(seed=3):
    rng = np.random.default_rng(seed)
    t = hours(); n = len(t)
    doy = t.dayofyear.values; hr = t.hour.values
    season = np.sin(np.pi * (doy - 91) / 183.0)                    # 0 in April, 1 in early July, 0 in October
    day = np.cumsum(rng.normal(0, 0.35, n)) * 0.0
    synoptic = np.repeat(rng.normal(0, 2.5, n // 24 + 1), 24)[:n]
    tdb = 14 + 13 * season + 5.5 * np.sin(2 * np.pi * (hr - 9) / 24) + synoptic + rng.normal(0, 0.6, n)
    rh = np.clip(62 - 22 * np.sin(2 * np.pi * (hr - 9) / 24) + np.repeat(rng.normal(0, 8, n // 24 + 1), 24)[:n]
                 + rng.normal(0, 3, n), 18, 98)
    p = 92200 + np.repeat(rng.normal(0, 450, n // 24 + 1), 24)[:n] + rng.normal(0, 40, n)
    ws = np.clip(np.abs(4.9 + np.repeat(rng.normal(0, 1.6, n // 6 + 1), 6)[:n] + rng.normal(0, 0.6, n)), 0, 12)
    wd = (250 + np.repeat(rng.normal(0, 70, n // 12 + 1), 12)[:n] + rng.normal(0, 15, n)) % 360
    return pd.DataFrame(dict(time=t, tdb=tdb, rh=rh, p=p, wind_ms=ws, wind_deg=wd))


def operation(seed=5):
    """Per-cell riser flow (m3/h, true), fan speed (%), hot water temperature (true)."""
    rng = np.random.default_rng(seed)
    t = hours(); n = len(t)
    load = np.clip(0.92 + 0.06 * np.sin(2 * np.pi * (t.hour.values - 15) / 24) + np.repeat(rng.normal(0, 0.04, n // 24 + 1), 24)[:n], 0.75, 1.05)
    th = 37.5 + 3.5 * load + rng.normal(0, 0.15, n)
    out = {"time": t, "th": th}
    for c in CELLS:
        valve = np.repeat(rng.uniform(0.86, 1.04, n // 168 + 1), 168)[:n]
        out[c + "_flow"] = Q_DESIGN_M3H * valve * (1 + rng.normal(0, 0.004, n))
        spd = np.where(rng.uniform(0, 1, n // 4 + 1) < 0.18, rng.choice([60.0, 75.0, 85.0], n // 4 + 1), 100.0)
        spd = np.repeat(spd, 4)[:n]
        off = np.repeat(rng.uniform(0, 1, n // 12 + 1) < 0.03, 12)[:n]
        out[c + "_spd"] = np.where(off, 0.0, spd)
    return pd.DataFrame(out)


def truth_table():
    """Graded values: each cell's capability at END (percent of design)."""
    return {c: float(cap(c, pd.DatetimeIndex([END]))[0]) for c in CELLS}


def simulate(seed=11):
    """True hourly state and the DCS records (with their faults)."""
    rng = np.random.default_rng(seed)
    wx = weather(); op = operation()
    t = pd.DatetimeIndex(wx.time); n = len(t)
    wb = psy.wet_bulb(wx.tdb.values, wx.rh.values, wx.p.values)
    w_amb = psy.w_from_rh(wx.tdb.values, wx.rh.values, wx.p.values)
    rho = psy.density(wx.tdb.values, w_amb, wx.p.values)
    rec = {"time": t}
    west = (wx.wind_deg.values >= 225) & (wx.wind_deg.values <= 315)
    header = np.zeros(n)
    basin, flows_true = {}, {}
    byp = np.where(t < BYPASS[1], BYPASS[2], BYPASS[3]) * (1 + 0.03 * np.sin(2 * np.pi * np.arange(n) / 24.0 - 1.0)) \
        * (1 + rng.normal(0, 0.01, n))
    c3_out = (t >= C3_OUT[0]) & (t < C3_OUT[1])
    for c in CELLS:
        flow = op[c + "_flow"].values.copy()
        spd = op[c + "_spd"].values.copy()
        if c == "C3":
            flow = np.where(c3_out, 0.0, flow); spd = np.where(c3_out, 0.0, spd)
        if c == "C8":       # fan stopped while the stack extension was fitted
            spd = np.where((t >= STACK_C8 - pd.Timedelta(hours=9)) & (t < STACK_C8), 0.0, spd)
        L = flow * RHO_W / 3600.0
        G = G_DESIGN / RHO_DESIGN * rho * A_CELL[c] * spd / 100.0
        P = P_DESIGN * (rho / RHO_DESIGN) * (A_CELL[c] * spd / 100.0) ** 3
        wb_in = wb + np.where((c == "C8") & west & (t < STACK_C8), RECIRC_K, 0.0)
        h_in = psy.hsat(wb_in, wx.p.values)
        kfac = np.where(wx.wind_ms.values > WIND_LIMIT, WIND_LOSS, 1.0)
        C = cap(c, t) / 100.0 * C_DESIGN
        th = op.th.values + RISER_BIAS[c]          # each riser's hot water differs a little (heat loss on the header)
        lg = np.where((spd > 0) & (flow > 0), L / np.maximum(G, 1e-9), 1.0)
        tc = psy.cold_water(th, lg, h_in, wx.p.values, kfac * C * lg ** -N_EXP)
        tc = np.where(spd > 0, tc, th - 2.0)          # fan off: natural draft only, a little cooling
        if c == "C3":
            tc = np.where(c3_out, wb + 1.0, tc)        # drained basin: the weir sensor sits in damp air
        header += flow
        # records
        f_rec = flow * (1 + rng.normal(0, 0.008, n))
        if c == "C3":
            f_rec = f_rec + C3_ZERO + rng.normal(0, 3.0, n)
        if c == "C6":
            f_rec = np.where(t >= C6_FLOW[0], f_rec * C6_FLOW[1], f_rec)
        if c in GPM_CELLS:
            f_rec = f_rec * GPM_PER_M3H
        p_rec = P * (1 + rng.normal(0, 0.01, n))
        if c == "C4":
            p_rec = np.where(t >= C4_POWER[0], p_rec * C4_POWER[1], p_rec)
        noise_th = np.where((c == "C2") & (t < C2_TH[0]), 0.45, 0.10)        # the old C2 thermocouple was noisy
        th_rec = th + rng.normal(0, 1, n) * noise_th + np.where((c == "C2") & (t >= C2_TH[0]), C2_TH[1], 0.0)
        out_flow = flow.copy()
        if c == BYPASS[0]:      # the bypassed header water lands in the basin ahead of the outlet weir
            tc = np.where(flow + byp > 0, (flow * tc + byp * th) / np.maximum(flow + byp, 1e-9), tc)
            out_flow = flow + byp
        basin[c] = tc
        flows_true[c] = out_flow
        tc_rec = tc + rng.normal(0, 0.10, n)
        rec[c + "_flow"] = np.round(f_rec, 0)
        rec[c + "_fan_pct"] = np.round(spd, 0)
        rec[c + "_fan_kw"] = np.round(np.where(spd > 0, p_rec, 0.0), 1)
        rec[c + "_hw_in_c"] = np.round(th_rec, 2)
        rec[c + "_cw_out_c"] = np.round(tc_rec, 2)
    rec["header_flow_m3h"] = np.round((header + byp) * (1 + rng.normal(0, 0.004, n)), 0)
    qsum = sum(flows_true[c] for c in CELLS)
    mix = np.where(qsum > 0, sum(flows_true[c] * basin[c] for c in CELLS) / np.maximum(qsum, 1e-9), basin["C5"])
    rec[FLUME_TC + "_cw_out_c"] = np.round(mix + rng.normal(0, 0.10, n), 2)
    met = pd.DataFrame(dict(time=t + pd.Timedelta(hours=MET_UTC_OFFSET_H), dry_bulb_c=np.round(wx.tdb.values, 2), rh_pct=np.round(wx.rh.values, 1),
                            pressure_kpa=np.round(wx.p.values / 1000, 2), wind_ms=np.round(wx.wind_ms.values, 1),
                            wind_from_deg=np.round(wx.wind_deg.values, 0)))
    return pd.DataFrame(rec), met
