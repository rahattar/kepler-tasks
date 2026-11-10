"""A second GT-1 reduction program, written apart from solution/gtperf.py and sharing no code with it.

    python3 independent_gtperf.py RECORD_DIR OUT_CSV

Different choices: the record files are read with the csv module, not pandas; the base-load window is found from the
last qualifying minute backwards; frozen RTDs are found by their distinct readings; rest is found from zero generator frequency once the rotor has coasted below
5 % speed, and each instrument's error at rest is a 20 % trimmed mean; the correction tables are read from the OEM document's markdown at run time, not
embedded; the LHV is computed from each sample's mass fractions; IAPWS-IF97 saturation pressure; corrections are
applied minute by minute and the 30 corrected minutes averaged.
"""
import csv
import math
import os
import sys
from datetime import datetime, timedelta

DOCS = "/app/data/docs"                       # read at run time, as in the agent's environment and the verifier image
NET = {"CH4": (802.69, 16.043), "C2H6": (1428.84, 30.069), "C3H8": (2043.37, 44.096), "iC4H10": (2648.42, 58.122),
       "nC4H10": (2657.60, 58.122), "neoC5H12": (3250.48, 72.149), "iC5H12": (3265.08, 72.149),
       "nC5H12": (3272.00, 72.149), "nC6H14": (3887.21, 86.175), "H2": (241.72, 2.016), "He": (0.0, 4.0026),
       "N2": (0.0, 28.0135), "CO2": (0.0, 44.010), "O2": (0.0, 31.9988)}


def tables():
    out, cur = {}, None
    for line in open(os.path.join(DOCS, "oem_correction_curves.md")):
        if line.startswith("## "):
            cur = line[3:].strip()
            out[cur] = []
        elif cur and line.startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            try:
                out[cur].append(tuple(float(c) for c in cells))
            except ValueError:
                pass
    return out


def lookup(rows, x, k):
    xs = [r[0] for r in rows]
    if x <= xs[1]:
        i = 0
    elif x >= xs[-2]:
        i = len(xs) - 2
    else:
        i = max(j for j in range(len(xs) - 1) if xs[j] <= x)
    x0, x1, y0, y1 = xs[i], xs[i + 1], rows[i][k], rows[i + 1][k]
    return y0 + (x - x0) * (y1 - y0) / (x1 - x0)


def psat_kpa(t):
    n = [0.11670521452767e4, -0.72421316703206e6, -0.17073846940092e2, 0.12020824702470e5, -0.32325550322333e7,
         0.14915108613530e2, -0.48232657361591e4, 0.40511340542057e6, -0.23855557567849, 0.65017534844798e3]
    T = t + 273.15
    th = T + n[8] / (T - n[9])
    A, B, C = th * th + n[0] * th + n[1], n[2] * th * th + n[3] * th + n[4], n[5] * th * th + n[6] * th + n[7]
    return (2 * C / (-B + math.sqrt(B * B - 4 * A * C))) ** 4 * 1000.0


def trimmed(v, cut=0.2):
    v = sorted(v)
    k = int(len(v) * cut)
    v = v[k:len(v) - k] or v
    return sum(v) / len(v)


def rows_of(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def stamp(s):
    return datetime.strptime(s.strip()[:16], "%Y-%m-%d %H:%M")


def main(test_dir, out_path):
    T = tables()
    tc, ti, te, th = (T["Compressor inlet temperature"], T["Inlet loss"], T["Exhaust loss"],
                      T["Ambient specific humidity"])
    das = {stamp(r["time"]): r for r in rows_of(os.path.join(test_dir, "test_das_1min.csv"))}
    dcs = {stamp(r["time"]): r for r in rows_of(os.path.join(test_dir, "dcs_1min.csv"))}
    day = min(das).date()
    # RTD channels in service: not flagged -999 and not frozen (more than two distinct readings over the day)
    live = [i for i in range(1, 9)
            if len({das[t]["cit_%d_c" % i] for t in das if float(das[t]["cit_%d_c" % i]) > -998.0}) > 2]
    # instrument verification at rest: zero frequency and the rotor below 5 % speed
    rest = [t for t in sorted(das) if float(das[t]["freq_hz"]) == 0.0 and float(das[t]["speed_pct"]) < 5.0 and t in dcs]

    def baro(m):
        return float(m["met_baro_kpa"]) if "met_baro_kpa" in m else float(m["met_baro_hpa"]) / 10.0

    def fuel(r):
        return float(r["fuel_coriolis_kg_s"]) if "fuel_coriolis_kg_s" in r else float(r["fuel_coriolis_kg_h"]) / 3600.0
    z_pt = z_fuel = 0.0
    z_rtd = [0.0] * 9
    if rest:
        z_pt = trimmed([float(das[t]["pt102_inlet_total_kpa_abs"]) - baro(dcs[t]) for t in rest])
        z_fuel = trimmed([fuel(das[t]) for t in rest])
        for i in live:
            v = [float(das[t]["cit_%d_c" % i]) - float(dcs[t]["met_dry_bulb_c"]) for t in rest
                 if float(das[t]["cit_%d_c" % i]) > -998.0]
            z_rtd[i] = trimmed(v) if v else 0.0
    # LHV from mass fractions of each of the test day's samples
    vals = []
    for r in rows_of(os.path.join(test_dir, "gas_analysis.csv")):
        if stamp(r["sample_time"]).date() != day:
            continue
        mol = {c: float(v) / 100.0 for c, v in r.items() if c in NET and v not in ("", None)}
        mass = sum(x * NET[c][1] for c, x in mol.items())
        vals.append(sum((x * NET[c][1] / mass) * (NET[c][0] / NET[c][1]) for c, x in mol.items()) * 1000.0)
    lhv = sum(vals) / len(vals)
    # runs
    st, en, ab = {}, {}, set()
    for r in rows_of(os.path.join(test_dir, "test_log.csv")):
        w = r["entry"].split()
        if len(w) == 3 and w[0] == "Run":
            {"start": st, "end": en}.get(w[2], {})[w[1]] = stamp(r["time"])
            if w[2] == "aborted":
                ab.add(w[1])
    results = []
    for name in st:
        if name in ab or name not in en:
            continue
        minutes = [t for t in sorted(das) if st[name] < t <= en[name]]

        def good(t):
            r = das[t]
            return float(r["igv_deg"]) >= 85.5 and abs(float(r["texh_avg_c"]) - float(r["ttrf_c"])) <= 3.0
        pick = None
        for i in range(len(minutes) - 29):
            block = minutes[i:i + 30]
            if block[-1] - block[0] == timedelta(minutes=29) and all(good(t) for t in block):
                pick = block
                break
        if pick is None:
            continue
        P = sum(float(das[t]["gen_mw_jt001"]) for t in pick) / 30 * 1000.0
        Q = sum(float(das[t]["gen_mvar_jt001"]) for t in pick) / 30 * 1000.0
        pf = P / math.sqrt(P * P + Q * Q)
        loss = lambda pk, f: 410.0 + 560.0 * (pk / 1000.0 / f / 56.0) ** 2
        ppf = P + loss(P, pf) - loss(P, 0.85)
        outs, hrs = [], []
        for t in pick:
            r, m = das[t], dcs[t]
            p = baro(m)
            mf = fuel(r) - z_fuel
            cits = [float(r["cit_%d_c" % i]) - z_rtd[i] for i in live if float(r["cit_%d_c" % i]) > -998.0]
            cit = sum(cits) / len(cits)
            pv = float(m["met_rh_pct"]) / 100.0 * psat_kpa(float(m["met_dry_bulb_c"]))
            w = 0.621945 * pv / (p - pv)
            di, de = p - (float(r["pt102_inlet_total_kpa_abs"]) - z_pt), float(r["pdt201_exhaust_kpa_g"])
            heat = mf * (lhv + 2.20 * (float(r["te305_fuel_skid_c"]) - 15.0))
            fo = lookup(tc, cit, 1) * p / 101.325 * lookup(th, w, 1) * lookup(ti, di, 1) * lookup(te, de, 1)
            fh = lookup(tc, cit, 2) * lookup(th, w, 2) * lookup(ti, di, 2) * lookup(te, de, 2)
            outs.append(ppf / fo)
            hrs.append(3600.0 * heat / ppf / fh)
        results.append((sum(outs) / 30 / 1000.0, sum(hrs) / 30))
    po = sum(r[0] for r in results) / len(results)
    hr = sum(r[1] for r in results) / len(results)
    with open(out_path, "w") as f:
        f.write("corrected_output_mw,corrected_heat_rate_kj_kwh\n%.4f,%.2f\n" % (po, hr))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
