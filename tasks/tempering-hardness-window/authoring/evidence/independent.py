"""A second solution, written separately from solution/solve.py, with other tests, other fits and another rule.

    python3 authoring/evidence/independent.py      (writes independent.txt beside this file)

Tests (11 tempers): heat 52-1250 at both its batches' conditions (B07, B11) and 52-1312 at B08 and 52-1377 at B13,
all double tempered as production does; 41-7864 at the pinions' condition (B09), 43-2288 at B12 and 32-0458 at B10,
once. The two other heats of ordinary composition (41-7731, 43-2210) are taken from the supplier curves.
Model: the supplier curve as a monotone-piecewise cubic (PCHIP) in the Hollomon-Jaffe parameter P = T_K (20 + log10 t)
itself; a heat's test sets its offset in HRC at the batch the test was made for (and the heat's other batch takes the
nearest test); the section effect is a linear loss of 0.5 HRC per HRC of as-quenched shortfall from the supplier's
25 mm half-radius (the reference scales the excess over 18 HRC instead); each setpoint is solved for the middle of the
range (the reference takes the middle of the predicted window). Everything is read from the documents; the laboratory is the emulator in common.py, which gives
the real laboratory's readings.
"""
import csv
import math
import os
import re
import sys

import numpy as np
from scipy.interpolate import PchipInterpolator
from scipy.optimize import brentq

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as C  # noqa: E402

K_SECTION = 0.5
PLAN = [("B07", True), ("B11", True), ("B08", True), ("B13", True), ("B09", False), ("B12", False), ("B10", False)]


def rows(name):
    with open(os.path.join(C.DATA, name), newline="") as f:
        return list(csv.DictReader(f))


def setup():
    batches = {r["batch"]: dict(r) for r in rows("batches.csv")}
    for r in rows("production_log.csv"):
        m = re.search(r"heat (\S+) used up; .* from heat (\d{2}-\d{4})", r["entry"])
        if m and r["batch"] in batches and batches[r["batch"]]["heat"] == m.group(1):
            batches[r["batch"]]["heat"] = m.group(2)
    certs = {r["heat"]: r for r in rows("mill_certificates.csv")}
    proc = open(os.path.join(C.DATA, "docs", "procedure.md")).read()
    table = np.array([[float(a), float(b), float(c)] for a, b, c in re.findall(r"\| (\d+) \| ([\d.]+) \| ([\d.]+) \|", proc)])
    curves = {}
    for r in rows("supplier_tempering_curves.csv"):
        curves.setdefault(r["grade"], []).append((float(r["tempering_temperature_C"]), float(r["hardness_HRC"])))
    tmin = {"G41": 400, "G43": 400, "G32": 500, "G52": 540}
    for g, t in (("G41", r"(\d+) C for G41"), ("G32", r"(\d+) C for G32"), ("G52", r"(\d+) C for G52")):
        tmin[g] = int(re.search(t, proc).group(1))
    double = {"G52"} if "G52 is double tempered" in proc else set()
    return batches, certs, table, curves, tmin, double


BATCHES, CERTS, TABLE, CURVES, TMIN, DOUBLE = setup()


def P(T, hours):
    return (T + 273.15) * (20.0 + math.log10(hours)) / 1000.0


SUP = {}
for g, pts in CURVES.items():
    pts = sorted(pts)
    SUP[g] = PchipInterpolator([P(t, 2.0) for t, h in pts], [h for t, h in pts], extrapolate=True)


def aq(heat, D, loc):
    J = np.interp(D, TABLE[:, 0], TABLE[:, 1 if loc == "surface" else 2])
    js = [float(k.split("_at_")[1][:-2]) for k in CERTS[heat] if k.startswith("jominy_HRC_at_")]
    return float(np.interp(J, js, [float(CERTS[heat]["jominy_HRC_at_%gmm" % j]) for j in js]))


def hours(b):
    D = float(BATCHES[b]["ruling_section_diameter_mm"])
    g = CERTS[BATCHES[b]["heat"]]["grade"]
    return max(2.0, D / 25.0) * (2 if g in DOUBLE else 1)


def model(heat, Pv, D, loc, offset):
    g = CERTS[heat]["grade"]
    return float(SUP[g](Pv)) - K_SECTION * (aq(heat, 25.0, "half-radius") - aq(heat, D, loc)) + offset


def setpoint(b, shift):
    r = BATCHES[b]
    heat, D, loc = r["heat"], float(r["ruling_section_diameter_mm"]), r["hardness_location"]
    mid = 0.5 * (float(r["hardness_min_HRC"]) + float(r["hardness_max_HRC"]))
    g = CERTS[heat]["grade"]
    f = lambda T: model(heat, P(T, hours(b)), D, loc, shift) - mid  # noqa: E731
    lo = TMIN[g]
    if f(lo) < 0:
        return lo
    return int(round(brentq(f, lo, 700.0)))


def main(seed=C.SEED):
    lab = C.Lab(seed)
    shift, bshift = {}, {}
    out = []
    for b, dbl in PLAN:
        r = BATCHES[b]
        heat, D, loc = r["heat"], float(r["ruling_section_diameter_mm"]), r["hardness_location"]
        Tp = setpoint(b, bshift.get(b, shift.get(heat, 0.0)))
        Pp = P(Tp, hours(b))
        Tl = int(round(Pp * 1000.0 / (20.0 + math.log10(4.0 if dbl else 2.0)) - 273.15))
        h = lab(heat, Tl, D, loc, dbl)
        Pl = P(Tl, 4.0 if dbl else 2.0)
        s = h - model(heat, Pl, D, loc, 0.0)
        shift[heat] = bshift[b] = s
        out.append("test %s %d C %d mm %s%s -> %.1f HRC: offset %+.2f HRC" % (heat, Tl, D, loc, " double" if dbl else "", h, s))
    temps = {b: setpoint(b, bshift.get(b, shift.get(BATCHES[b]["heat"], 0.0))) for b in BATCHES}
    res, n = C.grade(temps)
    out.append("tempers used %d of %d" % (lab.used, lab.budget))
    for b, T in temps.items():
        ok, hh = res[b]
        out.append("%s %s %d C -> true %.2f HRC, margin %+.2f %s" % (b, BATCHES[b]["heat"], T, hh, C.margin(b, T), "ok" if ok else "BAD"))
    out.append("independent solution: %d of 13 batches right; smallest true margin %+.2f HRC" % (
        n, min(C.margin(b, T) for b, T in temps.items())))
    return temps, n, "\n".join(out)


if __name__ == "__main__":
    temps, n, txt = main()
    print(txt)
    open(os.path.join(HERE, "independent.txt"), "w").write(txt + "\n")
