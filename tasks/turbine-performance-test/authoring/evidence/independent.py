"""A second reduction of the GT-1 test, written apart from solution/solve.py and sharing no code with it.

    python3 authoring/evidence/independent.py > authoring/evidence/independent.txt

Different choices throughout:
- IAPWS-IF97 saturation pressure.
- Station pressure from the day-2 sea-level reading by the hypsometric equation with the station air temperature,
  instead of the standard atmosphere.
- PT-102's zero from a least-squares fit of the day-1 standstill minutes.
- The inlet RTD bias from the noon reference-thermometer spot checks.
- The fuel meter zero from a trimmed mean of the standstill minutes.
- The contaminated gas sample corrected by removing its air, not left out.
- Base load judged from IGV and exhaust temperature with the last 30 qualifying minutes of each run.
- Corrections applied minute by minute and then averaged.
- Correction curves by cubic interpolation through the OEM tables.
"""
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
DATA = os.path.join(ROOT, "environment", "data")
sys.path.insert(0, os.path.join(ROOT, "tests"))
import gt1_truth as T  # noqa: E402

GAS = {"CH4": (802.69, 16.043), "C2H6": (1428.84, 30.069), "C3H8": (2043.37, 44.096), "iC4H10": (2648.42, 58.122),
       "nC4H10": (2657.60, 58.122), "iC5H12": (3265.08, 72.149), "nC5H12": (3272.00, 72.149),
       "nC6H14": (3887.21, 86.175), "N2": (0.0, 28.0135), "CO2": (0.0, 44.010), "O2": (0.0, 31.9988)}


def p_sat_kpa(t_c):
    n = [0.11670521452767e4, -0.72421316703206e6, -0.17073846940092e2, 0.12020824702470e5, -0.32325550322333e7,
         0.14915108613530e2, -0.48232657361591e4, 0.40511340542057e6, -0.23855557567849, 0.65017534844798e3]
    Tk = np.asarray(t_c, float) + 273.15
    th = Tk + n[8] / (Tk - n[9])
    A = th ** 2 + n[0] * th + n[1]
    B = n[2] * th ** 2 + n[3] * th + n[4]
    C = n[5] * th ** 2 + n[6] * th + n[7]
    return (2 * C / (-B + np.sqrt(B ** 2 - 4 * A * C))) ** 4 * 1000.0


def tables():
    txt = open(os.path.join(DATA, "docs", "oem_correction_curves.md")).read()
    out = {}
    for block in txt.split("## ")[1:]:
        name = block.splitlines()[0].strip()
        rows = []
        for ln in block.splitlines():
            parts = [p.strip() for p in ln.strip("|").split("|")]
            if ln.startswith("|") and len(parts) == 3:
                try:
                    rows.append([float(p) for p in parts])
                except ValueError:
                    pass
        out[name] = np.array(rows)
    return out


def cubic(tab, x, col):
    """Natural cubic spline through the table, evaluated at x (numpy only)."""
    xs, ys = tab[:, 0], tab[:, col]
    n = len(xs)
    h = np.diff(xs)
    A = np.zeros((n, n)); r = np.zeros(n)
    A[0, 0] = A[-1, -1] = 1.0
    for i in range(1, n - 1):
        A[i, i - 1], A[i, i], A[i, i + 1] = h[i - 1], 2 * (h[i - 1] + h[i]), h[i]
        r[i] = 3 * ((ys[i + 1] - ys[i]) / h[i] - (ys[i] - ys[i - 1]) / h[i - 1])
    c = np.linalg.solve(A, r)
    x = np.asarray(x, float)
    i = np.clip(np.searchsorted(xs, x) - 1, 0, n - 2)
    dx = x - xs[i]
    b = (ys[i + 1] - ys[i]) / h[i] - h[i] * (2 * c[i] + c[i + 1]) / 3
    dd = (c[i + 1] - c[i]) / (3 * h[i])
    return ys[i] + b * dx + c[i] * dx ** 2 + dd * dx ** 3


def main():
    das = pd.read_csv(os.path.join(DATA, "test_das_1min.csv"), index_col="time", parse_dates=True)
    dcs = pd.read_csv(os.path.join(DATA, "dcs_1min.csv"), index_col="time", parse_dates=True)
    gas = pd.read_csv(os.path.join(DATA, "gas_analysis.csv"), parse_dates=["sample_time"])
    log = pd.read_csv(os.path.join(DATA, "test_log.csv"), parse_dates=["time"])
    tb = tables()
    x = das.join(dcs)
    dates = x.index.normalize()
    d1, d2 = sorted(set(dates))
    stand = x.index.hour * 60 + x.index.minute < 7 * 60 + 20
    # station pressure on day 2: hypsometric reduction with the ambient temperature (the logger reports QNH)
    baro = x.met_baro_hpa / 10.0
    tk = x.met_dry_bulb_c + 273.15
    p_st = baro.where(dates == d1, baro * np.exp(-9.80665 * 310.0 / (287.05 * (tk + 0.0065 * 310.0 / 2))))
    # PT-102 zero: least squares PT-102 = a + baro over the day-1 standstill minutes
    s1 = stand & (dates == d1)
    a = float(np.linalg.lstsq(np.ones((s1.sum(), 1)), (x.pt102_inlet_total_kpa_abs - baro)[s1].values, rcond=None)[0][0])
    pt102 = x.pt102_inlet_total_kpa_abs - a
    # inlet RTD bias from the noon spot checks
    rtd = x[[c for c in x.columns if c.startswith("cit_")]].mean(axis=1)
    bias = {}
    for _, r in log.iterrows():
        if "spot check" in r.entry:
            bias[r.time.normalize()] = float(rtd[r.time]) - float(r.entry.rsplit(":", 1)[1].split()[0])
    cit = rtd - dates.map(bias).values
    # fuel zero: 10 % trimmed mean of the standstill minutes
    zero = {}
    for dd in (d1, d2):
        v = np.sort(x.fuel_coriolis_kg_s[stand & (dates == dd)].values)
        k = len(v) // 10
        zero[dd] = v[k:len(v) - k].mean()
    # LHV per day, air removed from a contaminated sample
    lhv = {}
    for dd in (d1, d2):
        vals = []
        for _, r in gas[gas.sample_time.dt.normalize() == dd].iterrows():
            f = {c: r[c] / 100.0 for c in GAS}
            air = f["O2"] / 0.2095
            f["N2"] = f["N2"] - 0.7905 * air
            f["O2"] = 0.0
            tot = sum(f.values())
            num = sum(f[c] / tot * GAS[c][0] for c in GAS)
            den = sum(f[c] / tot * GAS[c][1] for c in GAS)
            vals.append(num / den * 1000.0)
        lhv[dd] = np.mean(vals)
    P = x.gen_mw_jt001 * 1000.0 * 13800.0 / 14400.0
    Q = x.gen_mvar_jt001 * 1000.0 * 13800.0 / 14400.0
    rh = x.met_rh_pct / 100.0 * p_sat_kpa(x.met_dry_bulb_c)
    spec = 0.621945 * rh / (p_st - rh)
    loss = lambda pk, pf: 410.0 + 560.0 * (pk / 1000.0 / pf / 56.0) ** 2
    marks = log[log.entry.str.match(r"^Run \w+ (start|end)$")]
    runs = {}
    for _, r in marks.iterrows():
        nm, what = r.entry.split()[1], r.entry.split()[2]
        runs.setdefault(nm, {})[what] = r.time
    results = {}
    for nm, se in runs.items():
        y = x[(x.index > se["start"]) & (x.index <= se["end"])]
        good = ((y.igv_deg >= 85.5) & ((y.texh_avg_c - y.ttrf_c).abs() <= 3.0)).values
        last = [i for i in range(len(y) - 29) if good[i:i + 30].all()]
        if not last:
            continue
        idx = y.index[last[-1]:last[-1] + 30]
        dd = idx[0].normalize()
        pf = P[idx] / np.hypot(P[idx], Q[idx])
        ppf = P[idx] + loss(P[idx], pf) - loss(P[idx], 0.85)
        qin = (x.fuel_coriolis_kg_s[idx] - zero[dd]) * (lhv[dd] + 2.20 * (x.te305_fuel_skid_c[idx] - 15.0))
        inl = p_st[idx] - pt102[idx]
        fo = (cubic(tb["Compressor inlet temperature"], cit[idx], 1) * p_st[idx] / 101.325
              * cubic(tb["Ambient specific humidity"], spec[idx], 1) * cubic(tb["Inlet loss"], inl, 1)
              * cubic(tb["Exhaust loss"], x.pdt201_exhaust_kpa_g[idx], 1))
        fh = (cubic(tb["Compressor inlet temperature"], cit[idx], 2) * cubic(tb["Ambient specific humidity"], spec[idx], 2)
              * cubic(tb["Inlet loss"], inl, 2) * cubic(tb["Exhaust loss"], x.pdt201_exhaust_kpa_g[idx], 2))
        results[nm] = (float(np.mean(ppf / fo)) / 1000.0, float(np.mean(3600.0 * qin / ppf / fh)))
    print("Independent reduction of the GT-1 test\n")
    print("runs used: %s" % ", ".join(sorted(results)))
    worst = 0.0
    for cond, letter in (("as_found", "A"), ("as_left", "L")):
        v = [results[k] for k in results if k.startswith(letter)]
        po, hr = np.mean([a for a, _ in v]), np.mean([b for _, b in v])
        mo, mh = 100 * (po / T.OUTPUT_MW[cond] - 1), 100 * (hr / T.HEAT_RATE[cond] - 1)
        worst = max(worst, abs(mo), abs(mh))
        print("%-9s output %.3f MW (true %.2f, %+.2f %%)   heat rate %.1f kJ/kWh (true %.0f, %+.2f %%)"
              % (cond, po, T.OUTPUT_MW[cond], mo, hr, T.HEAT_RATE[cond], mh))
    print("\nPT-102 zero %.3f kPa; RTD bias %s; fuel zero %s kg/s" % (a, {str(k.date()): round(v, 2) for k, v in bias.items()},
                                                                   {str(k.date()): round(float(v), 4) for k, v in zero.items()}))
    print("Largest miss: %.2f %%" % worst)


if __name__ == "__main__":
    main()
