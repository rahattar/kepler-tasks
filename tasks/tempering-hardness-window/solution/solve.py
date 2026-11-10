"""Reference solution: tempering setpoints for the thirteen batches.

    python3 solve.py [DATA] [OUT]        (defaults /app/data, /app/output/tempering.json)

Uses only the documents in DATA and the laboratory's `temper` command.

Model of a batch's hardness after tempering at setpoint T, for a heat of grade g:
  - time: the Hollomon-Jaffe parameter (T + 273.15)(20 + log10 t), t the total hours at temperature (soak 1 h per
    25 mm of ruling section, at least 2 h, times 2 for the double-tempered grade G52), referred to one 2 h temper;
  - shape: the supplier's typical curve for g at that equivalent temperature (25 mm round, half-radius);
  - section: the excess over 18 HRC scaled by the heat's as-quenched hardness at the location (its Jominy curve at the
    procedure's equivalent distance) over its as-quenched hardness at the supplier's 25 mm half-radius;
  - heat: an offset in HRC from a laboratory test of the heat, made as the batch is made: at the batch's diameter and
    location, at the laboratory temperature with the same tempering parameter as the setpoint first predicted, and
    for G52 double tempered (a single temper of G52 does not stand for a double one).
The plan tests every heat once, at one of its batches' conditions, and spends 6 of the 11 tempers on the G52 heats
(double, 2 tempers each; 52-1250 at the punch holders' condition, B11): heat 41-7864 at the pinions' condition (B09;
the production log moved them to this heat), 43-2288 (B12), 32-0458 (B05), 43-2210 (B03) and 41-7731 (B01).
"""
import csv
import json
import math
import os
import re
import subprocess
import sys

import numpy as np

FLOOR = 18.0
C_HJ = 20.0
PLAN = [("52-1250", "B11", True), ("52-1312", "B06", True), ("52-1377", "B13", True), ("41-7864", "B09", False),
        ("43-2288", "B12", False), ("32-0458", "B05", False), ("43-2210", "B03", False), ("41-7731", "B01", False)]


def run_temper(heat, T, D, loc, double):
    """one laboratory test through the `temper` command; returns the reported hardness"""
    cmd = ["temper", heat, "%d" % T, "%d" % int(D), loc] + (["double"] if double else [])
    out = subprocess.run(cmd, capture_output=True, text=True, cwd="/app" if os.path.isdir("/app") else None).stdout
    m = re.search(r"hardness_HRC,([0-9.]+)", out)
    if not m:
        raise RuntimeError("laboratory refused: %s" % out.strip())
    return float(m.group(1))


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


class Records:
    def __init__(self, data):
        self.batches = {r["batch"]: r for r in read_csv(os.path.join(data, "batches.csv"))}
        for r in read_csv(os.path.join(data, "production_log.csv")):
            m = re.search(r"cut from heat (\d{2}-\d{4})", r["entry"])
            if r["batch"] in self.batches and m:
                self.batches[r["batch"]]["heat"] = m.group(1)
        self.certs = {r["heat"]: r for r in read_csv(os.path.join(data, "mill_certificates.csv"))}
        self.jdist = [float(k.split("_at_")[1][:-2]) for k in read_csv(os.path.join(data, "mill_certificates.csv"))[0]
                      if k.startswith("jominy_HRC_at_")]
        self.sup = {}
        for r in read_csv(os.path.join(data, "supplier_tempering_curves.csv")):
            self.sup.setdefault(r["grade"], []).append((float(r["tempering_temperature_C"]), float(r["hardness_HRC"])))
        proc = open(os.path.join(data, "docs", "procedure.md")).read()
        self.jtab = [tuple(float(x) for x in m) for m in re.findall(r"^\| (\d+) \| ([0-9.]+) \| ([0-9.]+) \|$", proc, re.M)]
        self.tmin = {g: float(t) for t, g in re.findall(r"(\d{3}) C for (G\d\d)", proc)}
        for t, g1, g2 in re.findall(r"(\d{3}) C for (G\d\d) and (G\d\d)", proc):
            self.tmin[g1] = self.tmin[g2] = float(t)
        self.double = set(re.findall(r"Grade (G\d\d) is double tempered", proc))

    def grade(self, heat):
        return self.certs[heat]["grade"]

    def jeq(self, D, loc):
        Ds = [r[0] for r in self.jtab]
        col = 1 if loc == "surface" else 2
        return float(np.interp(D, Ds, [r[col] for r in self.jtab]))

    def as_quenched(self, heat, D, loc):
        hs = [float(self.certs[heat]["jominy_HRC_at_%gmm" % J]) for J in self.jdist]
        return float(np.interp(self.jeq(D, loc), self.jdist, hs))

    def soak(self, D):
        return max(2.0, D / 25.0)

    def ntemper(self, heat):
        return 2 if self.grade(heat) in self.double else 1


class Model:
    def __init__(self, rec, c_hj=C_HJ, interp="linear", rule="window"):
        self.rec, self.c, self.interp, self.rule = rec, c_hj, interp, rule
        self.offset, self.boff = {}, {}

    def teq(self, T, hours):
        return (T + 273.15) * (self.c + math.log10(hours)) / (self.c + math.log10(2.0)) - 273.15

    def sup(self, grade, Teq):
        pts = sorted(self.rec.sup[grade])
        x, y = [p[0] for p in pts], [p[1] for p in pts]
        if self.interp == "pchip":
            from scipy.interpolate import PchipInterpolator
            return float(PchipInterpolator(x, y, extrapolate=True)(Teq))
        return float(np.interp(Teq, x, y))

    def raw(self, heat, T, D, loc, hours_total):
        g = self.rec.grade(heat)
        base = self.sup(g, self.teq(T, hours_total))
        aq, aq0 = self.rec.as_quenched(heat, D, loc), self.rec.as_quenched(heat, 25.0, "half-radius")
        return FLOOR + (base - FLOOR) * (aq - FLOOR) / (aq0 - FLOOR)

    def predict(self, b, T):
        r = self.rec.batches[b]
        heat, D, loc = r["heat"], float(r["ruling_section_diameter_mm"]), r["hardness_location"]
        off = self.boff.get(b, self.offset.get(heat, 0.0))
        return self.raw(heat, T, D, loc, self.rec.soak(D) * self.rec.ntemper(heat)) + off

    def choose(self, b):
        """the middle of the longest run of whole-degree setpoints predicted inside the range"""
        r = self.rec.batches[b]
        lo, hi = float(r["hardness_min_HRC"]), float(r["hardness_max_HRC"])
        Ts = list(range(int(self.rec.tmin[self.rec.grade(r["heat"])]), 701))
        inside = [lo <= self.predict(b, T) <= hi for T in Ts]
        mid = 0.5 * (lo + hi)
        if self.rule == "mid":
            return min(Ts, key=lambda T: abs(self.predict(b, T) - mid))
        best, cur = [], []
        for T, ok in zip(Ts, inside):
            cur = cur + [T] if ok else []
            if len(cur) > len(best):
                best = cur
        if best:
            return best[len(best) // 2]
        return min(Ts, key=lambda T: abs(self.predict(b, T) - mid))

    def lab_temperature(self, b, Tp, double):
        """laboratory temperature (2 h, once or twice) with the same tempering parameter as setpoint Tp for batch b"""
        r = self.rec.batches[b]
        heat, D = r["heat"], float(r["ruling_section_diameter_mm"])
        target = self.teq(Tp, self.rec.soak(D) * self.rec.ntemper(heat))
        hours = 4.0 if double else 2.0
        lo, hi = 300.0, 800.0
        for _ in range(60):
            m = 0.5 * (lo + hi)
            lo, hi = (m, hi) if self.teq(m, hours) < target else (lo, m)
        return int(round(0.5 * (lo + hi)))


def solve(data, out, lab=run_temper, plan=PLAN, log=print, lab_dT=0, **kw):
    """lab_dT shifts every laboratory temperature off the equivalent one (a robustness check in the evidence)"""
    rec = Records(data)
    model = Model(rec, **kw)
    tests = []
    for heat, b, double in plan:
        r = rec.batches[b]
        assert r["heat"] == heat, (b, heat)
        D, loc = float(r["ruling_section_diameter_mm"]), r["hardness_location"]
        Tp = model.choose(b)
        Tl = model.lab_temperature(b, Tp, double) + lab_dT
        h = lab(heat, Tl, D, loc, double)
        model.offset[heat] = model.boff[b] = h - model.raw(heat, Tl, D, loc, 4.0 if double else 2.0)
        tests.append((heat, Tl, D, loc, double, h, model.offset[heat]))
        log("test: %s %d C %d mm %s%s -> %.1f HRC (offset %+.2f; aimed at %s, setpoint %d C)" % (
            heat, Tl, D, loc, " double" if double else "", h, model.offset[heat], b, Tp))
    temps = {b: int(model.choose(b)) for b in rec.batches}
    for b, T in temps.items():
        log("%s %s %d C, predicted %.2f HRC" % (b, rec.batches[b]["heat"], T, model.predict(b, T)))
    if out:
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        with open(out, "w") as f:
            json.dump({"tempering_C": temps}, f, indent=1)
    return temps, tests


if __name__ == "__main__":
    solve(sys.argv[1] if len(sys.argv) > 1 else "/app/data", sys.argv[2] if len(sys.argv) > 2 else "/app/output/tempering.json")
