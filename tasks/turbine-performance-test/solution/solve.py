"""Reference solution for turbine-performance-test: reduce the GT-1 test records by procedure TP-GT-07 to corrected gross
output and corrected heat rate, as found and as left.

    python3 solve.py DATA_DIR OUT_CSV

Every correction below is taken from the records; the comments say which record shows it.
"""
import os
import sys

import numpy as np
import pandas as pd

ELEV_M = 310.0                   # plant datum, site_data.md
REF_PF = 0.85
CP_FUEL = 2.20                   # kJ/kg K, procedure
GEN_L0, GEN_K, GEN_S = 410.0, 560.0, 56.0      # generator losses, generator_data.md
PT_ACTUAL, PT_SET = 13800.0, 14400.0           # generator_data.md / JT-001 calibration certificate
COMP = ["CH4", "C2H6", "C3H8", "iC4H10", "nC4H10", "iC5H12", "nC5H12", "nC6H14", "N2", "CO2", "O2"]
HN = dict(CH4=802.69, C2H6=1428.84, C3H8=2043.37, iC4H10=2648.42, nC4H10=2657.60, iC5H12=3265.08, nC5H12=3272.00,
          nC6H14=3887.21, N2=0.0, CO2=0.0, O2=0.0)                  # kJ/mol, procedure table
MM = dict(CH4=16.043, C2H6=30.069, C3H8=44.096, iC4H10=58.122, nC4H10=58.122, iC5H12=72.149, nC5H12=72.149,
          nC6H14=86.175, N2=28.0135, CO2=44.010, O2=31.9988)
STILL_END = "07:20"              # the unit starts at 07:30 (test log); minutes before are standstill


def psat_kpa(t):
    T = np.asarray(t, float) + 273.15
    return np.exp(-5.8002206e3 / T + 1.3914993 - 4.8640239e-2 * T + 4.1764768e-5 * T ** 2
                  - 1.4452093e-8 * T ** 3 + 6.5459673 * np.log(T)) / 1000.0


def curve_tables(path):
    """The four OEM tables: {name: array of [x, output factor, heat rate factor]}."""
    out, cur = {}, None
    for line in open(path):
        if line.startswith("## "):
            cur = line[3:].strip().lower()
            out[cur] = []
        elif cur and line.startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            try:
                out[cur].append([float(c) for c in cells])
            except ValueError:
                pass
    return {k: np.array(v) for k, v in out.items() if v}


def gen_loss_kw(p_kw, pf):
    return GEN_L0 + GEN_K * (p_kw / 1000.0 / pf / GEN_S) ** 2


def lhv_kj_kg(x):
    return sum(x[c] * HN[c] for c in COMP) / sum(x[c] * MM[c] for c in COMP) * 1000.0


def load(data):
    das = pd.read_csv(os.path.join(data, "test_das_1min.csv"), parse_dates=["time"]).set_index("time")
    dcs = pd.read_csv(os.path.join(data, "dcs_1min.csv"), parse_dates=["time"]).set_index("time")
    gc = pd.read_csv(os.path.join(data, "gas_analysis.csv"), parse_dates=["sample_time"])
    log = pd.read_csv(os.path.join(data, "test_log.csv"), parse_dates=["time"])
    T = curve_tables(os.path.join(data, "docs", "oem_correction_curves.md"))
    return das.join(dcs), gc, log, T


def runs(log):
    out = {}
    for _, r in log.iterrows():
        w = r.entry.split()
        if len(w) == 3 and w[0] == "Run" and w[2] in ("start", "end"):
            out.setdefault(w[1], {})[w[2]] = r.time
    return out


def reduce(data):
    d, gc, log, T = load(data)
    day = d.index.normalize()
    days = sorted(set(day))
    still = d.index.strftime("%H:%M") < STILL_END
    info = {}
    # Ambient pressure. The met barometer (calibrated 2026-07) reads station pressure on day 1. At standstill PT-102 sees
    # ambient pressure with no flow, and reads 0.60 kPa below the barometer on day 1: PT-102's zero error. On day 2,
    # after the met logger was replaced, the standstill gap is 4.26 kPa: the same 0.60 kPa plus the 3.66 kPa by which
    # the new logger's sea-level (QNH) value exceeds station pressure at 310 m (standard atmosphere).
    baro = d.met_baro_hpa / 10.0
    gap = (d.pt102_inlet_total_kpa_abs - baro)[still].groupby(day[still]).mean()
    pt_zero = float(gap[days[0]])
    qnh_to_station = (1.0 - 2.25577e-5 * ELEV_M) ** 5.25588
    p_amb = baro.copy()
    for k in days[1:]:
        excess = -(gap[k] - pt_zero)                                   # met reading above station pressure
        if abs(excess - float(baro[day == k].mean()) * (1 - qnh_to_station)) < 0.3:
            p_amb[day == k] = baro[day == k] * qnh_to_station
        info["day %s barometer excess at standstill, kPa" % k.date()] = round(float(excess), 3)
    pt102 = d.pt102_inlet_total_kpa_abs - pt_zero
    info["PT-102 zero, kPa"] = round(pt_zero, 3)
    # Inlet temperature. At standstill the plenum air is the ambient air; the RTD array agrees with the met dry bulb
    # on day 1 and reads 1.2 K high on day 2 (the noon spot checks with the reference thermometer show the same).
    cit = d[["cit_%d_c" % i for i in range(1, 9)]].mean(axis=1)
    bias = (cit - d.met_dry_bulb_c)[still].groupby(day[still]).mean()
    cit = cit - bias.reindex(day).values
    info["RTD array bias by day, K"] = {str(k.date()): round(float(v), 2) for k, v in bias.items()}
    # Gross output. JT-001 multiplies its secondary readings by 14400:120 (calibration certificate); the PTs are
    # 13800:120 (generator data sheet).
    P = d.gen_mw_jt001 * 1000.0 * PT_ACTUAL / PT_SET
    Q = d.gen_mvar_jt001 * 1000.0 * PT_ACTUAL / PT_SET
    dp_in = p_amb - pt102
    pv = d.met_rh_pct / 100.0 * psat_kpa(d.met_dry_bulb_c)
    w = 0.621945 * pv / (p_amb - pv)
    # Fuel. FT-301 reads a steady flow at standstill with no fuel burnt: its zero error, subtracted per day.
    zero = d.fuel_coriolis_kg_s[still].groupby(day[still]).median()
    info["FT-301 zero by day, kg/s"] = {str(k.date()): round(float(v), 4) for k, v in zero.items()}
    # LHV per day: mean over the day's samples, leaving out a sample with oxygen (air drawn into the sample).
    lhv = {}
    for k in days:
        vals = []
        for _, r in gc[gc.sample_time.dt.normalize() == k].iterrows():
            x = {c: r[c] / 100.0 for c in COMP}
            if x["O2"] > 0.001:
                info["gas sample left out"] = str(r.sample_time)
                continue
            vals.append(lhv_kj_kg(x))
        lhv[k] = float(np.mean(vals))
    info["LHV by day, kJ/kg"] = {str(k.date()): round(v, 1) for k, v in lhv.items()}
    res = {}
    for name, se in runs(log).items():
        x = d[(d.index > se["start"]) & (d.index <= se["end"])]
        base = ((x.igv_deg >= 85.5) & ((x.texh_avg_c - x.ttrf_c).abs() <= 3.0)).values
        start = next((i for i in range(len(x) - 29) if base[i:i + 30].all()), None)
        if start is None:
            info["run %s" % name] = "not valid: no 30 minutes at base load"
            continue
        win = x.index[start:start + 30]
        k = win[0].normalize()
        Pm, Qm = P[win].mean(), Q[win].mean()
        pf = Pm / np.hypot(Pm, Qm)
        Ppf = Pm + gen_loss_kw(Pm, pf) - gen_loss_kw(Pm, REF_PF)
        heat = (d.fuel_coriolis_kg_s[win].mean() - zero[k]) * (lhv[k] + CP_FUEL * (d.te305_fuel_skid_c[win].mean() - 15.0))
        c, pa, ww = cit[win].mean(), p_amb[win].mean(), w[win].mean()
        di, de = dp_in[win].mean(), d.pdt201_exhaust_kpa_g[win].mean()
        t_c, t_i, t_e, t_h = (T["compressor inlet temperature"], T["inlet loss"], T["exhaust loss"],
                              T["ambient specific humidity"])
        fo = (np.interp(c, t_c[:, 0], t_c[:, 1]) * pa / 101.325 * np.interp(ww, t_h[:, 0], t_h[:, 1])
              * np.interp(di, t_i[:, 0], t_i[:, 1]) * np.interp(de, t_e[:, 0], t_e[:, 1]))
        fh = (np.interp(c, t_c[:, 0], t_c[:, 2]) * np.interp(ww, t_h[:, 0], t_h[:, 2])
              * np.interp(di, t_i[:, 0], t_i[:, 2]) * np.interp(de, t_e[:, 0], t_e[:, 2]))
        res[name] = dict(output=Ppf / fo / 1000.0, hr=3600.0 * heat / Ppf / fh, window=str(win[0]))
        info["run %s" % name] = "window from %s, %.3f MW, %.1f kJ/kWh" % (win[0], res[name]["output"], res[name]["hr"])
    out = {}
    for cond, letter in (("as_found", "A"), ("as_left", "L")):
        r = [v for n, v in res.items() if n.startswith(letter)]
        out[cond] = (np.mean([v["output"] for v in r]), np.mean([v["hr"] for v in r]))
    return out, info


def main():
    data = sys.argv[1] if len(sys.argv) > 1 else "/app/data"
    path = sys.argv[2] if len(sys.argv) > 2 else "/app/output/gt1_corrected_results.csv"
    out, info = reduce(data)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w") as f:
        f.write("condition,corrected_output_mw,corrected_heat_rate_kj_kwh\n")
        for cond in ("as_found", "as_left"):
            f.write("%s,%.3f,%.1f\n" % (cond, out[cond][0], out[cond][1]))
    for k, v in info.items():
        print("%s: %s" % (k, v))
    for cond in out:
        print(cond, "%.3f MW" % out[cond][0], "%.1f kJ/kWh" % out[cond][1])


if __name__ == "__main__":
    main()
