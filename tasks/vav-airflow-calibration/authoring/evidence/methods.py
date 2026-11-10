"""Shared engine for the evidence studies: calibrates the floor from the shipped records and a visit plan, with
the choices a sound method could make and the shortcuts a weak one takes, and grades the result.

Visits are emulated with vav.hood_visit at the same seeds as the service (the seed depends on the visit number
and the box), so a plan run here sees exactly the readings the service would return for that plan in that order.
The sealed definition (authoring/provenance/vav.py) is used only for that and for grading (tests/grade_vav.py
logic: worst delivered-airflow error over design minimum and maximum, 10 percent).
"""
import math, os, re, sys
import numpy as np
import pandas as pd
from scipy.optimize import least_squares

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "authoring", "provenance"))
import vav

DATA = os.path.join(ROOT, "environment", "data")
FLOOR = vav.make_floor(31)
TRUTH = {b["tag"]: b for b in FLOOR}
S = pd.read_csv(os.path.join(DATA, "box_schedule.csv")).set_index("tag")
V = pd.read_csv(os.path.join(DATA, "inlet_survey.csv")).set_index("tag")
R = pd.read_csv(os.path.join(DATA, "tab_report_2024.csv")).set_index("tag")
TAGS = list(S.index)
_note = open(os.path.join(DATA, "docs", "vav_application_note.md")).read()
KF_SIZE = {int(a): float(b) for a, b in re.findall(r"^\|\s*(\d+)\s*\|\s*([\d.]+)\s*\|", _note, re.M)}
KF = {t: KF_SIZE[int(S.loc[t, "inlet_in"])] for t in TAGS}
FW24 = {t: str(S.loc[t, "controller_fw"]).startswith("2.") for t in TAGS}
LD = {t: float(V.loc[t, "straight_run_diameters"]) for t in TAGS}
FLEX_FT = {t: (float(V.loc[t, "flex_length_ft"]) if pd.notna(V.loc[t, "flex_length_ft"]) else None) for t in TAGS}
EAST = {t: S.loc[t, "wing"] == "east" for t in TAGS}
_ren = open(os.path.join(DATA, "docs", "renovation_2025.md")).read()
KINKED = re.findall(r"VAV-3-\d\d", _ren.split("Punch list")[1].split("Commissioning walk-down")[0])


def _cls(t):
    f = V.loc[t, "upstream_fitting"]
    if f.startswith("straight"):
        return "straight"
    if "elbow" in f:
        return "elbow_v" if "vertical" in f else "elbow_h"
    if t in KINKED:
        return "kinked"
    if FLEX_FT[t] is not None and FLEX_FT[t] > 5.0:
        return "sagging"
    return "flex"


CLS = {t: _cls(t) for t in TAGS}


def _zero():
    z = {}
    for t in TAGS:
        tr = pd.read_csv(os.path.join(DATA, "trends", "%s.csv" % t.lower()))
        shut = tr[tr.flow_sp_cfm == 0]
        z[t] = float(shut.vp_inwc.median()) if len(shut) >= 20 else None
    return z


ZERO = _zero()
LABS24 = [t for t in TAGS if FW24[t] and ZERO[t] is None]


def fit_visit(pts, how="wls"):
    vp = np.array([p["vp_inwc"] for p in pts], float)
    q = np.array([p["hood_total_cfm"] for p in pts], float)
    if how == "two":                                   # exact through design minimum and design maximum
        i, j = 0, len(q) - 1
        K2 = (q[j] ** 2 - q[i] ** 2) / (vp[j] - vp[i])
        return math.sqrt(K2), vp[i] - q[i] ** 2 / K2
    A = np.vstack([vp, -np.ones_like(vp)]).T
    w = 1.0 / q if how == "wls" else np.ones_like(q)
    c = np.linalg.lstsq(A * w[:, None], q ** 2 * w, rcond=None)[0]
    return math.sqrt(c[0]), c[1] / c[0]


def _decay(ld, m, sign):
    ld, m = np.asarray(ld, float), np.asarray(m, float)
    return least_squares(lambda z: 1 + sign * z[0] * np.exp(-ld / z[1]) - m, [0.2, 1.5],
                         bounds=([0, 0.2], [1.0, 6.0])).x


def calibrate(plan, fit="wls", transfer="decay", z24="half", az_check=True, night_offsets=True, use_stale=False,
              kinks="punch", sag="own", vertical="own", lab_zero="fleet", one_point=False):
    """Returns {tag: (K, offset)}.

    Sound choices: fit wls | ols | two; transfer decay (amplitude at the elbows' decay length) | mean (class mean of
    measured members) | free (two-parameter fit per class where it has enough members); z24 (a 2.4 box's zero at
    the 2024 report) half | zero | full of today's.
    Shortcuts and fallbacks: az_check False (offsets only on firmware 2.4); night_offsets False; use_stale True
    (the 2024 report for east-wing boxes); kinks 'survey' (punch-list boxes treated as ordinary flex at their
    surveyed L/D); sag 'flex' | 'kinked' (long connectors as ordinary flex, or at the kinked factor) when not
    visited; vertical 'factory' | 'horizontal' when no drop is visited (or 'pool' to force one elbow model);
    lab_zero 'fleet' | 'labs' | 'zero' for an unvisited 2.4 lab; one_point (K from the maximum reading only).
    """
    cls = dict(CLS)
    if kinks == "survey":
        for t in KINKED:
            cls[t] = "flex" if not (FLEX_FT[t] and FLEX_FT[t] > 5.0) else "sagging"
    if vertical == "pool":
        cls = {t: ("elbow_h" if c == "elbow_v" else c) for t, c in cls.items()}
    off = {}
    for t in TAGS:
        z = ZERO[t]
        use = night_offsets and z is not None and (FW24[t] or (az_check and abs(z) > 0.005))
        off[t] = z if use else 0.0
    meas = {}
    for k, t in enumerate(plan, 1):
        pts = vav.hood_visit(TRUTH[t], k)
        if one_point:
            meas[t] = (pts[-1]["hood_total_cfm"] / math.sqrt(pts[-1]["vp_inwc"]), 0.0)
        else:
            meas[t] = fit_visit(pts, fit)
    m = {t: meas[t][0] / KF[t] for t in meas}
    for t in R.index:
        if t in m or (EAST[t] and not use_stale):
            continue
        frac = dict(zero=0.0, half=0.5, full=1.0)[z24]
        zz = frac * off[t] if FW24[t] else 0.0
        vp = (R.loc[t, "bas_cfm"] / KF[t]) ** 2 - zz
        m[t] = R.loc[t, "hood_cfm"] / (KF[t] * math.sqrt(vp))
    eh = [t for t in m if cls[t] == "elbow_h"]
    a_h, lam_h = _decay([LD[t] for t in eh], [m[t] for t in eh], -1)

    def amp(ts):
        x = np.array([math.exp(-LD[t] / lam_h) for t in ts]); y = np.array([m[t] - 1 for t in ts])
        return float(x @ y / (x @ x))

    model = {"straight": lambda t: 1.0, "elbow_h": lambda t: 1 - a_h * math.exp(-LD[t] / lam_h)}
    for c in ("flex", "elbow_v"):
        ts = [t for t in m if cls[t] == c]
        if not ts:
            continue
        if transfer == "mean":
            model[c] = (lambda v: (lambda t: v))(float(np.mean([m[t] for t in ts])))
        elif transfer == "free" and len(ts) >= 3:
            a, lam = _decay([LD[t] for t in ts], [m[t] for t in ts], +1)
            model[c] = (lambda a, lam: (lambda t: 1 + a * math.exp(-LD[t] / lam)))(a, lam)
        else:
            model[c] = (lambda a: (lambda t: 1 + a * math.exp(-LD[t] / lam_h)))(amp(ts))
    for c in ("kinked", "sagging"):
        ts = [t for t in m if cls[t] == c]
        if ts:
            model[c] = (lambda v: (lambda t: v))(float(np.mean([m[t] for t in ts])))
    # fallbacks for classes nobody measured
    if "elbow_v" not in model:
        model["elbow_v"] = (lambda t: 1.0) if vertical in ("own", "factory") else model["elbow_h"]
    if "sagging" not in model:
        model["sagging"] = model.get("kinked", model["flex"]) if sag == "kinked" else model["flex"]
    if "kinked" not in model:
        model["kinked"] = model["flex"]
    zeros24 = [off[t] for t in TAGS if FW24[t] and ZERO[t] is not None] + [meas[t][1] for t in meas if t in LABS24]
    labs_seen = [meas[t][1] for t in meas if t in LABS24]
    cal = {}
    for t in TAGS:
        if t in meas:
            cal[t] = meas[t]
            continue
        o = off[t]
        if t in LABS24:
            o = dict(fleet=float(np.median(zeros24)), zero=0.0,
                     labs=float(np.mean(labs_seen)) if labs_seen else float(np.median(zeros24)))[lab_zero]
        cal[t] = (KF[t] * (m[t] if t in m else model[cls[t]](t)), o)
    return cal


def grade(cal):
    """(worst error, worst box, failing boxes) on the sealed definition, as tests/grade_vav.py computes it."""
    errs = {}
    for b in FLOOR:
        K, o = cal[b["tag"]]
        errs[b["tag"]] = max(abs(vav.true_flow(b, K, o, q) / q - 1) for q in (b["qmin"], b["qmax"]))
    worst = max(errs, key=errs.get)
    return errs[worst], worst, sorted(t for t, e in errs.items() if e > vav.TOL)


REFERENCE_PLAN = ["VAV-3-36", "VAV-3-37", "VAV-3-38", "VAV-3-28", "VAV-3-31"]
