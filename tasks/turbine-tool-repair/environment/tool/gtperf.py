"""GT-1 performance test reduction - plant program v2.3 (2021, written to TP-GT-07 rev 3).

    python3 gtperf.py RECORD_DIR OUT_CSV

RECORD_DIR holds one test day's record set (gt1_record_format.md): test_das_1min.csv, dcs_1min.csv, gas_analysis.csv and
test_log.csv. OUT_CSV gets the header corrected_output_mw,corrected_heat_rate_kj_kwh and one row: GT-1's corrected
gross output (MW) and corrected heat rate (kJ/kWh, LHV) at the contract reference conditions, the mean of the valid
runs.
"""
import os
import sys

import numpy as np
import pandas as pd

REF_PF = 0.85
CP_FUEL = 2.20                                   # kJ/kg K
GEN_L0, GEN_K, GEN_S = 410.0, 560.0, 56.0        # generator losses L = L0 + K (S/GEN_S)^2 kW, S in MVA
IGV_MIN, TEXH_BAND, WINDOW = 85.5, 3.0, 30       # IGVs fully open at 86 deg; temperature control band

# ISO 6976 net molar heating value at 15 degC (kJ/mol) and molar mass (g/mol), procedure table
COMPONENTS = {
    "CH4": (802.69, 16.043), "C2H6": (1482.84, 30.069), "C3H8": (2043.37, 44.096), "iC4H10": (2648.42, 58.122),
    "nC4H10": (2657.60, 58.122), "iC5H12": (3265.08, 72.149), "nC5H12": (3272.00, 72.149),
    "nC6H14": (3887.21, 86.175), "N2": (0.0, 28.0135), "CO2": (0.0, 44.010), "O2": (0.0, 31.9988),
}

# OEM correction curves (OEM performance document): x, output factor, heat rate factor
CIT_TABLE = np.array([
    [-5, 1.1300, 0.9660], [0, 1.1001, 0.9730], [5, 1.0685, 0.9810], [10, 1.0351, 0.9900], [15, 1.0000, 1.0000],
    [20, 0.9631, 1.0110], [25, 0.9425, 1.0230], [30, 0.8841, 1.0360], [35, 0.8420, 1.0500], [40, 0.7981, 1.0650]])
INLET_TABLE = np.array([
    [0.0, 1.0145, 0.9950], [0.5, 1.0072, 0.9975], [1.0, 1.0000, 1.0000], [1.5, 0.9928, 1.0025],
    [2.0, 0.9855, 1.0050], [2.5, 0.9782, 1.0075], [3.0, 0.9710, 1.0100]])
EXHAUST_TABLE = np.array([
    [0.0, 0.9850, 1.0165], [1.0, 0.9900, 1.0110], [2.0, 0.9950, 1.0055], [3.0, 1.0000, 1.0000],
    [4.0, 1.0050, 0.9945], [5.0, 1.0100, 0.9890], [6.0, 1.0150, 0.9835]])
HUMIDITY_TABLE = np.array([
    [0.002, 0.9987, 1.0002], [0.004, 0.9993, 1.0001], [0.006, 0.9999, 1.0000], [0.008, 1.0005, 0.9999],
    [0.010, 1.0011, 0.9999], [0.012, 1.0017, 0.9998], [0.014, 1.0023, 0.9997], [0.016, 1.0029, 0.9996],
    [0.018, 1.0035, 0.9995], [0.020, 1.0041, 0.9995]])


def curve(table, x, col):
    """Linear interpolation in the table; linear extrapolation from the end segments outside it."""
    xs, ys = table[:, 0], table[:, col]
    x = np.asarray(x, float)
    y = np.interp(x, xs, ys)
    return float(y)


def psat_kpa(t):
    T = np.asarray(t, float) + 273.15
    return np.exp(-5.8002206e3 / T + 1.3914993 - 4.8640239e-2 * T + 4.1764768e-5 * T ** 2
                  - 1.4452093e-8 * T ** 3 + 6.5459673 * np.log(T)) / 1000.0


def gen_loss_kw(p_kw, pf):
    return GEN_L0 + GEN_K * (p_kw / 1000.0 / pf / GEN_S) ** 2


def lhv_kj_kg(sample):
    num = den = 0.0
    for c, (hn, mm) in COMPONENTS.items():
        x = float(sample.get(c, 0.0) or 0.0) / 100.0
        num += x * hn
        den += x * mm
    return num / den * 1000.0


def read(test_dir):
    das = pd.read_csv(os.path.join(test_dir, "test_das_1min.csv"), parse_dates=["time"]).set_index("time")
    dcs = pd.read_csv(os.path.join(test_dir, "dcs_1min.csv"), parse_dates=["time"]).set_index("time")
    gas = pd.read_csv(os.path.join(test_dir, "gas_analysis.csv"))
    log = pd.read_csv(os.path.join(test_dir, "test_log.csv"), parse_dates=["time"])
    d = das.join(dcs, how="left")
    # units
    d["p_amb"] = d["met_baro_hpa"] / 10.0
    d["m_fuel"] = d["fuel_coriolis_kg_s"]
    rtd = d[["cit_%d_c" % i for i in range(1, 9)]]
    d["cit"] = rtd.mean(axis=1, skipna=True)
    pv = d.met_rh_pct / 100.0 * psat_kpa(d.met_dry_bulb_c)
    d["w"] = 0.621945 * pv / (d.p_amb - pv)
    d["dp_in"] = d.pdt101_filter_dp_kpa
    return d, gas, log


def runs(log):
    out = {}
    for _, r in log.iterrows():
        words = str(r.entry).split()
        if len(words) == 3 and words[0] == "Run" and words[2] in ("start", "end", "aborted"):
            out.setdefault(words[1], {})["end" if words[2] == "aborted" else words[2]] = r.time
    return {k: v for k, v in out.items() if "start" in v and "end" in v}


def window(x):
    """First 30 successive minutes at steady base load, or None."""
    ok = ((x.igv_deg >= IGV_MIN) & ((x.texh_avg_c - x.ttrf_c) <= TEXH_BAND)).values
    t = x.index
    for i in range(len(x) - WINDOW + 1):
        if ok[i:i + WINDOW].all() and (t[i + WINDOW - 1] - t[i]) == pd.Timedelta(minutes=WINDOW - 1):
            return x.index[i:i + WINDOW]
    return None


def reduce(test_dir):
    d, gas, log = read(test_dir)
    lhv = float(np.mean([lhv_kj_kg(r) for _, r in gas.iterrows()]))
    results = []
    for name, se in sorted(runs(log).items()):
        x = d[(d.index > se["start"]) & (d.index <= se["end"])]
        win = window(x)
        if win is None:
            continue
        a = d.loc[win].mean(numeric_only=True)
        P = a.gen_mw_jt001 * 1000.0
        Qr = a.gen_mvar_jt001 * 1000.0
        pf = abs(P) / np.hypot(P, Qr)
        p_pf = P + gen_loss_kw(P, REF_PF) - gen_loss_kw(P, pf)
        heat = a.m_fuel * lhv + CP_FUEL * (a.te301_fuel_meter_c - 15.0)
        fh = curve(HUMIDITY_TABLE, a.w, 1)
        gh = curve(HUMIDITY_TABLE, a.w, 2)
        f = curve(CIT_TABLE, a.cit, 1) * (a.p_amb / 101.325) * fh * curve(INLET_TABLE, a.dp_in, 1) \
            * curve(EXHAUST_TABLE, a.pdt201_exhaust_kpa_g, 1)
        g = curve(CIT_TABLE, a.cit, 2) * gh * curve(INLET_TABLE, a.dp_in, 2) * curve(EXHAUST_TABLE, a.pdt201_exhaust_kpa_g, 2)
        results.append((p_pf / f / 1000.0, 3600.0 * heat / p_pf * g))
    if not results:
        raise RuntimeError("no valid run")
    return float(np.mean([r[0] for r in results])), float(np.mean([r[1] for r in results]))


def main():
    test_dir, out = sys.argv[1], sys.argv[2]
    p, hr = reduce(test_dir)
    with open(out, "w") as f:
        f.write("corrected_output_mw,corrected_heat_rate_kj_kwh\n%.4f,%.2f\n" % (p, hr))


if __name__ == "__main__":
    main()
