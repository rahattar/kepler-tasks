"""A second, independently written implementation of the assessment (shares no code with solution/solve.py or
methods.py), used as the correct-side comparator for the 25 % bound. Writes independent.txt.

Different choices throughout: faulty pads are corrected additively (an offset or a fitted linear drift against a
neighbour, estimated from the data) instead of by ratios; dead pads are filled from a neighbour plus their median
difference over two years; the oxide is integrated as dx/dt with a midpoint step instead of x^2 updates; 2018 is one
block per month at that month's mean conditions; walls are piecewise linear through the surveys; E3's
post-modification pickup is an additive increment found by the secant method. It uses the outage inspection report's
oxide on E3 and wall on E9.
"""
import csv
import math
import os
import sys
from datetime import date, timedelta

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
DATA = os.path.join(ROOT, "environment", "data")
EL = ["E%d" % i for i in range(1, 11)]
D = lambda s: date.fromisoformat(s)
START, END = D("2015-01-01"), D("2026-10-31")
UPGRADE, MIGR, CLEAN, MOD, IK14 = D("2019-07-01"), D("2024-03-12"), D("2023-05-15"), D("2022-09-12"), D("2021-04-01")
NEW = {"E2": D("2021-06-20"), "E9": D("2023-11-08")}


def rd(name):
    with open(os.path.join(DATA, name)) as f:
        return list(csv.DictReader(f))


def fnum(x):
    return float(x) if x not in ("", None) else math.nan


def std_constants():
    txt = open(os.path.join(DATA, "docs", "creep_life_standard.md")).read()
    lmp = {}
    for line in txt.splitlines():
        c = [x.strip() for x in line.strip().strip("|").split("|")]
        if len(c) == 3 and c[0] in ("T22", "T91"):
            try:
                lmp[c[0]] = (float(c[1]), float(c[2]))
            except ValueError:
                if "e" in c[1]:
                    pass
        if len(c) == 2 and c[0] in ("T22", "T91"):
            pass
    aox = {}
    for line in txt.splitlines():
        c = [x.strip() for x in line.strip().strip("|").split("|")]
        if len(c) == 2 and c[0] in ("T22", "T91"):
            aox[c[0]] = float(c[1])
    return lmp, aox


def t_r(sig, tk, pts):
    p40, p100 = pts            # log10 sigma linear in LMP through (p40, log 40) and (p100, log 100)
    p = p40 + (math.log10(sig) - math.log10(40)) * (p100 - p40) / (math.log10(100) - math.log10(40))
    return 10 ** (p / tk - 20)


def main(meas):
    lmp, aox = std_constants()
    reg = {r["element"]: r for r in rd("element_register.csv")}
    rows = rd("historian_daily.csv")
    days, L, P, hA, hB, T = [], [], [], [], [], {e: [] for e in EL}
    for r in rows:
        d = D(r["date"])
        if float(r["load_MW"]) <= 0:
            continue
        conv = (lambda v: (v - 32) / 1.8) if d < UPGRADE else (lambda v: v)
        days.append(d); L.append(float(r["load_MW"]) / 600); P.append(float(r["ms_press_bar"]) / 10)
        hA.append(conv(float(r["hdrA_in"]))); hB.append(conv(float(r["hdrB_in"])))
        for e in EL:
            src = e
            if d >= MIGR and e in ("E7", "E8"):
                src = "E8" if e == "E7" else "E7"
            T[e].append(conv(fnum(r["TMT_" + src])))
    days = np.array(days); L = np.array(L); P = np.array(P); hA = np.array(hA); hB = np.array(hB)
    hdr = {e: (hA if reg[e]["inlet_header"] == "A" else hB) for e in EL}
    pk = {e: np.array(T[e]) - 3.0 - hdr[e] for e in EL}

    def win(t0, years):
        return (days < t0) & (days >= t0 - timedelta(days=int(365.25 * years)))

    def offset_fix(e, ref, t0):          # additive step against a neighbour at t0
        b = win(t0, 1); a = (days >= t0) & (days < t0 + timedelta(days=365))
        step = np.nanmedian(pk[e][a] - pk[ref][a]) - np.nanmedian(pk[e][b] - pk[ref][b])
        pk[e] = np.where(days >= t0, pk[e] - step, pk[e])

    def regress_fill(e, ref, t0):        # e = ref + its median difference over the two years before t0
        m = win(t0, 2) & np.isfinite(pk[e]) & np.isfinite(pk[ref])
        pk[e] = np.where(days >= t0, pk[ref] + np.median(pk[e][m] - pk[ref][m]), pk[e])

    def drift_fix(e, ref, t0):           # linear drift of e against ref from t0, fitted and removed
        diff = pk[e] - pk[ref]
        base = np.nanmedian(diff[win(t0, 1)])
        m = days >= t0
        tt = np.array([(d - t0).days for d in days[m]], float)
        k = np.polyfit(tt, diff[m] - base, 1)
        corr = np.zeros(len(days)); corr[m] = np.polyval(k, tt)
        pk[e] = pk[e] - corr

    offset_fix("E7", "E8", D("2020-02-10"))
    offset_fix("E2", "E1", NEW["E2"])
    drift_fix("E5", "E2", D("2022-10-01"))
    regress_fill("E4", "E2", D("2025-08-04"))
    regress_fill("E6", "E1", D("2025-01-20"))
    regress_fill("E9", "E7", NEW["E9"])
    regress_fill("E3", "E1", D("2022-03-01"))
    # 2018: one block per month
    blocks = []
    for r in rd("historian_2018_monthly.csv"):
        d = D(r["month"] + "-15")
        tm = {e: (float(r["mean_TMT_" + e]) - 32) / 1.8 for e in EL}
        blocks.append((d, float(r["hours_on_line"]), float(r["mean_load_MW"]) / 600, tm))
    meanA = np.mean(hA[[d.year == 2017 for d in days]]); meanB = np.mean(hB[[d.year == 2017 for d in days]])
    surveys = {}
    for r in rd("ut_wall_surveys.csv"):
        surveys.setdefault(r["element"], []).append((D(r["survey"]), float(r["min_wall_mm"])))

    def wall_fn(e):
        nom = float(reg[e]["nominal_wall_mm"])
        st = NEW.get(e, START)
        s = sorted((d, h) for d, h in surveys.get(e, []) if d >= st)
        yr = lambda d: (d - st).days / 365.25
        if e == "E9":
            h_now = meas["E9"]
            return lambda d: h_now + 0.02 * (END - d).days / 365.25
        if e == "E1":
            (d1, h1), (d2, h2) = s
            base = (nom - h1) / yr(d1)
            extra = (h1 - base * (d2 - d1).days / 365.25 - h2) / ((d2 - IK14).days / 365.25)
            return lambda d: nom - base * yr(d) - extra * max((d - IK14).days, 0) / 365.25
        if len(s) >= 2:
            (d1, h1), (d2, h2) = s[0], s[-1]
            rate_s = (h1 - h2) / ((d2 - d1).days / 365.25)
            if (nom - h1) / yr(d1) > 3 * max(rate_s, 0.02) + 0.05:      # as built thinner than the register
                return lambda d: h1 - rate_s * (d - d1).days / 365.25
            pts = [(0.0, nom)] + [(yr(d), h) for d, h in s]
            last = (pts[-2][1] - pts[-1][1]) / (pts[-1][0] - pts[-2][0])
            return lambda d: (np.interp(yr(d), [p[0] for p in pts], [p[1] for p in pts]) if yr(d) <= pts[-1][0]
                              else pts[-1][1] - last * (yr(d) - pts[-1][0]))
        pts = [(0.0, nom)] + [(yr(d), h) for d, h in s]
        rate = (nom - pts[-1][1]) / pts[-1][0] if len(pts) > 1 else 0.02
        return lambda d: nom - rate * yr(d)

    def life(e, pick_override=None):
        g = reg[e]["grade"].split()[-1]
        do = float(reg[e]["od_mm"])
        wf = wall_fn(e)
        st = NEW.get(e)
        pk_e = pk[e] if pick_override is None else pick_override
        steps = [(b[0], b[1], b[2], b[3][e] - 3.0 - (meanA if reg[e]["inlet_header"] == "A" else meanB),
                  (meanA if reg[e]["inlet_header"] == "A" else meanB), 172.0 / 10) for b in blocks]
        steps += [(days[i], 24.0, L[i], pk_e[i], hdr[e][i], P[i]) for i in range(len(days))]
        steps.sort(key=lambda s: s[0])
        x, dmg, reset = 0.0, 0.0, False
        if st is not None:
            x = 0.0
        for d, hrs, l, pu, tin, p in steps:
            if st is not None and d < st:
                continue
            if d >= CLEAN and not reset:
                x, reset = 0.0, True
            h = wf(d)
            ts = tin + pu
            q = 70e3 * pu / 62.0 * l
            hi = 6000.0 * l ** 0.8
            r = do / (do - 2 * h)

            def rate(xx):                  # dx/dt (um/h) at oxide thickness xx
                tox = ts + q * r * (1 / hi + xx * 1e-6 / 1.2) + 273.15
                kp = aox[g] * math.exp(-200e3 / (8.314 * tox))
                return kp / (2 * max(xx, 0.5))
            if x < 1.0:                    # start-up from bare metal: parabolic law in closed form at the start temperature
                tox0 = ts + q * r / hi + 273.15
                x = math.sqrt(x * x + aox[g] * math.exp(-200e3 / (8.314 * tox0)) * hrs)
            else:
                k1 = rate(x)
                x = x + hrs * rate(x + 0.5 * hrs * k1)
            tm = ts + q * r * (1 / hi + x * 1e-6 / 0.6) + q * h * 1e-3 / 66.0
            sig = p * (do - h) / (2 * h)
            dmg += hrs / t_r(sig, tm + 273.15, lmp[g])
        return dmg, x

    # E3: additive increment after the modification, so that the oxide grown since the clean matches the measurement
    base3 = pk["E3"].copy()

    def oxide3(inc):
        return life("E3", np.where(days >= MOD, base3 + inc, base3))[1] - meas["E3"]
    a, b = 0.0, 20.0
    fa, fb = oxide3(a), oxide3(b)
    for _ in range(30):
        c = b - fb * (b - a) / (fb - fa)
        a, fa, b, fb = b, fb, c, oxide3(c)
        if abs(fb) < 0.05:
            break
    pk["E3"] = np.where(days >= MOD, base3 + b, base3)
    return {e: life(e)[0] for e in EL}, b


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    sys.path.insert(0, os.path.join(ROOT, "authoring", "provenance"))
    import superheater
    rep = {r["element"]: float(r["value"]) for r in rd("outage_inspection_2026.csv")}
    m = {"E3": rep["E3"], "E9": rep["E9"]}
    res, inc = main(m)
    miss = {e: res[e] / superheater.DAMAGE[e] - 1 for e in EL}
    lines = ["inspection results used: E3 oxide %.0f um, E9 wall %.2f mm; E3 pickup increment after the modification %.1f K" % (m["E3"], m["E9"], inc)]
    lines += ["%s independent %.4f  sealed %.4f  miss %+.1f%%" % (e, res[e], superheater.DAMAGE[e], 100 * miss[e]) for e in EL]
    lines.append("largest miss %.1f%%" % (100 * max(abs(v) for v in miss.values())))
    print("\n".join(lines))
    open(os.path.join(HERE, "independent.txt"), "w").write("\n".join(lines) + "\n")
