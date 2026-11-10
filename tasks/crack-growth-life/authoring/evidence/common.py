"""Shared helpers for the evidence studies. Everything here reads the agent's documents (environment/data) and the
sealed definition (tests/sealed), and emulates the laboratory exactly as environment/rig/fcgr.py does: a budget of 5
slots, a Paris test uses one and a threshold test three, and the scatter is seeded by (seed, first slot index,
round(1000 R)). The loading follows the maintenance log as an assessor reads it: unloader 1 out of service for part of
the survey, and unloader 2's heavier grab (higher ranges, fewer cycles at the conveyor's fixed throughput). So the numbers below are what the shipped scenario gives. A crack is right when its interval is 0.40
to 0.50 of its true remaining life; the gate is 16 of 16. Intervals are set at 0.447 x the model's life (the geometric
middle of the window) unless a study says otherwise.
"""
import csv
import datetime as dt
import json
import os
import re
import sys

import numpy as np
from scipy.optimize import brentq, least_squares

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
DATA = os.path.join(ROOT, "environment", "data")
sys.path.insert(0, os.path.join(ROOT, "tests", "sealed"))
import fcgsim as F  # noqa: E402

SEED = json.load(open(os.path.join(ROOT, "tests", "sealed", "seed.json")))["seed"]
COST = {"paris": 1, "threshold": 3}
BUDGET = 5
FRACTION = 0.447
IDS = [t[0] for t in F.COMPS]
TRUTH = {t[0]: F.life_months(F.comp(t))[0] for t in F.COMPS}


def rows(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


REG = {r["component"]: r for r in rows(os.path.join(DATA, "component_register.csv"))}
CERT = {r["heat"]: r for r in rows(os.path.join(DATA, "material_certificates.csv"))}
INSP = {r["component"]: float(r["crack_depth_mm"]) for r in rows(os.path.join(DATA, "inspection_2026.csv"))}
SPEC = {}
for _r in rows(os.path.join(DATA, "strain_survey_rainflow.csv")):
    SPEC.setdefault(_r["component"], []).append((float(_r["stress_range_MPa"]), float(_r["cycles"])))
LOG = rows(os.path.join(DATA, "maintenance_log.csv"))
SITE_WELDED = {r["location"] for r in LOG if "welded on site" in r["entry"]}
GRAB, GRAB_CYCLES = {}, {}
for _r in LOG:
    _m = re.search(r"\(([\d.]+) t empty, ([\d.]+) t rated payload\) replaced by \S+ \(([\d.]+) t empty, ([\d.]+) t rated\s+payload\)",
                   _r["entry"])
    if _m:
        GRAB[_r["location"]] = (float(_m.group(3)) + float(_m.group(4))) / (float(_m.group(1)) + float(_m.group(2)))
        GRAB_CYCLES[_r["location"]] = float(_m.group(2)) / float(_m.group(4))   # fixed throughput: cycles go with 1/payload
_D = lambda s: dt.date.fromisoformat(s)  # noqa: E731
SURVEY = ([_D(r["date"]) for r in LOG if "survey started" in r["entry"]][0],
          [_D(r["date"]) for r in LOG if "survey ended" in r["entry"]][0])
SURVEY_DAYS = (SURVEY[1] - SURVEY[0]).days + 1
DOWN, _since = {}, {}
for _r in LOG:
    if "out of service" in _r["entry"]:
        _since[_r["location"]] = _D(_r["date"])
    if "back in service" in _r["entry"]:
        _a, _b = max(_since[_r["location"]], SURVEY[0]), min(_D(_r["date"]), SURVEY[1] + dt.timedelta(days=1))
        DOWN[_r["location"]] = DOWN.get(_r["location"], 0) + max(0, (_b - _a).days)
EXAMPLES = {}
for _name in sorted(os.listdir(os.path.join(DATA, "examples"))):
    _e = {r["item"]: r["value"] for r in rows(os.path.join(DATA, "examples", _name))}
    EXAMPLES[_e["component"]] = _e


# ---------------------------------------------------------------- the laboratory
def lab(campaign, seed=SEED):
    """[(kind, R[, heat]), ...] -> [(kind, R, dK, da/dN, heat), ...], as fcgr reports them (heat H1 unless given);
    refuses past the budget"""
    used, out = 0, []
    for test in campaign:
        kind, R = test[0], test[1]
        heat = test[2] if len(test) > 2 else "H1"
        if used + COST[kind] > BUDGET:
            raise RuntimeError("test allowance exhausted")
        idx = used + 1
        used += COST[kind]
        rng = np.random.default_rng([seed, idx, int(round(R * 1000)), int(heat[1])])
        dK, r = F.lab(kind, round(R, 3), rng, heat)
        out.append((kind, R, dK, r, heat))
    return out


GRADE = {h: r["grade"] for h, r in CERT.items()}   # the grade of each heat, from the material certificates


# ---------------------------------------------------------------- growth-law fits
def BS_TH(R):
    """BS 7910 recommended threshold for steels in air (the handbook), MPa sqrt(m)"""
    R = np.asarray(R, float)
    return np.where(R < 0.5, 5.38 - 6.77 * R, 2.0)


def fit(data, rform="closure", threshold="bs", heats="fit"):
    """da/dN = exp(a(R)) dK^m (1 - dKth(R)/dK)^p, fitted to all the reports together (log rates, least squares).
    rform 'closure': a(R) = ln C + m ln U(R), U = min(1, U0 + (1 - U0) R / Rc), U0 fitted and Rc, the R where closure
                     ends, searched on a grid (the reference). Where the tests leave Rc open (no closure-affected test
                     between the lowest test and the first closure-free one), the largest Rc that fits as well is
                     taken: the straight line through the measured points, as an assessor would draw it;
          'interp':  one intercept per tested R, linear in R between them, flat outside;
          'walker':  a(R) = ln C - m (1 - g) ln(1 - R), one Walker exponent g;
          'newman':  U(R) = (1 - f) / (1 - R) from Newman's closure function f(R; alpha, Smax/sigma0), both fitted.
    threshold 'bs':    dKth = max(BS 7910 line 5.38 - 6.77 R, a fitted closure-free threshold) (the reference);
              'flat':  one fitted threshold for every R;
              'paris': the fitted closure-free threshold scaled to lower R by the Paris-regime closure, dKth / U(R);
              'handbook': the handbook's BS 7910 values, not fitted (2.0 from R 0.5).
    heats 'fit': a rate factor for each tested heat relative to heat H1 (the reference); a heat that was not tested
          takes the factor of a tested heat of its grade, or 1 (law.hf; examples_for_heats can set it from a record);
          'grade': one factor per grade, all S355J2 heats taken as H1; 'none': one law for every heat, BS 7910's
          assumption for ferritic steels."""
    Ra = sorted(set(R for _, R, _, _, _ in data))
    R = np.concatenate([np.full(len(d), r) for _, r, d, _, _ in data])
    dK = np.concatenate([d for _, _, d, _, _ in data])
    v = np.concatenate([x for _, _, _, x, _ in data])
    hcol = np.concatenate([np.full(len(d), h, object) for _, _, d, _, h in data])
    tested = sorted(set(hcol))
    if heats == "none" or "H1" not in tested:
        groups = []
    elif heats == "grade":
        groups = [[h for h in tested if GRADE[h] != GRADE["H1"]]]
        groups = [g for g in groups if g]
    else:
        groups = [[h] for h in tested if h != "H1"]
    gmask = [np.isin(hcol, g).astype(float) for g in groups]
    ng = len(groups)
    if rform == "interp":
        r0, rl, ru = [-25.0] * len(Ra), [-60.0] * len(Ra), [10.0] * len(Ra)
    elif rform == "closure":
        r0, rl, ru = [-25.0, 0.6], [-60.0, 0.2], [10.0, 1.0]
    elif rform == "newman":
        r0, rl, ru = [-25.0, 2.0, 0.3], [-60.0, 1.0, 0.05], [10.0, 3.0, 0.9]
    else:
        r0, rl, ru = [-25.0, 0.5], [-60.0, -2.0], [10.0, 3.0]

    def lnA(Rv, q):
        rq, Rv = q[3:3 + len(r0)], np.asarray(Rv, float)
        if rform == "interp":
            return np.interp(Rv, Ra, rq)
        if rform == "closure":
            return rq[0] + q[0] * np.log(np.minimum(1.0, rq[1] + (1 - rq[1]) * Rv / rc[0]))
        if rform == "newman":
            al, sr = rq[1], rq[2]
            A0 = (0.825 - 0.34 * al + 0.05 * al ** 2) * np.cos(np.pi * sr / 2) ** (1 / al)
            A1 = (0.415 - 0.071 * al) * sr
            A3 = 2 * A0 + A1 - 1
            A2 = 1 - A0 - A1 - A3
            f = np.maximum(Rv, A0 + A1 * Rv + A2 * Rv ** 2 + A3 * Rv ** 3)
            return rq[0] + q[0] * np.log(np.clip((1 - f) / (1 - Rv), 1e-3, None))
        return rq[0] - q[0] * (1 - rq[1]) * np.log(1 - Rv)

    def th(Rv, q):
        Rv = np.asarray(Rv, float)
        if threshold == "bs":
            return np.maximum(5.38 - 6.77 * Rv, q[2])
        if threshold == "flat":
            return np.full_like(Rv, q[2])
        if threshold == "handbook":
            return BS_TH(Rv)
        Urel = np.minimum(1.0, np.exp((lnA(Rv, q) - lnA(np.array([0.9]), q)[0]) / q[0]))
        return q[2] / Urel

    def resid(q):
        g = sum(q[len(q) - ng + i] * gmask[i] for i in range(ng)) if ng else 0.0
        return g + lnA(R, q) + q[0] * np.log(dK) + q[1] * np.log(np.clip(1 - th(R, q) / dK, 1e-6, None)) - np.log(v)

    tmax = 0.999 * dK.min() if threshold in ("flat", "paris") else 20.0
    rc = [1.0]

    def solve():
        best = None
        for p0 in (0.3, 0.5, 1.0):
            for t0 in (1.5, 2.2):
                q0 = np.r_[3.0, p0, min(t0, 0.95 * tmax), r0, [0.0] * ng]
                lo = np.r_[1.5, 0.05, 0.3, rl, [-2.0] * ng]
                up = np.r_[6.0, 3.0, tmax, ru, [2.0] * ng]
                try:
                    sol = least_squares(resid, q0, bounds=(lo, up))
                except ValueError:
                    continue
                if best is None or sol.cost < best.cost:
                    best = sol
        return best
    if rform == "closure":
        trials = []
        for r_c in np.arange(0.15, 0.951, 0.005):
            rc[0] = r_c
            sol = solve()
            trials.append((sol.cost, r_c, sol.x))
        cmin = min(t[0] for t in trials)
        _, rc[0], q = max((t for t in trials if t[0] <= cmin * (1 + 1e-6) + 1e-12), key=lambda t: t[1])
    else:
        q = solve().x

    def law(dKx, Rx):
        dKx, Rx = np.asarray(dKx, float), np.asarray(Rx, float)
        k = th(Rx, q)
        out = np.exp(lnA(Rx, q)) * dKx ** q[0] * np.clip(1 - k / np.maximum(dKx, 1e-9), 0, None) ** q[1]
        return np.where(dKx > k, out, 0.0)
    law.q, law.m, law.p, law.rc = q, q[0], q[1], rc[0]
    hf = {"H1": 1.0}
    for i, g in enumerate(groups):
        for h in g:
            hf[h] = float(np.exp(q[len(q) - ng + i]))
    for h in GRADE:
        if h not in hf:
            mate = [hf[k] for k in hf if GRADE[k] == GRADE[h]]
            hf[h] = mate[0] if (mate and heats != "none") else 1.0
    law.hf = hf
    law.tested = set(tested)
    law.th = lambda Rv: th(Rv, q)
    law.U = lambda Rv: np.minimum(1.0, np.exp((lnA(np.asarray(Rv, float), q) - lnA(np.array([0.9]), q)[0]) / q[0]))
    return law


def handbook_law(dK, R):
    """BS 7910 simplified law (mean + 2 SD) with the BS 7910 recommended threshold, from the handbook"""
    dK = np.asarray(dK, float)
    R = np.asarray(R, float)
    return np.where(dK > BS_TH(R), 1.65e-11 * dK ** 3, 0.0)


# ---------------------------------------------------------------- the crack model an assessor builds
def Mk(aT, LT, cap=True):
    aT = np.asarray(aT, float)
    if LT <= 2.0 or not cap:
        v = np.where(aT <= 0.05 * LT ** 0.55, 0.51 * LT ** 0.27 * aT ** -0.31, 0.83 * aT ** (-0.15 * LT ** 0.46))
    else:
        v = np.where(aT <= 0.073, 0.615 * aT ** -0.31, 0.83 * aT ** -0.2)
    return np.maximum(v, 1.0)


def Y(aT):
    return 1.12 - 0.231 * aT + 10.55 * aT ** 2 - 21.72 * aT ** 3 + 30.39 * aT ** 4


def crack(cid):
    r = REG[cid]
    h = CERT[r["flange_plate_heat"]]
    return dict(id=cid, member=r["member"], where="%s, %s" % (r["member"], r["position"]),
                fab=r["member_fabrication"].lower(), T=float(r["flange_thickness_mm"]) * 1e-3,
                tatt=float(r["attachment_thickness_mm"]) * 1e-3, leg=float(r["fillet_weld_leg_mm"]) * 1e-3,
                sy=float(h["yield_strength_MPa"]), kmat=float(h["fracture_toughness_Kmat_MPa_sqrt_m"]), grade=h["grade"],
                heat=r["flange_plate_heat"],
                smin=float(r["dead_load_stress_MPa"]), a0=INSP[cid] * 1e-3,
                ds=np.array([d for d, _ in SPEC[cid]]), n=np.array([c for _, c in SPEC[cid]]))


REPAIR_MARGIN = 1.0e-3   # FA-3: a repair groove is ground 1 mm past the last MPI indication


def example(eid, face_value=False):
    """an example record as an assessor reads it: the crack depth at repair is the excavation depth less FA-3's 1 mm
    margin (face_value=True takes the excavation depth itself as the crack depth)"""
    e = EXAMPLES[eid]
    h = CERT[e["flange_plate_heat"]]
    bins = [(float(k.split("_")[2]), float(v)) for k, v in e.items() if k.startswith("survey_range")]
    n = np.array([c for _, c in bins])
    return dict(id=eid, member=e["member"], where="%s, %s" % (e["member"], e["position"]), fab=e["member_fabrication"].lower(),
                T=float(e["flange_thickness_mm"]) * 1e-3, tatt=float(e["attachment_thickness_mm"]) * 1e-3,
                leg=float(e["fillet_weld_leg_mm"]) * 1e-3, sy=float(h["yield_strength_MPa"]), kmat=1e9, grade=h["grade"],
                heat=e["flange_plate_heat"],
                smin=float(e["dead_load_stress_MPa"]), a0=float(e["crack_depth_found_mm"]) * 1e-3,
                a1=float(e["excavation_depth_mm"]) * 1e-3 - (0.0 if face_value else REPAIR_MARGIN),
                ds=np.array([b for b, _ in bins]), n=n,
                N=float(e["operating_days_found_to_repair"]) / float(e["survey_days"]) * n.sum())


DEFAULT = dict(mk="bs", L="toe", resid="bs", site_welds=True, vsr=False, grab="loader", cycles=True, stoppage=True,
               fudge=1.0, fudge_on=None)


def curve(law, c, future=True, **kw):
    """(a, da/dN) along the crack from a0 to its critical depth under the given assessment choices:
    mk 'bs' (capped at L/T 2) | 'uncapped' | 'const' (held at its a0 value) | 'none'; L 'toe' (attachment + 2 legs) |
    'att'; resid 'bs' (yield as welded, 0.2 yield after PWHT) | 'none' | a number (fraction of yield after PWHT);
    site_welds: honour the log's site welds after PWHT; vsr: credit vibratory stress relief as PWHT;
    grab 'loader' (every member of unloader 2) | 'boom' (its boom only) | 'none'; cycles: unloader 2's grab cycles
    fall with 1/payload (fixed throughput); stoppage: unloader 1's counts cover only its operating days in the survey;
    fudge: a rate factor, applied to every crack or only to the cracks in fudge_on."""
    o = dict(DEFAULT, **{k: v for k, v in kw.items() if k in DEFAULT})
    T = c["T"]
    L = c["tatt"] + 2 * c["leg"] if o["L"] == "toe" else c["tatt"]
    if o["mk"] == "const":
        m0 = float(Mk(c["a0"] / T, L / T))
        g = lambda a: m0 * Y(a / T) * np.sqrt(np.pi * a)  # noqa: E731
    elif o["mk"] == "none":
        g = lambda a: Y(a / T) * np.sqrt(np.pi * a)  # noqa: E731
    else:
        g = lambda a: Mk(a / T, L / T, cap=(o["mk"] == "bs")) * Y(a / T) * np.sqrt(np.pi * a)  # noqa: E731
    pwht = c["fab"].startswith("pwht") and not (o["site_welds"] and c["where"] in SITE_WELDED)
    if o["vsr"] and "vibratory" in c["fab"]:
        pwht = True
    sy = c["sy"]
    if o["resid"] == "nominal":     # the grade's specified minimum yield instead of the certificate's
        sy = 460.0 if "460" in c.get("grade", "") else 355.0
    frac = 0.2 if o["resid"] in ("bs", "nominal") else (0.0 if o["resid"] == "none" else float(o["resid"]))
    sres = frac * sy if pwht else (0.0 if o["resid"] == "none" else sy)
    k = 1.0
    if future and GRAB:
        loader, f = next(iter(GRAB.items()))
        if o["grab"] == "loader" and c["member"].startswith(loader):
            k = f
        elif o["grab"] == "boom" and c["member"] == loader + " boom":
            k = f
    ds, n, smin = c["ds"] * k, c["n"], c["smin"]
    Rb = np.clip((smin + sres) / (smin + sres + ds), 0.0, 0.95)
    aa = np.linspace(c["a0"], 0.5 * T, 8000)
    hit = np.nonzero((smin + ds.max()) * g(aa) >= c["kmat"])[0]
    ac = aa[hit[0]] if len(hit) else 0.5 * T
    a = np.linspace(c["a0"], ac, 2000)
    fud = o["fudge"] if (o["fudge_on"] is None or c["id"] in o["fudge_on"]) else 1.0
    fud *= getattr(law, "hf", {}).get(c.get("heat"), 1.0)
    rr = fud * (law(ds[None, :] * g(a)[:, None], Rb[None, :]) * (n / n.sum())[None, :]).sum(1)
    return a, rr


def cycles_per_month(c, **kw):
    o = dict(DEFAULT, **{k: v for k, v in kw.items() if k in DEFAULT})
    days = SURVEY_DAYS - (sum(v for k, v in DOWN.items() if c["member"].startswith(k)) if o["stoppage"] else 0)
    k = 1.0
    if o["cycles"] and o["grab"] != "none":
        k = next((v for loader, v in GRAB_CYCLES.items() if c["member"].startswith(loader)
                  and (o["grab"] == "loader" or c["member"] == loader + " boom")), 1.0)
    return k * c["n"].sum() / days * F.OPERATING_DAYS / 12.0


def life(law, cid, **kw):
    c = crack(cid)
    a, rr = curve(law, c, **kw)
    inv = np.where(rr > 0, 1 / np.maximum(rr, 1e-300), 1e30)
    return float(np.trapezoid(inv, a)) / cycles_per_month(c, **kw)


def example_factor(law, eid, face_value=False, **kw):
    """the rate factor that makes the model reproduce an example's depth at repair"""
    e = example(eid, face_value)

    def miss(f):
        a, rr = curve(law, e, future=False, **dict(kw, fudge=f, fudge_on=None))
        Nc = np.concatenate([[0], np.cumsum(np.diff(a) * 0.5 * (1 / rr[1:] + 1 / rr[:-1]))])
        return np.interp(e["N"], Nc, a) - e["a1"]
    try:
        return brentq(miss, 0.02, 80)
    except ValueError:
        return float("nan")


def examples_for_heats(law, face_value=False, **kw):
    """a copy of the law in which each heat that has an example record but was not tested in the laboratory takes the
    rate factor that makes the model reproduce that record (the reference reads heat H2's rate from E02 this way)"""
    import copy
    new = copy.copy(law)
    new.hf = dict(law.hf)
    tested = getattr(law, "tested", None) or {"H1"}
    for eid, e in EXAMPLES.items():
        h = e["flange_plate_heat"]
        if h not in tested:
            new.hf[h] = law.hf.get(h, 1.0) * example_factor(law, eid, face_value=face_value, **kw)
    return new


def grade(intervals):
    ratio = {c: intervals[c] / TRUTH[c] for c in IDS}
    ok = [c for c in IDS if F.LO <= ratio[c] <= F.HI]
    return len(ok), ok, ratio


def assess(law, fraction=FRACTION, **kw):
    lives = {c: life(law, c, **kw) for c in IDS}
    return {c: fraction * v for c, v in lives.items()}, lives


UNLOADER2 = [c for c in IDS if REG[c]["member"].startswith("unloader 2")]
UNLOADER1 = [c for c in IDS if REG[c]["member"].startswith("unloader 1")]
