"""Shared machinery for the evidence scripts: an in-process copy of the laboratory and the weigh shop (the same
readings as environment/rig/lab.py for the same seed and reading order), the reference's model with a switch for
every step a solver can take differently, and grading against the sealed definition.
"""
import json
import os
import re
import sys

import numpy as np

sys.dont_write_bytecode = True
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "authoring", "provenance"))
sys.path.insert(0, os.path.join(ROOT, "solution"))
import isim as S  # noqa: E402
import solve  # noqa: E402

DATA = os.path.join(ROOT, "environment", "data")
SEED = json.load(open(os.path.join(ROOT, "authoring", "provenance", "seed.json")))["seed"]
SEEDS = list(range(4101, 4121))
IDS = sorted(S.CYL)
ITEMS = [(cid, part) for cid in IDS for part in ("pressure", "limit")]
PLAN = ("gc 2", "weigh 3B")
_R = None
_LINER, _TREND = None, None


class Lab:
    """the services of environment/rig/lab.py, in process"""

    def __init__(self, seed=SEED):
        self.seed, self.n, self.log = seed, 0, []

    def _book(self, what):
        self.n += 1
        if self.n > S.BUDGET:
            raise RuntimeError("over the allowance")
        self.log.append(what)
        return self.n

    def gc(self, stage):
        self._book("gc %s" % stage)
        return S.lab_gc(int(stage))

    def weigh(self, cid):
        idx = self._book("weigh %s" % cid)
        rng = np.random.default_rng([self.seed, idx, 5, list(S.LAB_CMDS).index("weigh"), IDS.index(cid)])
        return S.lab_weigh(cid, rng)


def liner(first=False):
    global _LINER
    if _LINER is None:
        rs = sorted(solve.rows(DATA, "liner_records.csv"), key=lambda r: r["date"])
        _LINER = ({}, {})
        for r in rs:
            _LINER[0][r["cylinder"]] = r
            _LINER[1].setdefault(r["cylinder"], r)
    return _LINER[1 if first else 0]


def trend():
    global _TREND
    if _TREND is None:
        _TREND = sorted(solve.rows(DATA, "temperature_trend.csv"), key=lambda r: r["month"])
    return _TREND


class Agent(solve.Model):
    """the reference model with a switch for each step

    plan        the readings drawn, in order (default ("gc 2", "weigh 3B"))
    bypass      True carries the second stage's analysis to the third, which the maintenance log settles
    interstage  "settle" the pressures of RC-4 2.1, "measured" the operating record's values held fixed
    speed       "contract" the speed the contract flow needs, "record" the drive record's held speed
    balance     "molar" each stage passes the molar flow of the one before it, "volumetric" the swept volume
                matched instead, "nocond" the condensate ignored, "design" the design fraction of the bypassed
                separator used
    range_      "speed" the range ends where the speed reaches the rated speed, "floor" at the standard's floor
    rod_load    "bulletin" the reduced rating, "sheet" the data sheet's
    derate      True applies the de-rating of the repaired throw
    bore        "asbored" the latest liner entry's mean bore, "nominal" the schedule's nominal, "earliest" the
                liner record's first entry, "largest" or "smallest" the latest entry's extremes
    rod         "schedule" each throw's own rod, "common" the common 65 mm
    clearance   "pockets" the open pockets from the register, "log" the same from the maintenance log,
                "both_ends" the pocket over the swept volume of both ends, "one_clearance" the head end's figure
                used for both ends, "sheet" the data sheet's
    ts          "reading" the element's reading, "design" the design value, "trend" the last month of the trend
    bottle      True corrects a bottle-mounted element to the valve flange
    gas         "stage" each stage's own analysis, "sheet" the data sheet's, "feed" the feed for every stage
    weight      "records" the weights as the records and the weighing give them, "sheet" the data sheet's,
                "as_fitted" the shop ticket's piston as fitted read as the difference
    valve       True applies the standard's valve losses
    inertia     "full", "primary" (the secondary term dropped), "none"
    glim        "cylinder" the cylinder's allowable gas load, "frame" the throw's rated rod load
    crank_area  "rod" the crank end area less the rod, "norod" the bore area at both ends
    kappa       "computed" the iterated exponent at the mean temperature, "suction" at the suction temperature
                only, "discharge" at the discharge temperature, or a number
    scan        "down" the standard's rule, "up" the first acceptable pressure from the bottom
    reversal    True checks pin reversal
    nth         crank angles per revolution
    step        the resolution of the pressure scan, bar
    td_tol      the convergence test on the discharge temperature, K
    margin      "ratio" or "difference"
    sweeps      how many passes the interstage balance is taken through
    """

    def __init__(self, R, lab, **sw):
        super().__init__(R, lab)
        self.sw = sw
        self.NTH = int(sw.get("nth", 360))

    # --- the plan -------------------------------------------------------------------------------------------
    def plan(self):
        for item in self.sw.get("plan", PLAN):
            cmd, arg = item.split()
            if cmd == "gc":
                self._gas[int(arg)] = self.lab.gc(int(arg))
            else:
                self._weight[arg] = self.lab.weigh(arg)
        if self.sw.get("bypass", True):
            if 2 in self._gas and 3 not in self._gas:
                self._gas[3] = self._gas[2]
            if 3 in self._gas and 2 not in self._gas:
                self._gas[2] = self._gas[3]

    # --- the duty -------------------------------------------------------------------------------------------
    def condensate(self, after_stage):
        mode = self.sw.get("balance", "molar")
        if mode == "nocond":
            return 0.0
        if mode == "design":
            return S.CONDENSATE_DESIGN[after_stage]
        return super().condensate(after_stage)

    def molar_per_rev(self, stage, ps, pd):
        if self.sw.get("balance") == "volumetric":
            return self.stage_swept(stage, ps, pd)
        return super().molar_per_rev(stage, ps, pd)

    def table(self):
        if self._table is None:
            g = self.grid()
            if self.sw.get("interstage") == "measured":
                opr = {r["item"]: r for r in solve.rows(DATA, "operating_record.csv")}
                p12 = np.full_like(g, float(opr["first interstage pressure measured"]["value"]))
                p23 = np.full_like(g, float(opr["second interstage pressure measured"]["value"]))
            else:
                p12, p23 = self.split(g, sweeps=int(self.sw.get("sweeps", 16)))
            if self.sw.get("speed") == "record":
                held = sorted(solve.rows(DATA, "drive_record.csv"), key=lambda r: r["date"])[-1]
                sp = np.full_like(g, float(held["speed_held_rev_min"]))
            else:
                sp = self.speed(g, p12)
            inside = sp <= self.R["rpm_rated"] if self.sw.get("range_", "speed") == "speed" \
                else np.ones(g.size, dtype=bool)
            self._table = (g, p12, p23, sp, inside)
        return self._table

    def grid(self):
        step = float(self.sw.get("step", solve.STEP))
        top = self.R["field"]
        return np.round(np.arange(round(top * solve.FLOOR, 2), top + step / 2.0, step), 4)

    # --- the machine ----------------------------------------------------------------------------------------
    def bore(self, cid):
        mode = self.sw.get("bore")
        if mode == "nominal":
            return float(self.R["schedule"][cid]["nominal_bore_mm"])
        if mode in ("largest", "smallest"):
            return float(liner()[cid]["%s_bore_mm" % mode])
        if mode == "earliest":
            return float(liner(first=True)[cid]["mean_bore_mm"])
        return super().bore(cid)

    def rod(self, cid):
        return 65.0 if self.sw.get("rod") == "common" else super().rod(cid)

    def clearance(self, cid):
        mode = self.sw.get("clearance")
        r = self.R["schedule"][cid]
        he, ce = float(r["clearance_head_end_sheet"]), float(r["clearance_crank_end_sheet"])
        sw_he, sw_ce = self.swept(cid)
        pocket = float(r["clearance_pocket_cm3"])
        if mode == "sheet":
            return he, ce
        if mode == "log":
            throws = [int(x) for x in re.search(r"pockets of throws (\d+) and (\d+) opened",
                                                self.R["log"]).groups()]
            return he + (pocket / (sw_he * 1e6) if self.throw(cid) in throws else 0.0), ce
        if mode == "both_ends":
            open_ = self.throw(cid) in self.R["pocket_throws"]
            return he + (pocket / ((sw_he + sw_ce) * 1e6) if open_ else 0.0), ce
        if mode == "one_clearance":
            c_he = super().clearance(cid)[0]
            return c_he, c_he
        return super().clearance(cid)

    def weight(self, cid):
        mode = self.sw.get("weight")
        if mode == "sheet":
            return float(self.R["schedule"][cid]["reciprocating_weight_kg_sheet"])
        if mode == "as_fitted" and cid not in self._weight and self.throw(cid) == self.R["piston_throw"]:
            return float(self.R["schedule"][cid]["reciprocating_weight_kg_sheet"]) + S.PISTON["2B"][0]
        return super().weight(cid)

    def rod_limit(self, cid):
        base = float(self.R["schedule"][cid]["rated_rod_load_kN_sheet"])
        if self.sw.get("rod_load", "bulletin") == "bulletin":
            base *= self.R["bulletin"]
        if self.sw.get("derate", True) and self.throw(cid) == self.R["derate_throw"]:
            return min(base, self.R["derate_kn"])
        return base

    def gas_limit(self, cid):
        return self.rod_limit(cid) if self.sw.get("glim") == "frame" else super().gas_limit(cid)

    def suction_t(self, stage):
        if self.sw.get("ts") == "design":
            sheet = solve.text(DATA, "docs/machine_data_sheet.md")
            design = {int(a): float(b) for a, b in
                      re.findall(r"\n\| (\d) \| [\d.]+ \| [\d.]+ \| ([\d.]+) \|", sheet)}
            t = design[stage]
        elif self.sw.get("ts") == "trend":
            t = float(trend()[-1]["stage_%d_suction_C" % stage])
        else:
            t = self.R["ts_read"][stage]
        tag = self.R["ts_tag"][stage]
        if self.sw.get("bottle", True) and "bottle" in self.R["inst"][tag]["mounting"]:
            t += solve.BOTTLE
        return t

    def gas(self, stage):
        if self.sw.get("gas") == "sheet":
            return self.R["sheet_gas"]
        if self.sw.get("gas") == "feed":
            return self.R["feed"]
        return super().gas(stage)

    def kappa_td(self, stage, ps, pd):
        mode = self.sw.get("kappa", "computed")
        if mode == "computed":
            keep = solve.TD_TOL
            solve.TD_TOL = float(self.sw.get("td_tol", keep))
            try:
                return super().kappa_td(stage, ps, pd)
            finally:
                solve.TD_TOL = keep
        ts = self.suction_t(stage)
        r = self.ratio(ps, pd)
        if mode == "suction":
            k = self.kappa_at(stage, ts)
        elif mode == "discharge":
            k = self.kappa_at(stage, super().kappa_td(stage, ps, pd)[1])
        else:
            k = float(mode)
        return k, (ts + 273.15) * r ** ((k - 1.0) / k) - 273.15

    # --- the requirements -----------------------------------------------------------------------------------
    def areas(self, cid):
        a_he, a_ce = super().areas(cid)
        return (a_he, a_he) if self.sw.get("crank_area") == "norod" else (a_he, a_ce)

    def ratio(self, ps, pd):
        if not self.sw.get("valve", True):
            return pd / ps
        return super().ratio(ps, pd)

    def inertia(self, cid, speed):
        mode = self.sw.get("inertia", "full")
        if mode == "none":
            return np.zeros((np.size(speed), self.NTH))
        if mode == "primary":
            th, _, _ = self.angles()
            w = speed[:, None] * 2.0 * np.pi / 60.0
            return -self.weight(cid) * w * w * (self.R["stroke"] / 2000.0) * np.cos(th) / 1e3
        return super().inertia(cid, speed)

    def margins(self, cid):
        m = super().margins(cid)
        if self.sw.get("margin") == "difference":
            g, p12, p23, speed, _ = self.table()
            st = self.stage(cid)
            ps, pd = {1: (g, p12), 2: (p12, p23), 3: (p23, np.full_like(g, self.R["pipe"]))}[st]
            a_he, a_ce = self.areas(cid)
            _, head_first, _ = self.angles()
            head = np.where(head_first, pd[:, None], ps[:, None])
            crank = np.where(head_first, ps[:, None], pd[:, None]) * (1.0 if self.double(cid) else 0.0)
            gas = (head * a_he - crank * a_ce) * 1e2
            comb = gas + self.inertia(cid, speed)
            m = dict(m)
            m["gas_load"] = self.gas_limit(cid) - np.abs(gas).max(axis=1)
            m["rod_load_compression"] = self.rod_limit(cid) - comb.max(axis=1)
            m["rod_load_tension"] = self.rod_limit(cid) + comb.min(axis=1)
            m["discharge_temperature"] = solve.TD_LIMIT - self.kappa_td(st, ps, pd)[1]
        return m

    def checked(self):
        return tuple(q for q in solve.REQS if q != "pin_reversal" or self.sw.get("reversal", True))

    def answer(self, cid):
        if self.sw.get("scan") != "up":
            ps, req = super().answer(cid)
            return (None, None) if ps is None else (round(ps + 1e-9, 2), req)
        g, _, _, _, inside = self.table()
        m = self.margins(cid)
        ok = inside.copy()
        for q in self.checked():
            ok &= m[q] >= 0.0
        if not ok.any():
            return None, None
        i = int(np.argmax(ok))
        return round(float(g[i]) + 1e-9, 2), min(solve.REQS, key=lambda q: m[q][max(i - 1, 0)])


def records():
    global _R
    if _R is None:
        _R = solve.load(DATA)
    return _R


def route(seed=SEED, **sw):
    """one route: ({cylinder: (bar, requirement)}, the readings used)"""
    lab = Lab(seed)
    A = Agent(records(), lab, **sw)
    try:
        A.plan()
    except RuntimeError:
        pass
    return {cid: A.answer(cid) for cid in IDS}, list(lab.log)


def grade(sheet):
    """(values right, {(cylinder, part): error}, (worst cylinder, worst relative error))"""
    truth = S.truth()
    err, n = {}, 0
    for cid in IDS:
        tp, tq = truth[cid]
        gp, gq = sheet.get(cid, (None, None))
        rel = 99.0 if gp is None else (gp - tp) / tp
        err[(cid, "pressure")] = rel
        err[(cid, "limit")] = 0.0 if gq == tq else 1.0
        n += int(abs(rel) <= S.TOL + 1e-12) + int(gq == tq)
    wc = max(IDS, key=lambda c: abs(err[(c, "pressure")]))
    return n, err, (wc, err[(wc, "pressure")])


def failed_items(err):
    return [k for k in ITEMS if (abs(err[k]) > S.TOL + 1e-12 if k[1] == "pressure" else err[k] != 0.0)]


def over_bar(err, mult=2.0):
    """the items this route fails by at least mult tolerances, or on the requirement, which is categorical"""
    return [k for k in ITEMS if (abs(err[k]) >= mult * S.TOL if k[1] == "pressure" else err[k] != 0.0)]


def fmt(sheet):
    return "  ".join("%s %s %s" % (cid, "----" if sheet[cid][0] is None else "%.2f" % sheet[cid][0],
                                   sheet[cid][1] or "-") for cid in IDS)
