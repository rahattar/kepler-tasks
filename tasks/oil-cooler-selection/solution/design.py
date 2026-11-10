"""Lube oil cooler selection program (reference).

    python3 design.py CASE_DIR OUT_JSON

Reads a cooler case package (case.json, trend.csv, instruments.csv, calibration.csv, maintenance.csv,
oil_analysis.csv), sets up the design case from the true process values, and writes the cheapest catalogue design
that meets every requirement at that case under the plant rating standard RS-12.

Before the trend is used: readings before an adjusting calibration are corrected by the as-found error; a
transmitter that sends the same value for an hour or more is frozen and its readings there are replaced from the
redundant cooling water measurement (offset from the hours when both are live); a single 10-minute value that jumps
far beyond what the process can do and comes straight back is an instrument glitch and is replaced by its neighbours;
and where the cooling water inlet transmitter wanders away from the basin outlet measurement it is not measuring the
water (for example out of its thermowell) and the basin outlet measurement, offset, is used instead.
"""
import csv
import json
import math
import os
import sys

import numpy as np

# ------------------------------------------------------------------ catalogue (vendor_catalogue.md)
SHELLS = [305, 337, 387, 438, 489, 540, 591, 635, 686, 737, 787, 838]
TUBES = {"19.05x1.65": (19.05, 1.65), "19.05x2.11": (19.05, 2.11), "25.40x2.11": (25.40, 2.11)}
LENGTHS = [2.44, 3.66, 4.88, 6.10]
SPAN = {19.05: 1524.0, 25.40: 1880.0}
GRADE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "oil_grades.csv")
DOCS = "/app/data/docs"


def price(shell, L, nt, od, passes, layout):
    area = nt * math.pi * od / 1000 * L
    return round(9000 + 26.0 * shell * L + 210.0 * area + 450.0 * passes + (600 if layout == 90 else 0), -1)


# ------------------------------------------------------------------ rating standard RS-12
COEF = {
    30: ([(1e4, 0.321, -0.388, 0.372, -0.123), (1e3, 0.321, -0.388, 0.486, -0.152), (1e2, 0.593, -0.477, 4.570, -0.476),
          (10, 1.360, -0.657, 45.10, -0.973), (0, 1.400, -0.667, 48.00, -1.000)], (1.450, 0.519, 7.00, 0.500)),
    90: ([(1e4, 0.370, -0.396, 0.391, -0.148), (1e3, 0.107, -0.266, 0.0815, 0.022), (1e2, 0.408, -0.460, 6.0900, -0.602),
          (10, 0.900, -0.631, 32.10, -0.963), (0, 0.970, -0.667, 35.00, -1.000)], (1.187, 0.370, 6.30, 0.378)),
}


def nu_d341(T, nu40, nu100):
    z = lambda nu: math.log10(math.log10(nu + 0.7))  # noqa: E731
    t1, t2 = math.log10(313.15), math.log10(373.15)
    B = (z(nu40) - z(nu100)) / (t2 - t1)
    A = z(nu40) + B * t1
    return 10 ** (10 ** (A - B * math.log10(T + 273.15))) - 0.7


def oil_p(T, oil):
    rho = oil["rho15"] * (1 - 0.00065 * (T - 15.0))
    return rho, 1000.0 * (1.80 + 0.0036 * T), 0.134 - 0.00007 * T, nu_d341(T, oil["nu40"], oil["nu100"]) * 1e-6 * rho


def water_p(T):
    return 1000.6 - 0.0128 * T ** 1.76, 4180.0, 0.569 + 0.00188 * T - 7.5e-6 * T * T, \
        2.414e-5 * 10 ** (247.8 / (T + 273.15 - 140.0))


def rate(d, b):
    do = d["od"] / 1000
    di = do - 2 * d["wall"] / 1000
    Ds = d["shell"] / 1000
    Pt = 1.25 * do
    Lbc = d["spacing"] / 1000
    Bc = d["cut"] / 100
    lay, Nt, L = d["layout"], d["tubes"], d["length"]
    Lsb = (3.1 + 0.004 * d["shell"]) / 1000
    Ltb = 0.0008
    Lbb = (12.0 + 0.005 * d["shell"]) / 1000
    Dotl = Ds - Lbb
    Dctl = Dotl - do
    Pp = Pt * (math.cos(math.radians(30)) if lay == 30 else 1.0)
    Sm = Lbc * (Lbb + Dctl / Pt * (Pt - do))
    tds = 2 * math.acos(1 - 2 * Bc)
    tct = 2 * math.acos(Ds / Dctl * (1 - 2 * Bc))
    Fw = (tct - math.sin(tct)) / (2 * math.pi)
    Fc = 1 - 2 * Fw
    Sw = Ds * Ds / 8 * (tds - math.sin(tds)) - Nt * Fw * math.pi * do * do / 4
    Ssb = math.pi * Ds * Lsb / 2 * (1 - tds / (2 * math.pi))
    Stb = math.pi / 4 * ((do + Ltb) ** 2 - do * do) * Nt * (1 - Fw)
    Sb = Lbc * (Ds - Dotl)
    Ntcc = Ds * (1 - 2 * Bc) / Pp
    Ntcw = 0.8 * (Ds * Bc - (Ds - Dctl) / 2) / Pp
    Nb = max(1, int(round(L / Lbc)) - 1)
    rs = Ssb / (Ssb + Stb)
    rlm = (Ssb + Stb) / Sm
    rows, (a3, a4, b3, b4) = COEF[lay]
    oil, mo, mc = b["oil"], b["oil_kg_s"], b["cw_kg_s"]
    Thi, Tci, Ns = b["oil_in_c"], b["cw_in_c"], d["shells"]
    Aone = Nt * math.pi * do * L
    Tho = Thi - 25.0
    res = None
    for _ in range(60):
        cpo = oil_p(0.5 * (Thi + Tho), oil)[1]
        Tco = Tci + mo * cpo * (Thi - Tho) / (mc * 4180.0)
        Tmo, Tmc = 0.5 * (Thi + Tho), 0.5 * (Tci + Tco)
        Tw = Tmc + 0.35 * (Tmo - Tmc)
        for _ in range(4):
            rho, cp, k, mu = oil_p(Tmo, oil)
            muw = oil_p(Tw, oil)[3]
            Re = do * mo / (mu * Sm)
            for Rmin, a1, a2, b1, b2 in rows:
                if Re >= Rmin:
                    break
            ji = a1 * (1.33 / 1.25) ** (a3 / (1 + 0.14 * Re ** a4)) * Re ** a2
            fi = b1 * (1.33 / 1.25) ** (b3 / (1 + 0.14 * Re ** b4)) * Re ** b2
            Jc = 0.55 + 0.72 * Fc
            Jl = 0.44 * (1 - rs) + (1 - 0.44 * (1 - rs)) * math.exp(-2.2 * rlm)
            Jb = math.exp(-(1.25 if Re < 100 else 1.35) * Sb / Sm)
            if Re >= 100:
                Jr = 1.0
            else:
                j20 = (10.0 / ((Ntcc + Ntcw) * (Nb + 1))) ** 0.18
                Jr = j20 if Re <= 20 else j20 + (20 - Re) / 80.0 * (j20 - 1)
            G = mo / Sm
            hs = ji * cp * G * (cp * mu / k) ** (-2 / 3) * (mu / muw) ** 0.14 * Jc * Jl * Jb * Jr
            dPbi = 2 * fi * Ntcc * G * G / rho * (muw / mu) ** 0.14
            Rl = math.exp(-1.33 * (1 + rs) * rlm ** (0.8 - 0.15 * (1 + rs)))
            Rb = math.exp(-(4.5 if Re < 100 else 3.7) * Sb / Sm)
            mw = mo / math.sqrt(Sm * Sw)
            if Re >= 100:
                dPw = Nb * (2 + 0.6 * Ntcw) * mw * mw / (2 * rho) * Rl
            else:
                Dw = 4 * Sw / (math.pi * do * Nt * Fw + Ds * tds)
                dPw = Nb * (26 * mu * mw / rho * (Ntcw / (Pt - do) + Lbc / Dw ** 2) + mw * mw / rho) * Rl
            dPs = dPbi * (Nb - 1) * Rb * Rl + dPw + 2 * dPbi * (1 + Ntcw / Ntcc) * Rb
            rw, cpw, kw_, muw_ = water_p(Tmc)
            v = mc / (rw * (Nt / d["passes"]) * math.pi * di * di / 4)
            Ret = rw * v * di / muw_
            f = (0.790 * math.log(Ret) - 1.64) ** -2
            Pr = cpw * muw_ / kw_
            Nu = (f / 8) * (Ret - 1000) * Pr / (1 + 12.7 * math.sqrt(f / 8) * (Pr ** (2 / 3) - 1)) if Ret > 2300 else 3.66
            ht = Nu * kw_ / di
            dPt = d["passes"] * (f * L / di + 2.5) * rw * v * v / 2
            Rfi = 0.000176 if v > 0.9 else 0.000352
            U = 1 / (1 / hs + 0.000176 + do * math.log(do / di) / (2 * 45.0) + Rfi * do / di + do / (di * ht))
            Tw = Tmo - U * (Tmo - Tmc) / hs
        Ch, Cc = mo * oil_p(Tmo, oil)[1], mc * 4180.0
        Cmin, Cmax = min(Ch, Cc), max(Ch, Cc)
        Cr = Cmin / Cmax
        n1 = U * Aone / Cmin
        s = math.sqrt(1 + Cr * Cr)
        e1 = 2 / (1 + Cr + s * (1 + math.exp(-n1 * s)) / (1 - math.exp(-n1 * s)))
        if abs(Cr - 1) < 1e-9:
            e = Ns * e1 / (1 + (Ns - 1) * e1)
        else:
            q = ((1 - e1 * Cr) / (1 - e1)) ** Ns
            e = (q - 1) / (q - Cr)
        new = Thi - e * Cmin * (Thi - Tci) / Ch
        if abs(new - Tho) < 1e-4:
            Tho = new
            break
        Tho = 0.5 * (Tho + new)
    return Tho, dPs * Ns / 1000, dPt * Ns / 1000, v


# ------------------------------------------------------------------ records
def read(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def tube_count(shell, od, layout, passes):
    ctp = {2: 0.90, 4: 0.85, 6: 0.80}[passes]
    pt = 1.25 * od
    Dotl = shell - (12.0 + 0.005 * shell)
    return int(ctp * math.pi * Dotl ** 2 / 4 / ((0.866 if layout == 30 else 1.0) * pt * pt))


def counts_table():
    for p in (os.path.join(DOCS, "vendor_catalogue_tube_counts.csv"), "vendor_catalogue_tube_counts.csv"):
        if os.path.exists(p):
            return {(int(r["shell_id_mm"]), r["tube"], int(r["layout_deg"]), int(r["tube_passes"])): int(r["tubes"])
                    for r in read(p)}
    return None


def clean_glitches(x, limit):
    """A single value far from both neighbours, which agree with each other, is an instrument glitch."""
    x = x.copy()
    for i in range(1, len(x) - 1):
        a, b = x[i - 1], x[i + 1]
        if abs(a - b) < limit / 3 and abs(x[i] - 0.5 * (a + b)) > limit:
            x[i] = 0.5 * (a + b)
    return x


def frozen_mask(x, n=6):
    """Readings of a transmitter that sends exactly the same value for n or more samples (an hour)."""
    same = np.concatenate([[False], np.diff(x) == 0])
    m = np.zeros(len(x), bool)
    run = 0
    for i in range(len(x)):
        run = run + 1 if same[i] else 0
        if run >= n - 1:
            m[i - run:i + 1] = True
    return m


def hour_max(t, x):
    """Highest one-hour mean, on the time axis."""
    s = (t - t[0]).astype("timedelta64[m]").astype(float)
    best = -1e9
    j = 0
    cs = np.concatenate([[0.0], np.cumsum(x)])
    for i in range(len(x)):
        while s[i] - s[j] >= 60.0:
            j += 1
        if s[i] - s[j] >= 50.0 - 1e-9:
            best = max(best, (cs[i + 1] - cs[j]) / (i + 1 - j))
    return best


def design_case(case_dir):
    case = json.load(open(os.path.join(case_dir, "case.json")))
    inst = read(os.path.join(case_dir, "instruments.csv"))
    trend = read(os.path.join(case_dir, "trend.csv"))
    t = np.array([np.datetime64(r["time"].replace(" ", "T")) for r in trend])
    p0, p1 = np.datetime64(case["period"][0]), np.datetime64(case["period"][1]) + np.timedelta64(1, "D")
    keep = (t >= p0) & (t < p1)
    t = t[keep]
    col = {r["tag"]: np.array([float(q[r["tag"]]) for q in trend])[keep] for r in inst}
    for c in read(os.path.join(case_dir, "calibration.csv")):
        if c["adjusted"].strip().lower() != "yes" or c["tag"] not in col:
            continue
        e = float(c["as_found_error"])
        before = t < np.datetime64(c["date"])
        x = col[c["tag"]]
        if "%" in c["error_unit"]:
            col[c["tag"]] = np.where(before, x / (1 + e / 100.0), x)
        else:
            col[c["tag"]] = np.where(before, x - e, x)
    flow_tag = [r["tag"] for r in inst if r["measurement"] == "oil flow"][0]
    oil_tag = [r["tag"] for r in inst if r["measurement"] == "oil temperature"][0]
    cw = [r for r in inst if r["measurement"] == "cooling water temperature"]
    cw_tag = [r["tag"] for r in cw if "inlet" in r["location"]][0]
    hdr_tag = [r["tag"] for r in cw if r["tag"] != cw_tag][0]
    flow = clean_glitches(col[flow_tag], 0.25 * np.median(col[flow_tag]))
    oil_in = clean_glitches(col[oil_tag], 20.0)
    ci = clean_glitches(col[cw_tag], 5.0)
    ch = clean_glitches(col[hdr_tag], 5.0)
    bad = frozen_mask(ci)
    ok = ~bad & ~frozen_mask(ch)
    offset = float(np.median(ci[ok] - ch[ok]))
    # the inlet transmitter must track the basin outlet; where it wanders away from it (out of its thermowell,
    # reading air) it is not measuring the water
    dev = np.abs(ci - ch - offset)
    k = 6
    roll = np.array([np.median(dev[max(0, i - k):i + k + 1]) for i in range(len(dev))])
    bad |= roll > 0.8
    cwin = np.where(bad, ch + offset, ci)
    # oil in service
    an = sorted(read(os.path.join(case_dir, "oil_analysis.csv")), key=lambda r: r["sample_date"])[-1]
    oil = dict(rho15=float(an["density_15c_kg_m3"]), nu40=float(an["viscosity_40c_cst"]),
               nu100=float(an["viscosity_100c_cst"]))
    for e in sorted(read(os.path.join(case_dir, "maintenance.csv")), key=lambda r: r["date"]):
        if e["date"] > an["sample_date"] and "refilled with" in e["text"]:
            grade = e["text"].split("refilled with ")[1].split(" (")[0].strip().rstrip(".")
            for g in read(os.path.join(DOCS, "oil_grades.csv")):
                if g["oil"] == grade:
                    oil = dict(rho15=float(g["density_15c_kg_m3"]), nu40=float(g["viscosity_40c_cst"]),
                               nu100=float(g["viscosity_100c_cst"]))
    return case, dict(oil=oil, oil_kg_s=hour_max(t, flow), oil_in_c=hour_max(t, oil_in), cw_in_c=hour_max(t, cwin),
                      cw_kg_s=float(case["cw_allotment_kg_s"]))


def select(case, b):
    table = counts_table()
    cands = []
    for s in SHELLS:
        for tk, (od, wall) in TUBES.items():
            for L in LENGTHS:
                for npass in (2, 4, 6):
                    for lay in (30, 90):
                        nt = table.get((s, tk, lay, npass)) if table else tube_count(s, od, lay, npass)
                        if not nt:
                            continue
                        for ns in (1, 2, 3):
                            cands.append((price(s, L, nt, od, npass, lay) * ns, s, tk, od, wall, L, npass, lay, nt, ns))
    cands.sort()
    vmin, vmax = case["cw_velocity_m_s"]
    for p, s, tk, od, wall, L, npass, lay, nt, ns in cands:
        lo = int(math.ceil(max(0.2 * s, 50.0)))
        hi = int(min(s, SPAN[od] / 2))
        # the closest baffles give the most heat transfer: if no cut reaches the oil outlet limit there, none will
        reach = False
        for cut in (20, 25, 35):
            d = dict(shell=s, od=od, wall=wall, length=L, passes=npass, layout=lay, tubes=nt, shells=ns, cut=cut, spacing=lo)
            try:
                tho, dps, dpt, v = rate(d, b)
            except (ValueError, ZeroDivisionError, OverflowError):
                continue
            if not (vmin <= v <= vmax) or dpt > case["cw_dp_max_kpa"]:
                break
            reach = reach or tho <= case["oil_outlet_max_c"]
        if not reach:
            continue
        for cut in (20, 25, 35):
            for sp in range(lo, hi + 1, 5):
                d = dict(shell=s, od=od, wall=wall, length=L, passes=npass, layout=lay, tubes=nt, shells=ns, cut=cut,
                         spacing=sp)
                try:
                    tho, dps, dpt, v = rate(d, b)
                except (ValueError, ZeroDivisionError, OverflowError):
                    continue
                if not (vmin <= v <= vmax) or dpt > case["cw_dp_max_kpa"]:
                    break                                     # tube side does not depend on the baffles
                if tho <= case["oil_outlet_max_c"] and dps <= case["oil_dp_max_kpa"]:
                    return dict(shell_id_mm=s, tube=tk, tube_length_m=L, tube_passes=npass, layout_deg=lay,
                                baffle_cut_pct=cut, baffle_spacing_mm=sp, shells_in_series=ns)
    raise RuntimeError("no catalogue design meets the requirements")


def main():
    case_dir, out = sys.argv[1], sys.argv[2]
    case, b = design_case(case_dir)
    sel = select(case, b)
    with open(out, "w") as f:
        json.dump(sel, f, indent=1)


if __name__ == "__main__":
    main()
