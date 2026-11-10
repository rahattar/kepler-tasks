"""Sealed definition: cooling-water cooler bank of the glycol loop, units E1-E10 (shell-and-tube, counterflow
treated as pure counterflow). Units: m3/h, C, kW, W/m2K, m2K/kW for fouling resistance.

Overall coefficient: 1/U = 1/h_t + 1/h_s + R_w + R_f, with h_t ~ (tube-side velocity)^0.8 and h_s ~ (shell flow)^0.6.
- Model C-200 (E1-E9) and C-310 (E10, new). Design-sheet split per model; each unit varies a few per cent.
- E3, E7, E8: 2026 retrofit with enhanced (internally ribbed) tubes: tube-side friction factor x e_f (per unit,
  rib geometry varies between tube lots), tube-side coefficient x e_h = 1 + K_EH (e_f - 1) (one ratio).
- E2: leaking tubes plugged in 2026 (fraction open N_OPEN; area and tube flow area fall).
- E5: replacement bundle (Aug 2026) built to a revised baffle drawing (spacing 400 mm, was 300 mm): the shell-side
  crossflow velocity falls to 0.75 and the shell film with it to the power 0.6.
- E10: new unit; only the vendor's datasheet clean coefficient (optimistic).
- Fouling resistance grows linearly in time; E6 fast (biofouling after a chlorination outage). The shock
  chlorination of 2026-10-05 strips part of E6's biofilm (a step down), after which it grows at the same rate.
- Process-outlet temperature transmitter reads high by a per-unit bias; visible in standby (cooling water isolated,
  glycol circulating: true outlet = inlet). E8 never stands by.
Time: days from 2026-09-14 00:00 (start of the trends). Assessment (clean-and-test) day: T_TEST.
"""
import numpy as np

UNITS = ["E%d" % i for i in range(1, 11)]
T_TEST = 42.0                       # 2026-10-26, 4 weeks of trends + 14 days
TEST_DATE = "2026-10-26"
RHO_CW, CP_CW = 995.0, 4.18         # kg/m3, kJ/kg K
RHO_G, CP_G = 1050.0, 3.60          # glycol solution
K_EH = 0.65
MODEL = {"C-200": dict(A=90.0, ht=3000.0, hs=2500.0, rw=5e-5, ft=180.0, fs=60.0, dp=42.0),
         "C-310": dict(A=110.0, ht=3200.0, hs=2600.0, rw=5e-5, ft=220.0, fs=75.0, dp=38.0)}
ENH = {"E3": 1.25, "E7": 2.80, "E8": 1.80}           # tube-side friction factor ratio of the ribbed tubes
N_OPEN = {"E2": 0.88}                                # fraction of tubes open
HS_NEW = {"E5": (300.0 / 400.0) ** 0.6}               # replacement bundle: baffle spacing 300 -> 400 mm, crossflow
                                                     # velocity x 0.75, shell film x 0.75^0.6
VENDOR_U = 1.12                                      # E10 datasheet clean U over the true one
SHOCK_DAY = 21.5                                     # 2026-10-05 12:00, end of the shock chlorination
SHOCK_DROP = {"E6": 0.22}
RF_TEST = {"E4": 0.104, "E1": 0.197, "E10": 0.290, "E5": 0.500, "E2": 0.598, "E9": 0.690, "E6": 0.903,
           "E7": 0.996, "E3": 1.087, "E8": 1.283}  # m2K/kW on 2026-10-26: irregular, at least 0.092 apart


def make_fleet(seed=11):
    rng = np.random.default_rng(seed)
    fleet = {}
    for u in UNITS:
        model = "C-310" if u == "E10" else "C-200"
        m = MODEL[model]
        b = dict(unit=u, model=model, A_nom=m["A"])
        b["ht0"] = m["ht"] * (1 + rng.normal(0, 0.025))
        b["hs0"] = m["hs"] * (1 + rng.normal(0, 0.025))
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
    for u, target in RF_TEST.items():   # as-found fouling on the test day, irregularly spread across the bank
        b = fleet[u]
        b["rate"] = min(b["rate"], (target - 0.03) / T_TEST) if u != "E6" else b["rate"]
        b["rf0"] = target - b["rate"] * T_TEST + SHOCK_DROP.get(u, 0.0)
    return fleet


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
    r = b["rf0"] + b["rate"] * t
    if t >= SHOCK_DAY:                  # the shock dose strips part of the biofilm; growth carries on after it
        r -= SHOCK_DROP.get(b["unit"], 0.0)
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
