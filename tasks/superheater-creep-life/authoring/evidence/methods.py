"""Routes for the evidence studies: the reference pipeline of solution/solve.py with one step changed at a time,
run on the shipped records with the inspection results the service would return (its own seeds).

    damage(plan=(("E3", "oxide-ut"), ("E9", "wall-ut")), **options) -> {element: life fraction}
"""
import os
import sys
import numpy as np
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
sys.path.insert(0, os.path.join(ROOT, "solution"))
sys.path.insert(0, os.path.join(ROOT, "authoring", "provenance"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import solve as S
import tubes as T
import superheater as TRUTH

DATA = os.path.join(ROOT, "environment", "data")
TESTS = ("oxide-ut", "wall-ut")
LINES = S.lmp_lines(os.path.join(DATA, "docs", "creep_life_standard.md"))
_cache = {}


def result(e, test):
    """What the inspection service reports for (e, test) (fieldwork.py seeds)."""
    r = T.measure(e, test, np.random.default_rng(7000 + 31 * T.ELEMENTS.index(e) + TESTS.index(test)))
    return r["oxide_um"] if test == "oxide-ut" else r["min_wall_mm"]


def records(o):
    key = (o.get("no_unit_fix"), o.get("no_unswap"), o.get("hdr_2018"))
    if key not in _cache:
        h = pd.read_csv(os.path.join(DATA, "historian_daily.csv"), parse_dates=["date"])
        tc = [c for c in h.columns if c.startswith("TMT_") or c.startswith("hdr")]
        if not o.get("no_unit_fix"):
            m = h.date < S.UPGRADE
            h.loc[m, tc] = (h.loc[m, tc] - 32) * 5 / 9
        if not o.get("no_unswap"):
            m = h.date >= S.MIGRATION
            h.loc[m, ["TMT_E7", "TMT_E8"]] = h.loc[m, ["TMT_E8", "TMT_E7"]].values
        h = h[h.load_MW > 0].reset_index(drop=True)
        s = pd.read_csv(os.path.join(DATA, "historian_2018_monthly.csv"))
        rows = []
        y17 = h[h.date.dt.year == 2017]
        hA, hB = (y17.hdrA_in.mean(), y17.hdrB_in.mean()) if o.get("hdr_2018") == "2017" else (h.hdrA_in.mean(), h.hdrB_in.mean())
        for r in s.itertuples():
            for k in range(int(round(r.hours_on_line / 24))):
                row = dict(date=pd.Timestamp(r.month + "-01") + pd.Timedelta(days=k), load_MW=r.mean_load_MW,
                           ms_press_bar=h.ms_press_bar.mean(), hdrA_in=hA, hdrB_in=hB)
                for e in S.E:
                    row["TMT_" + e] = (getattr(r, "mean_TMT_" + e) - 32) * 5 / 9 if not o.get("no_unit_fix") else getattr(r, "mean_TMT_" + e)
                rows.append(row)
        if not o.get("skip_2018"):
            h = pd.concat([h, pd.DataFrame(rows)])
        h = h.sort_values("date").reset_index(drop=True)
        reg = pd.read_csv(os.path.join(DATA, "element_register.csv")).set_index("element")
        ut = pd.read_csv(os.path.join(DATA, "ut_wall_surveys.csv"), parse_dates=["survey"])
        _cache[key] = (h, reg, ut)
    return _cache[key]


def walls_opt(o):
    base = S.walls

    def w(e, dates, reg, ut, meas):
        nom = float(reg.loc[e, "nominal_wall_mm"])
        if e == "E9" and ("E9", "wall-ut") not in meas:
            return nom - 0.02 * np.maximum((dates - S.NEW["E9"]).days.values / 365.25, 0)
        if e == "E1" and o.get("e1_linear"):
            u = ut[ut.element == e]
            x = np.r_[0.0, [(t - S.START).days / 365.25 for t in u.survey]]
            rate = -np.polyfit(x, np.r_[nom, u.min_wall_mm.values], 1)[0]
            return nom - rate * (dates - S.START).days.values / 365.25
        if o.get("nominal_walls"):
            return np.full(len(dates), nom)
        if e == "E6" and o.get("e6_nominal"):
            return np.full(len(dates), nom)
        return base(e, dates, reg, ut, meas)
    return w


def damage(plan=(("E3", "oxide-ut"), ("E9", "wall-ut")), **o):
    meas = {(e, t): result(e, t) for e, t in plan}
    h, reg, ut = records(o)
    p = S.pickups(h, reg)
    win = o.get("window", 1.0)
    rf = lambda e, ref, t0: S.ratio_fill(p, e, ref, t0, years=win)
    sisA = o.get("sister_A", "E2")
    if not o.get("no_e2_fix"):
        p["E2"] = rf("E2", "E1", S.NEW["E2"])
    if not o.get("no_e7_fix"):
        p["E7"] = rf("E7", "E8", pd.Timestamp("2020-02-10"))
    if not o.get("no_drift_fix"):
        p["E5"] = rf("E5", sisA if sisA != "E5" else "E1", pd.Timestamp("2022-10-01"))
    p["E4"] = rf("E4", sisA, pd.Timestamp("2025-08-04"))
    p["E6"] = rf("E6", sisA, pd.Timestamp("2025-01-20"))
    p["E9"] = rf("E9", o.get("sister_B", "E7"), S.NEW["E9"])
    base3 = rf("E3", sisA, pd.Timestamp("2022-03-01"))
    S.walls_saved = S.walls
    S.walls = walls_opt(o)
    try:
        if ("E3", "oxide-ut") in meas and o.get("e3") is None:
            lo, hi = 0.8, 2.0
            for _ in range(40):
                k = 0.5 * (lo + hi)
                x = S.run("E3", h, base3.where(p.date < S.MOD, base3 * k), reg, ut, meas, LINES)[1]
                lo, hi = (k, hi) if x < meas[("E3", "oxide-ut")] else (lo, k)
            p["E3"] = base3.where(p.date < S.MOD, base3 * 0.5 * (lo + hi))
        elif o.get("e3") == "premod":
            p["E3"] = base3
        else:      # best fallback without a measurement: E4's rise at the modification carried over to E3
            m4b = (p.date < S.MOD) & (p.date >= S.MOD - pd.Timedelta(days=365))
            m4a = (p.date >= S.MOD) & (p.date < S.MOD + pd.Timedelta(days=365))
            k = p.loc[m4a, "E4"].median() / p.loc[m4b, "E4"].median()
            p["E3"] = base3.where(p.date < S.MOD, base3 * k)
        old_clean = S.CLEAN
        if o.get("no_clean"):
            S.CLEAN = pd.Timestamp("2100-01-01")
        out = {e: float(S.run(e, h, p[e], reg, ut, meas, LINES)[0]) for e in S.E}
        S.CLEAN = old_clean
    finally:
        S.walls = S.walls_saved
    return out


def misses(d):
    return {e: d[e] / TRUTH.DAMAGE[e] - 1 for e in S.E}
