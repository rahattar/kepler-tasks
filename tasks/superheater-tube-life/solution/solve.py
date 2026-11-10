"""Reference solution for superheater-tube-life.

    python3 solve.py DATA_DIR OUT_CSV

Applies PS-14 day by day to every element from its entry into service, with the October 2026 outage inspection
(oxide on E3 and E8, wall on E9 and E10) where it settles what the records cannot. Records as found and how they are
read:
- historian temperatures in degF before the 2019-07-01 DCS upgrade (and the 2018 monthly summary); degC after;
- E7 and E8 columns swapped from the 2024-03-12 historian migration (E8's pickup falls to E7's level and back);
- E2's pad, refitted on the 2021 tube, reads high and E7's, renewed in 2020-02, reads low: each one's ratio to a neighbour
  (E1, E8) jumps on that date with no change of flux, so its pickup after it = the earlier ratio x the neighbour's;
- E5's pad drifts low from 2022-10: E5 = its earlier ratio to E2 x E2; E4 (from 2025-08), E6 (from 2025-01) likewise
  from E2; E9's new tube has no pad: its earlier ratio to E7;
- E3's pad dead from 2022-03 and the burner modification under E3/E4 changed its flux by an unknown amount: before the
  modification its earlier ratio to E2; after it a factor fitted so that the oxide grown since the May 2023 clean
  equals the measured oxide;
- 2018 from the monthly summary (hours, mean load, mean pad temperatures; header temperatures at their means);
- walls: E1 thins at the 2015-2019 rate plus, from IK-14's entry (2021-04), the extra rate the 2023 survey shows;
  E9's new tube from its measured wall (and 0.02 mm/yr); others linear through nominal and their surveys, except
  where the drop from nominal to the first survey is far faster than the rate between the surveys (E6: the register's
  7.6 mm is not what was built), where the surveys alone give the wall;
- oxide restarts at the 2023-05-15 chemical clean and on each new tube; E2's and E9's lives start at their new tubes.
"""
import os
import sys
import numpy as np
import pandas as pd

E = ["E%d" % i for i in range(1, 11)]
PAD, DT0, Q0, HI0, KOX, KM, R = 3.0, 62.0, 70.0, 6000.0, 0.6, 33.0, 8.314
AOX = {"T22": 4.4e12, "T91": 3.0e11}
QOX = 200e3
UPGRADE, MIGRATION = pd.Timestamp("2019-07-01"), pd.Timestamp("2024-03-12")
CLEAN, MOD, IK14 = pd.Timestamp("2023-05-15"), pd.Timestamp("2022-09-12"), pd.Timestamp("2021-04-01")
START, END = pd.Timestamp("2015-01-01"), pd.Timestamp("2026-10-31")
NEW = {"E2": pd.Timestamp("2021-06-20"), "E9": pd.Timestamp("2023-11-08")}


def inspection(data):
    res = pd.read_csv(os.path.join(data, "outage_inspection_2026.csv"))
    out = {}
    for r in res.itertuples():
        test = "oxide-ut" if r.unit == "um" else "wall-ut"
        out[(r.element, test)] = float(r.value)
    return out


def lmp_lines(std):
    out = {}
    for line in open(std):
        c = [x.strip() for x in line.split("|")]
        if len(c) > 4 and c[1] in ("T22", "T91") and c[2].replace(".", "").isdigit() and c[3].replace(".", "").isdigit():
            p40, p100 = float(c[2]), float(c[3])
            b = (np.log10(100) - np.log10(40)) / ((p40 - p100) / 1000.0)
            out[c[1]] = (np.log10(40) + b * p40 / 1000.0, b)
    return out


def load(data):
    h = pd.read_csv(os.path.join(data, "historian_daily.csv"), parse_dates=["date"])
    tc = [c for c in h.columns if c.startswith("TMT_") or c.startswith("hdr")]
    m = h.date < UPGRADE
    h.loc[m, tc] = (h.loc[m, tc] - 32) * 5 / 9
    m = h.date >= MIGRATION
    h.loc[m, ["TMT_E7", "TMT_E8"]] = h.loc[m, ["TMT_E8", "TMT_E7"]].values
    h = h[h.load_MW > 0].reset_index(drop=True)
    s = pd.read_csv(os.path.join(data, "historian_2018_monthly.csv"))
    rows = []
    hA, hB = h.hdrA_in.mean(), h.hdrB_in.mean()
    for r in s.itertuples():
        for k in range(int(round(r.hours_on_line / 24))):
            row = dict(date=pd.Timestamp(r.month + "-01") + pd.Timedelta(days=k), load_MW=r.mean_load_MW,
                       ms_press_bar=h.ms_press_bar.mean(), hdrA_in=hA, hdrB_in=hB)
            for e in E:
                row["TMT_" + e] = (getattr(r, "mean_TMT_" + e) - 32) * 5 / 9
            rows.append(row)
    h = pd.concat([h, pd.DataFrame(rows)]).sort_values("date").reset_index(drop=True)
    reg = pd.read_csv(os.path.join(data, "element_register.csv")).set_index("element")
    ut = pd.read_csv(os.path.join(data, "ut_wall_surveys.csv"), parse_dates=["survey"])
    return h, reg, ut


def pickups(h, reg):
    p = pd.DataFrame({"date": h.date})
    for e in E:
        hdr = "hdr%s_in" % reg.loc[e, "inlet_header"]
        p[e] = h["TMT_" + e] - PAD - h[hdr]
    return p


def ratio_fill(p, e, ref, t0, years=1.0):
    m = (p.date < t0) & (p.date >= t0 - pd.Timedelta(days=int(365 * years)))
    r = (p.loc[m, e] / p.loc[m, ref]).median()
    out = p[e].copy()
    out[p.date >= t0] = r * p.loc[p.date >= t0, ref]
    return out


def walls(e, dates, reg, ut, meas):
    nom = float(reg.loc[e, "nominal_wall_mm"])
    u = ut[ut.element == e].sort_values("survey")
    yrs = lambda a, b: (a - b).days / 365.25
    if e == "E9":
        h0 = meas[("E9", "wall-ut")] + 0.02 * yrs(END, NEW["E9"])
        return h0 - 0.02 * np.maximum((dates - NEW["E9"]).days.values / 365.25, 0)
    if e == "E1":
        t19, t23 = u.survey.iloc[0], u.survey.iloc[1]
        h19, h23 = u.min_wall_mm.iloc[0], u.min_wall_mm.iloc[1]
        base = (nom - h19) / yrs(t19, START)
        er = (h19 - base * yrs(t23, t19) - h23) / yrs(t23, IK14)
        return nom - base * (dates - START).days.values / 365.25 - er * np.maximum((dates - IK14).days.values / 365.25, 0)
    st = NEW.get(e, START)
    u = u[u.survey >= st]
    ts = np.array([(t - st).days / 365.25 for t in u.survey])
    hs = u.min_wall_mm.values
    if len(ts) >= 2:
        r_surv = (hs[0] - hs[-1]) / (ts[-1] - ts[0])
        r_nom = (nom - hs[0]) / ts[0]
        if r_nom > 3 * max(r_surv, 0.02) + 0.05:
            # the register's wall is not what was built: the surveys alone give the wall and its rate (E6)
            c = np.polyfit(ts, hs, 1)
            return c[1] + c[0] * np.maximum((dates - st).days.values / 365.25, 0)
    x = np.r_[0.0, ts]
    y = np.r_[nom, hs]
    rate = max(-np.polyfit(x, y, 1)[0], 0.0) if len(x) > 1 else 0.02
    return nom - rate * np.maximum((dates - st).days.values / 365.25, 0)


def run(e, h, pick, reg, ut, meas, lines):
    g = reg.loc[e, "grade"].split()[-1]
    dates = pd.DatetimeIndex(h.date)
    L = h.load_MW.values / 600.0
    P = h.ms_press_bar.values / 10.0
    tin = h["hdr%s_in" % reg.loc[e, "inlet_header"]].values
    pv = pick.values
    hw = walls(e, dates, reg, ut, meas)
    a, b = lines[g]
    do = float(reg.loc[e, "od_mm"])
    x, D = 0.0, 0.0
    t0 = NEW.get(e)
    cleaned = False
    for i in range(len(dates)):
        d = dates[i]
        if t0 is not None and d < t0:
            continue
        if d >= CLEAN and not cleaned:
            x, cleaned = 0.0, True
        tout = tin[i] + pv[i]
        q = Q0 * 1e3 * pv[i] / DT0 * L[i]
        hi = HI0 * L[i] ** 0.8
        r = do / (do - 2 * hw[i])
        tox = tout + q * r * (1 / hi + x * 1e-6 / (2 * KOX)) + 273.15
        x = np.sqrt(x * x + AOX[g] * np.exp(-QOX / (R * tox)) * 24)
        tm = tout + q * r * (1 / hi + x * 1e-6 / KOX) + q * hw[i] * 1e-3 / (2 * KM)
        sig = P[i] * (do - hw[i]) / (2 * hw[i])
        tr = 10 ** (((a - np.log10(sig)) / b * 1000) / (tm + 273.15) - 20)
        D += 24 / tr
    return D, x


def main(data, out):
    meas = inspection(data)
    lines = lmp_lines(os.path.join(data, "docs", "creep_life_standard.md"))
    h, reg, ut = load(data)
    p = pickups(h, reg)
    p["E2"] = ratio_fill(p, "E2", "E1", NEW["E2"])          # refitted pad reads high: ratio jump at replacement
    p["E7"] = ratio_fill(p, "E7", "E8", pd.Timestamp("2020-02-10"))   # renewed pad reads high: same jump
    p["E5"] = ratio_fill(p, "E5", "E2", pd.Timestamp("2022-10-01"))
    p["E4"] = ratio_fill(p, "E4", "E2", pd.Timestamp("2025-08-04"))
    p["E6"] = ratio_fill(p, "E6", "E2", pd.Timestamp("2025-01-20"))
    p["E9"] = ratio_fill(p, "E9", "E7", NEW["E9"])
    base3 = ratio_fill(p, "E3", "E2", pd.Timestamp("2022-03-01"))
    lo, hi = 0.8, 2.0
    for _ in range(40):
        k = 0.5 * (lo + hi)
        x = run("E3", h, base3.where(p.date < MOD, base3 * k), reg, ut, meas, lines)[1]
        lo, hi = (k, hi) if x < meas[("E3", "oxide-ut")] else (lo, k)
    p["E3"] = base3.where(p.date < MOD, base3 * 0.5 * (lo + hi))
    print("E3 pickup factor after the burner modification: %.3f" % (0.5 * (lo + hi)))
    res = {e: round(float(run(e, h, p[e], reg, ut, meas, lines)[0]), 5) for e in E}
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    pd.DataFrame({"element": E, "life_fraction": [res[e] for e in E]}).to_csv(out, index=False)
    print(res)


if __name__ == "__main__":
    main(*sys.argv[1:3])
