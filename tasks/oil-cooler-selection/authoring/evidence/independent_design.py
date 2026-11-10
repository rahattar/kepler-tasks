"""A second cooler selection program, written apart from solution/design.py and sharing no code with it.

    python3 independent_design.py CASE_DIR OUT_JSON

Different choices: pandas with time-based rolling windows; a Hampel filter (rolling median and MAD) for instrument
glitches; the inlet water transmitter judged against the basin outlet by a 3-hour rolling median of their difference
(which also catches a frozen transmitter); the outlet temperature solved with scipy's brentq on the heat balance
instead of a damped fixed point; tube counts computed from the catalogue rule rather than read from the table; and
the baffle spacing searched on a 10 mm grid.
"""
import json
import math
import os
import sys

import numpy as np
import pandas as pd
from scipy.optimize import brentq

DOCS = "/app/data/docs"
SHELLS = [305, 337, 387, 438, 489, 540, 591, 635, 686, 737, 787, 838]
TUBES = {"19.05x1.65": (19.05, 1.65), "19.05x2.11": (19.05, 2.11), "25.40x2.11": (25.40, 2.11)}
TAB = {30: ([1e4, 1e3, 1e2, 10, 0], [0.321, 0.321, 0.593, 1.360, 1.400], [-0.388, -0.388, -0.477, -0.657, -0.667],
            [0.372, 0.486, 4.570, 45.10, 48.00], [-0.123, -0.152, -0.476, -0.973, -1.000], 1.450, 0.519, 7.00, 0.500),
       90: ([1e4, 1e3, 1e2, 10, 0], [0.370, 0.107, 0.408, 0.900, 0.970], [-0.396, -0.266, -0.460, -0.631, -0.667],
            [0.391, 0.0815, 6.0900, 32.10, 35.00], [-0.148, 0.022, -0.602, -0.963, -1.000], 1.187, 0.370, 6.30, 0.378)}


# ---------------------------------------------------------------- properties
def visc_cst(T, n40, n100):
    lg = np.log10
    w1, w2 = lg(lg(n40 + 0.7)), lg(lg(n100 + 0.7))
    slope = (w2 - w1) / (lg(373.15) - lg(313.15))
    return 10 ** (10 ** (w1 + slope * (lg(T + 273.15) - lg(313.15)))) - 0.7


def oil(T, o):
    rho = o["rho15"] * (1 - 0.00065 * (T - 15))
    return dict(rho=rho, cp=1800 + 3.6 * T, k=0.134 - 7e-5 * T, mu=visc_cst(T, o["nu40"], o["nu100"]) * 1e-6 * rho)


def water(T):
    return dict(rho=1000.6 - 0.0128 * T ** 1.76, cp=4180.0, k=0.569 + 0.00188 * T - 7.5e-6 * T * T,
                mu=2.414e-5 * 10 ** (247.8 / (T + 133.15)))


# ---------------------------------------------------------------- RS-12
class Cooler:
    def __init__(self, shell, tube, L, passes, layout, cut, spacing, nshell):
        od, wall = TUBES[tube]
        self.do, self.di = od / 1e3, (od - 2 * wall) / 1e3
        self.Ds, self.L, self.np, self.lay, self.ns = shell / 1e3, L, passes, layout, nshell
        self.pt = 1.25 * self.do
        Dotl_mm = shell - (12.0 + 0.005 * shell)
        self.Nt = int({2: 0.90, 4: 0.85, 6: 0.80}[passes] * math.pi * Dotl_mm ** 2 / 4 /
                      ((0.866 if layout == 30 else 1.0) * (1.25 * od) ** 2))
        self.B = spacing / 1e3
        bc = cut / 100
        lbb = (12.0 + 0.005 * shell) / 1e3
        lsb = (3.1 + 0.004 * shell) / 1e3
        dotl = self.Ds - lbb
        dctl = dotl - self.do
        pp = self.pt * (0.8660254 if layout == 30 else 1.0)
        self.Sm = self.B * (lbb + dctl * (self.pt - self.do) / self.pt)
        th_ds = 2 * math.acos(1 - 2 * bc)
        th_c = 2 * math.acos(self.Ds * (1 - 2 * bc) / dctl)
        fw = (th_c - math.sin(th_c)) / (2 * math.pi)
        self.Fc = 1 - 2 * fw
        self.Sw = self.Ds ** 2 / 8 * (th_ds - math.sin(th_ds)) - self.Nt * fw * math.pi * self.do ** 2 / 4
        ssb = math.pi * self.Ds * lsb / 2 * (1 - th_ds / (2 * math.pi))
        stb = math.pi / 4 * ((self.do + 0.0008) ** 2 - self.do ** 2) * self.Nt * (1 - fw)
        self.rs, self.rlm = ssb / (ssb + stb), (ssb + stb) / self.Sm
        self.fsbp = self.B * (self.Ds - dotl) / self.Sm
        self.ncc = self.Ds * (1 - 2 * bc) / pp
        self.ncw = 0.8 * (self.Ds * bc - (self.Ds - dctl) / 2) / pp
        self.Nb = max(1, int(round(L / self.B)) - 1)
        self.Dw = 4 * self.Sw / (math.pi * self.do * self.Nt * fw + self.Ds * th_ds)
        self.Aone = self.Nt * math.pi * self.do * L

    def shell(self, m, T, Tw, o):
        p, pw = oil(T, o), oil(Tw, o)
        Re = self.do * m / (p["mu"] * self.Sm)
        lims, a1s, a2s, b1s, b2s, a3, a4, b3, b4 = TAB[self.lay]
        i = next(j for j, lo in enumerate(lims) if Re >= lo)
        ji = a1s[i] * (1.33 / 1.25) ** (a3 / (1 + 0.14 * Re ** a4)) * Re ** a2s[i]
        fi = b1s[i] * (1.33 / 1.25) ** (b3 / (1 + 0.14 * Re ** b4)) * Re ** b2s[i]
        jl = 0.44 * (1 - self.rs) + (1 - 0.44 * (1 - self.rs)) * math.exp(-2.2 * self.rlm)
        jb = math.exp(-(1.25 if Re < 100 else 1.35) * self.fsbp)
        if Re >= 100:
            jr = 1.0
        else:
            j20 = (10 / ((self.ncc + self.ncw) * (self.Nb + 1))) ** 0.18
            jr = j20 if Re <= 20 else j20 + (20 - Re) / 80 * (j20 - 1)
        g = m / self.Sm
        visc = (p["mu"] / pw["mu"]) ** 0.14
        h = ji * p["cp"] * g * (p["cp"] * p["mu"] / p["k"]) ** (-2 / 3) * visc * (0.55 + 0.72 * self.Fc) * jl * jb * jr
        dpi = 2 * fi * self.ncc * g * g / p["rho"] / visc
        rl = math.exp(-1.33 * (1 + self.rs) * self.rlm ** (0.8 - 0.15 * (1 + self.rs)))
        rb = math.exp(-(4.5 if Re < 100 else 3.7) * self.fsbp)
        mw = m / math.sqrt(self.Sm * self.Sw)
        if Re >= 100:
            win = self.Nb * (2 + 0.6 * self.ncw) * mw * mw / (2 * p["rho"]) * rl
        else:
            win = self.Nb * (26 * p["mu"] * mw / p["rho"] * (self.ncw / (self.pt - self.do) + self.B / self.Dw ** 2)
                             + mw * mw / p["rho"]) * rl
        return h, dpi * (self.Nb - 1) * rb * rl + win + 2 * dpi * (1 + self.ncw / self.ncc) * rb

    def tubes(self, m, T):
        w = water(T)
        v = m / (w["rho"] * self.Nt / self.np * math.pi * self.di ** 2 / 4)
        Re = w["rho"] * v * self.di / w["mu"]
        f = 1 / (0.790 * math.log(Re) - 1.64) ** 2
        Pr = w["cp"] * w["mu"] / w["k"]
        nu = f / 8 * (Re - 1000) * Pr / (1 + 12.7 * math.sqrt(f / 8) * (Pr ** (2 / 3) - 1)) if Re > 2300 else 3.66
        return nu * w["k"] / self.di, self.np * (f * self.L / self.di + 2.5) * w["rho"] * v * v / 2, v

    def rate(self, b):
        o, mo, mc, thi, tci = b["oil"], b["oil_kg_s"], b["cw_kg_s"], b["oil_in_c"], b["cw_in_c"]
        out = {}

        def residual(tho):
            tco = tci + mo * oil(0.5 * (thi + tho), o)["cp"] * (thi - tho) / (mc * 4180)
            tmo, tmc = 0.5 * (thi + tho), 0.5 * (tci + tco)
            tw = tmc + 0.35 * (tmo - tmc)
            for _ in range(4):
                hs, dps = self.shell(mo, tmo, tw, o)
                ht, dpt, v = self.tubes(mc, tmc)
                rfi = 0.000176 if v > 0.9 else 0.000352
                U = 1 / (1 / hs + 0.000176 + self.do * math.log(self.do / self.di) / 90 + rfi * self.do / self.di
                         + self.do / (self.di * ht))
                tw = tmo - U * (tmo - tmc) / hs
            ch, cc = mo * oil(tmo, o)["cp"], mc * 4180.0
            cmin, cr = min(ch, cc), min(ch, cc) / max(ch, cc)
            n = U * self.Aone / cmin
            s = math.sqrt(1 + cr * cr)
            e1 = 2 / (1 + cr + s * (1 + math.exp(-n * s)) / (1 - math.exp(-n * s)))
            if abs(cr - 1) < 1e-9:
                e = self.ns * e1 / (1 + (self.ns - 1) * e1)
            else:
                q = ((1 - e1 * cr) / (1 - e1)) ** self.ns
                e = (q - 1) / (q - cr)
            out.update(dps=dps * self.ns / 1e3, dpt=dpt * self.ns / 1e3, v=v)
            return tho - (thi - e * cmin * (thi - tci) / ch)
        tho = brentq(residual, tci + 0.01, thi - 0.01, xtol=1e-5)
        residual(tho)
        return tho, out["dps"], out["dpt"], out["v"]


def price(c):
    return round(9000 + 26.0 * c.Ds * 1e3 * c.L + 210.0 * c.Aone + 450.0 * c.np + (600 if c.lay == 90 else 0), -1) * c.ns


# ---------------------------------------------------------------- records
def basis(case_dir):
    case = json.load(open(os.path.join(case_dir, "case.json")))
    inst = pd.read_csv(os.path.join(case_dir, "instruments.csv"))
    tr = pd.read_csv(os.path.join(case_dir, "trend.csv"), parse_dates=["time"]).set_index("time")
    tr = tr.loc[case["period"][0]:case["period"][1] + " 23:59"]
    cal = pd.read_csv(os.path.join(case_dir, "calibration.csv"))
    for _, c in cal[cal.adjusted.str.strip().str.lower() == "yes"].iterrows():
        pre = tr.index < pd.Timestamp(c.date)
        if "%" in c.error_unit:
            tr.loc[pre, c.tag] = tr.loc[pre, c.tag] / (1 + c.as_found_error / 100)
        else:
            tr.loc[pre, c.tag] = tr.loc[pre, c.tag] - c.as_found_error

    def tag(meas, where=None):
        sel = inst[inst.measurement == meas]
        if where:
            sel = sel[sel.location.str.contains(where)]
        return sel.tag.iloc[0]

    def hampel(s, k=5, n=6.0, floor=1.0):
        med = s.rolling(2 * k + 1, center=True, min_periods=1).median()
        mad = (s - med).abs().rolling(2 * k + 1, center=True, min_periods=1).median() * 1.4826
        return s.where((s - med).abs() <= np.maximum(n * mad, floor), med)
    flow = hampel(tr[tag("oil flow")], floor=0.15 * tr[tag("oil flow")].median())
    oil_in = hampel(tr[tag("oil temperature")], floor=12.0)
    ci = hampel(tr[tag("cooling water temperature", "inlet")], floor=4.0)
    other = [t for t in inst[inst.measurement == "cooling water temperature"].tag if t != ci.name][0]
    ch = hampel(tr[other], floor=4.0)
    diff = ci - ch
    base = diff.median()
    good = (diff - base).abs().rolling("3h", center=True).median() < 0.8
    cw = ci.where(good, ch + base)

    def peak(s):
        return float(s.rolling("60min").mean()[s.index >= s.index[0] + pd.Timedelta("50min")].max())
    an = pd.read_csv(os.path.join(case_dir, "oil_analysis.csv")).sort_values("sample_date").iloc[-1]
    o = dict(rho15=float(an.density_15c_kg_m3), nu40=float(an.viscosity_40c_cst), nu100=float(an.viscosity_100c_cst))
    log = pd.read_csv(os.path.join(case_dir, "maintenance.csv"))
    grades = pd.read_csv(os.path.join(DOCS, "oil_grades.csv")).set_index("oil")
    for _, e in log[log.date > an.sample_date].sort_values("date").iterrows():
        for g in grades.index:
            if "refilled with " + g in e.text:
                o = dict(rho15=float(grades.loc[g, "density_15c_kg_m3"]), nu40=float(grades.loc[g, "viscosity_40c_cst"]),
                         nu100=float(grades.loc[g, "viscosity_100c_cst"]))
    return case, dict(oil=o, oil_kg_s=peak(flow), oil_in_c=peak(oil_in), cw_in_c=peak(cw),
                      cw_kg_s=float(case["cw_allotment_kg_s"]))


def feasible(c, case, b):
    try:
        tho, dps, dpt, v = c.rate(b)
    except (ValueError, ZeroDivisionError, OverflowError):
        return False
    return (tho <= case["oil_outlet_max_c"] and dps <= case["oil_dp_max_kpa"] and dpt <= case["cw_dp_max_kpa"]
            and case["cw_velocity_m_s"][0] <= v <= case["cw_velocity_m_s"][1])


def main(case_dir, out):
    case, b = basis(case_dir)
    configs = []
    for s in SHELLS:
        for tk, (od, _) in TUBES.items():
            for L in (2.44, 3.66, 4.88, 6.10):
                for npass in (2, 4, 6):
                    for lay in (30, 90):
                        for ns in (1, 2, 3):
                            c = Cooler(s, tk, L, npass, lay, 25, s, ns)
                            if c.Nt >= 20:
                                configs.append((price(c), s, tk, L, npass, lay, ns))
    configs.sort()
    for p, s, tk, L, npass, lay, ns in configs:
        od = TUBES[tk][0]
        lo, hi = int(math.ceil(max(0.2 * s, 50))), int(min(s, (1524.0 if od < 20 else 1880.0) / 2))
        probe = Cooler(s, tk, L, npass, lay, 25, lo, ns)
        _, dpt, v = probe.tubes(b["cw_kg_s"], b["cw_in_c"] + 4.0)
        if not (0.95 * case["cw_velocity_m_s"][0] <= v <= 1.05 * case["cw_velocity_m_s"][1]) or \
                dpt * ns / 1e3 > 1.1 * case["cw_dp_max_kpa"]:
            continue                                   # the water side does not depend on the baffles
        for cut in (20, 25, 35):
            ok = [sp for sp in range(lo, hi + 1, 10) if feasible(Cooler(s, tk, L, npass, lay, cut, sp, ns), case, b)]
            if not ok:
                continue
            with open(out, "w") as f:
                json.dump(dict(shell_id_mm=s, tube=tk, tube_length_m=L, tube_passes=npass, layout_deg=lay,
                               baffle_cut_pct=cut, baffle_spacing_mm=ok[0], shells_in_series=ns), f, indent=1)
            return
    raise SystemExit("no design")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
