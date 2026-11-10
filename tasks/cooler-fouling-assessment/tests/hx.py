"""Sealed definition: cooling-water cooler bank of the glycol loop, units E1-E10 (shell-and-tube, counterflow
treated as pure counterflow). Units: m3/h, C, kW, W/m2K, m2K/kW for fouling resistance.

Overall coefficient: 1/U = 1/h_t + 1/h_s + R_w + R_f, with h_t ~ (tube-side velocity)^0.8 and h_s ~ (shell flow)^0.6.
- Model C-200 (E2-E9) and C-310 (E1, E10, both commissioned June 2026). Design-sheet split per model; the
  C-200s wander several per cent from it (bundles rebuilt and repaired over the years), so each one's own 2025
  acceptance test is its clean performance; the two C-310s are one build batch and are alike to about a per cent.
- E1 and E10: the only rating either has is the C-310 datasheet, one sheet from the vendor's thermal program for
  both of them, optimistic by VENDOR_U. The program's optimism is the same for the two of them, so a clean test on
  either one carries to the other; nothing else on site gives it.
- E3, E7, E8: 2026 retrofit with enhanced (internally ribbed) tubes: tube-side friction factor x e_f (per unit,
  rib geometry varies between tube lots), tube-side coefficient x e_h = 1 + K_EH (e_f - 1) (one ratio).
- E2: leaking tubes plugged in 2026 (fraction open N_OPEN; area and tube flow area fall).
- E5: replacement bundle (Aug 2026) built to a revised baffle drawing (spacing 400 mm, was 300 mm): the shell-side
  crossflow velocity falls to 0.75 and the shell film with it to the power 0.6.
- E9: its 2025 acceptance sheet does not close its heat balance (two readings misrecorded, see gen.py).
- Fouling resistance grows linearly in time, DOSE_FAST times faster over the ten days the cooling water ran with
  no chlorine (the dosing pump was down, 2026-09-02 to 2026-09-12), then at its own rate again. The shock
  chlorination of 2026-09-28 strips SHOCK_STRIP of the biofilm each unit grew over those ten days (a step down),
  after which growth carries on at the same rate. E6 fouls fast, so it grows and loses the most.
- Process-outlet temperature transmitter reads high by a per-unit bias; visible in standby (cooling water isolated,
  glycol circulating: true outlet = inlet). E8 never stands by.
Time: days from 2026-08-24 00:00 (start of the trends). Assessment (clean-and-test) day: T_TEST.
"""
import numpy as np

UNITS = ["E%d" % i for i in range(1, 11)]
T_TEST = 63.0                       # 2026-10-26, seven weeks of trends + 14 days
TEST_DATE = "2026-10-26"
RHO_CW, CP_CW = 995.0, 4.18         # kg/m3, kJ/kg K
RHO_G, CP_G = 1050.0, 3.60          # glycol solution
K_EH = 0.65
NEW = ("E1", "E10")                 # the two C-310 coolers commissioned June 2026: one batch, one vendor datasheet
MODEL = {"C-200": dict(A=90.0, ht=3000.0, hs=2500.0, rw=5e-5, ft=180.0, fs=60.0, dp=42.0),
         "C-310": dict(A=110.0, ht=3200.0, hs=2600.0, rw=5e-5, ft=220.0, fs=75.0, dp=38.0)}
ENH = {"E3": 1.25, "E7": 2.80, "E8": 1.80}           # tube-side friction factor ratio of the ribbed tubes
N_OPEN = {"E2": 0.88}                                # fraction of tubes open
HS_NEW = {"E5": (300.0 / 400.0) ** 0.6}               # replacement bundle: baffle spacing 300 -> 400 mm, crossflow
                                                     # velocity x 0.75, shell film x 0.75^0.6
VENDOR_U = 1.12                                      # C-310 datasheet clean U over the true one, both units
DOSE_FAIL, DOSE_FIX = 9.0, 19.0     # 2026-09-02 to 2026-09-12: no chlorine in the cooling water
DOSE_FAST = 8.0                     # fouling rate while the dosing pump is down, times the unit's own rate
SHOCK_DAY = 35.5                    # 2026-09-28 12:00, end of the shock chlorination
SHOCK_STRIP = 0.6                   # of the biofilm grown over the dosing outage, the share the shock dose removes
RF_TEST = {"E4": 0.104, "E1": 0.197, "E10": 0.290, "E5": 0.500, "E2": 0.598, "E9": 0.690, "E6": 0.903,
           "E7": 0.996, "E3": 1.087, "E8": 1.283}  # m2K/kW on 2026-10-26: irregular, at least 0.092 apart


def make_fleet(seed=11):
    rng = np.random.default_rng(seed)
    fleet = {}
    for u in UNITS:
        model = "C-310" if u in NEW else "C-200"
        m = MODEL[model]
        b = dict(unit=u, model=model, A_nom=m["A"])
        sd = 0.01 if u in NEW else 0.10          # the two C-310s are one build batch, so they are alike
        b["ht0"] = m["ht"] * (1 + rng.normal(0, sd))
        b["hs0"] = m["hs"] * (1 + rng.normal(0, sd))
        b["rw"] = m["rw"]
        b["dp0"] = m["dp"] * (1 + rng.normal(0, 0.015))
        b["e_f"] = ENH.get(u, 1.0)
        b["e_h"] = 1.0 + K_EH * (b["e_f"] - 1.0)
        b["open"] = N_OPEN.get(u, 1.0)
        b["hs_fac"] = HS_NEW.get(u, 1.0)
        b["bias"] = float(rng.uniform(-1.5, 1.5))     # K, process-outlet transmitter
        b["rf0"] = float(rng.uniform(0.10, 0.35))     # m2K/kW at day 0
        b["rate"] = float(rng.uniform(0.0005, 0.0025))  # m2K/kW per day
        fleet[u] = b
    fleet["E6"]["rate"] = 0.0090
    fleet["E8"]["bias"] = 2.0
    fleet["E9"]["ht0"] *= 0.80          # E9's bundle (rebuilt 2019) has a poorer tube side than its sisters
    span = T_TEST + (DOSE_FAST - 1.0) * (DOSE_FIX - DOSE_FAIL)      # growth days to the test day
    for u, target in RF_TEST.items():   # as-found fouling on the test day, irregularly spread across the bank
        b = fleet[u]
        b["rate"] = min(b["rate"], (target - 0.03) / span) if u != "E6" else b["rate"]
        b["rf0"] = target - growth(b, T_TEST) + strip(b)
    return fleet


def growth(b, t):
    """Fouling grown by day t: the unit's own rate, DOSE_FAST times that while the dosing pump is down."""
    r = b["rate"] * min(t, DOSE_FAIL)
    if t > DOSE_FAIL:
        r += b["rate"] * DOSE_FAST * (min(t, DOSE_FIX) - DOSE_FAIL)
    if t > DOSE_FIX:
        r += b["rate"] * (t - DOSE_FIX)
    return r


def strip(b):
    """What the shock chlorination takes off: part of the biofilm grown while the dosing pump was down."""
    return SHOCK_STRIP * b["rate"] * (DOSE_FAST - 1.0) * (DOSE_FIX - DOSE_FAIL)


def h_t(b, ft, now=True):
    """Tube-side coefficient at cooling-water flow ft (m3/h); now=False: before the 2026 changes."""
    m = MODEL[b["model"]]
    op = b["open"] if now else 1.0
    eh = b["e_h"] if now else 1.0
    return b["ht0"] * eh * (ft / op / m["ft"]) ** 0.8


def h_s(b, fs, now=True):
    m = MODEL[b["model"]]
    return b["hs0"] * (b["hs_fac"] if now else 1.0) * (fs / m["fs"]) ** 0.6


def area(b, now=True):
    return b["A_nom"] * (b["open"] if now else 1.0)


def rf(b, t):
    r = b["rf0"] + growth(b, t)
    if t >= SHOCK_DAY:                  # the shock dose strips part of the biofilm; growth carries on after it
        r -= strip(b)
    return r


def u_value(b, ft, fs, t=None, clean=False, now=True):
    r = 0.0 if clean else rf(b, t) / 1000.0
    return 1.0 / (1.0 / h_t(b, ft, now) + 1.0 / h_s(b, fs, now) + b["rw"] + r)


def dp_tube(b, ft, now=True):
    m = MODEL[b["model"]]
    op = b["open"] if now else 1.0
    ef = b["e_f"] if now else 1.0
    return b["dp0"] * ef * (ft / op / m["ft"]) ** 1.8


def outlets(UA, ft, fs, tci, thi):
    """Counterflow outlet temperatures (effectiveness-NTU). UA in W/K."""
    Cc = ft / 3600.0 * RHO_CW * CP_CW * 1000.0
    Ch = fs / 3600.0 * RHO_G * CP_G * 1000.0
    Cmin, Cmax = min(Cc, Ch), max(Cc, Ch)
    cr = Cmin / Cmax
    ntu = UA / Cmin
    if abs(1 - cr) < 1e-9:
        eps = ntu / (1 + ntu)
    else:
        eps = (1 - np.exp(-ntu * (1 - cr))) / (1 - cr * np.exp(-ntu * (1 - cr)))
    q = eps * Cmin * (thi - tci)
    return tci + q / Cc, thi - q / Ch, q / 1000.0


def clean_and_test(b, k):
    """The assessment-day test: as-found performance test with calibrated portable instruments (clamp-on flow meter,
    reference RTDs at the four nozzles) and the DCS readings at the same time; then the bundle is hydroblasted and
    the test repeated (clean)."""
    rng = np.random.default_rng(9000 + 31 * k + UNITS.index(b["unit"]))
    m = MODEL[b["model"]]
    ft, fs = m["ft"] * 0.97, m["fs"] * 1.02
    tci, thi = 27.0, 70.0
    out = {}
    for label, clean in (("as_found", False), ("after_cleaning", True)):
        UA = u_value(b, ft, fs, T_TEST, clean=clean) * area(b)
        tco, tho, q = outlets(UA, ft, fs, tci, thi)
        ref = dict(cw_flow_m3h=round(ft * (1 + rng.normal(0, 0.003)), 2), glycol_flow_m3h=round(fs * (1 + rng.normal(0, 0.003)), 2),
                   cw_in_c=round(tci + rng.normal(0, 0.02), 2), cw_out_c=round(tco + rng.normal(0, 0.02), 2),
                   glycol_in_c=round(thi + rng.normal(0, 0.02), 2), glycol_out_c=round(tho + rng.normal(0, 0.02), 2))
        dcs = dict(cw_flow_m3h=round(ft * (1 + rng.normal(0, 0.005)), 1), glycol_flow_m3h=round(fs * (1 + rng.normal(0, 0.005)), 1),
                   cw_in_c=round(tci + rng.normal(0, 0.05), 2), cw_out_c=round(tco + rng.normal(0, 0.05), 2),
                   glycol_in_c=round(thi + rng.normal(0, 0.05), 2), glycol_out_c=round(tho + b["bias"] + rng.normal(0, 0.05), 2),
                   dp_tube_kpa=round(dp_tube(b, ft) * (1 + rng.normal(0, 0.01)), 2))
        out[label] = dict(reference_instruments=ref, dcs=dcs)
    return out


def grade(est, fleet, tol):
    """est {unit: rf m2K/kW}. Returns {unit: (err, ok)} at the test day."""
    res = {}
    for u in UNITS:
        e = est[u] - rf(fleet[u], T_TEST)
        res[u] = (float(e), abs(e) <= tol)
    return res
