#!/usr/bin/env python3
"""Reference solution: the lowest field pressure at which each cylinder of K-4101 may be run while the unit holds
its contract flow, and the requirement of RC-4 that governs it.

    python3 solution/solve.py [DATA_DIR] [OUT_CSV]

Reads only the records in /app/data and the two readings the allowance pays for, and writes
/app/output/cylinder_limits.csv.

The duty is not in the records beyond the field pressure, the pipeline pressure and the contract flow. The
pressures between the stages settle where each stage passes what the stage before it delivers, less the condensate
its separator knocks out; the speed is whatever the contract flow needs at those pressures; and the range ends
where that speed reaches the rated speed of the frame. Every cylinder is therefore coupled to every other.

The machine is whatever the records say it is now, which is not what the data sheet says it was: one liner is at
the first repair size, one throw carries a heavier new piston and another a spare assembly of unknown weight, two
clearance pockets stand open, the rated rod load of every throw is reduced by the service bulletin and one throw is
de-rated below that, one suction temperature element sits on a bottle and reads well above its design value, one
interstage separator is bypassed, and the gas is neither the data sheet's nor the same in every stage.

The plan for the allowance. Four facts want a reading: the gas of the second stage, the gas of the third, and the
reciprocating weights of throws 4 and 6, which the maintenance log calls for along with throw 2. Two come out of
the records instead: the separator after the second stage has been bypassed since 2026-08-19, so the third stage
takes the gas the second stage discharges; and the register's shop ticket gives the piston fitted to throw 4 and
the piston removed, so that assembly's weight is the data sheet's plus the difference. Throw 2 has no entry in the
register at all, so the data sheet's weight stands. The two readings go on the second stage's analysis and the
weighing of throw 6.

The steps are separate methods of Model so that one of them can be changed on its own: authoring/evidence
subclasses it to study the routes a solver can take.
"""
import csv
import os
import re
import subprocess
import sys

import numpy as np

# RC-4 revision 8, quoted by clause. These are the method, not the plant's records.
DPS = 0.35          # 4, suction valve loss, bar
DPD = 0.70          # 4, discharge valve loss, bar
TD_LIMIT = 135.0    # 4.3, allowable discharge temperature, C
BOTTLE = 6.0        # 2.4, correction from a bottle-mounted element to the valve flange, K
REV_MIN = 15        # 4.5, least reversal, whole degrees
STEP = 0.01         # 5, resolution, bar
FLOOR = 0.50        # 2.3, bottom of the range, as a fraction of today's field pressure
TD_TOL = 0.001      # 3, convergence test on the discharge temperature, K
RGAS = 8314.0       # J per kmol per K
REQS = ("gas_load", "rod_load_compression", "rod_load_tension", "discharge_temperature",
        "cylinder_power", "pin_reversal")


def rows(data, name):
    with open(os.path.join(data, name)) as f:
        return list(csv.DictReader(f))


def text(data, name):
    with open(os.path.join(data, name)) as f:
        return f.read()


def load(data):
    """every record the method needs, as the records give it"""
    R = {}
    sheet = text(data, "docs/machine_data_sheet.md")
    register = text(data, "docs/overhaul_register.md")
    bulletin = text(data, "docs/service_bulletin.md")
    log = rows(data, "maintenance_log.csv")
    R["log_rows"] = [(r["equipment"], r["description"]) for r in log]
    R["log"] = "\n".join(r["description"] for r in log)
    R["stroke"] = float(re.search(r"\| stroke \| ([\d.]+) mm", sheet).group(1))
    R["ratio_L"] = float(re.search(r"crank radius \| ([\d.]+)", sheet).group(1))
    R["rpm_rated"] = float(re.search(r"\| rated speed \| ([\d.]+) rev/min", sheet).group(1))
    # the bulletin reduces the rated rod load of every throw to a fraction of the data sheet's figure
    R["bulletin"] = float(re.search(r"reduced to ([\d.]+) per cent", bulletin).group(1)) / 100.0
    # one throw carries a de-rating of its own; the lower figure applies
    R["derate_kn"] = float(re.search(r"rod load for throw \d+ limited to ([\d.]+) kN", register).group(1))
    R["derate_throw"] = int(re.search(r"rod load for throw (\d+) limited to", register).group(1))
    R["spare_throw"] = int(re.search(r"##[^\n]*throw (\d+) running assembly", register).group(1))
    R["pocket_throws"] = [int(x) for x in
                          re.search(r"clearance pockets, throws (\d+) and (\d+)", register).groups()]
    fitted, removed = re.search(r"piston as fitted ([\d.]+) kg, piston removed ([\d.]+) kg", register).groups()
    R["piston_diff"] = float(fitted) - float(removed)
    R["piston_throw"] = int(re.search(r"##[^\n]*throw (\d+) liner and piston", register).group(1))
    # the separators: the design condensate fraction of each, and whether it is in service
    R["condensate"] = {}
    for tag, stage, frac in re.findall(r"\| (V-\d+) \| (\d) \| ([\d.]+) \|", sheet):
        out = any(eq == tag and "taken out of service" in d for eq, d in R["log_rows"])
        R["condensate"][int(stage)] = 0.0 if out else float(frac)
    prop = rows(data, "component_properties.csv")
    cols = [c for c in prop[0] if c.startswith("cp_over_R_at_")]
    R["cp_T"] = [float(c[len("cp_over_R_at_"):-1]) for c in cols]
    R["cp_over_R"] = {r["component"]: [float(r[c]) for c in cols] for r in prop}
    R["feed"] = {r["component"]: float(r["mol_per_cent"]) for r in rows(data, "gas_analysis_feed.csv")}
    R["sheet_gas"] = {c.strip().replace(" ", "_"): float(v) for c, v in
                      re.findall(r"\| ([a-z ]+) \| ([\d.]+) \|", sheet.split("Gas analysis, design")[1])}
    # the bore of record is the latest entry of the liner record for the cylinder
    R["bore"] = {}
    for r in sorted(rows(data, "liner_records.csv"), key=lambda r: r["date"]):
        R["bore"][r["cylinder"]] = float(r["mean_bore_mm"])
    opr = {r["item"]: r for r in rows(data, "operating_record.csv")}
    R["field"] = float(opr["field pressure at the unit suction"]["value"])
    R["pipe"] = float(opr["pipeline pressure at the unit discharge"]["value"])
    R["contract"] = float(opr["contract flow"]["value"])
    R["ts_read"] = {1: float(opr["first stage suction temperature"]["value"]),
                    2: float(opr["second stage suction temperature"]["value"]),
                    3: float(opr["third stage suction temperature"]["value"])}
    R["ts_tag"] = {1: opr["first stage suction temperature"]["instrument"],
                   2: opr["second stage suction temperature"]["instrument"],
                   3: opr["third stage suction temperature"]["instrument"]}
    R["inst"] = {r["tag"]: r for r in rows(data, "instrument_schedule.csv")}
    R["schedule"] = {r["cylinder"]: r for r in rows(data, "cylinder_schedule.csv")}
    R["ids"] = sorted(R["schedule"])
    R["stage_cyl"] = {st: [c for c in R["ids"] if int(R["schedule"][c]["stage"]) == st] for st in (1, 2, 3)}
    return R


class Lab:
    """the allowance, through the `gc` and `weigh` commands"""

    def __init__(self):
        self.log = []

    def _run(self, cmd, arg):
        out = subprocess.run([cmd, arg], capture_output=True, text=True).stdout
        vals = {}
        for line in out.splitlines():
            if line.startswith("#") or "," not in line:
                continue
            a, b = line.rsplit(",", 1)
            try:
                vals[a.strip()] = float(b)
            except ValueError:
                pass
        if not vals:
            sys.exit("the reading failed:\n%s" % out)
        self.log.append("%s %s" % (cmd, arg))
        return vals

    def gc(self, stage):
        return self._run("gc", str(stage))

    def weigh(self, cid):
        return self._run("weigh", cid)[cid]


class Model:
    """RC-4 applied to the machine the records describe. Each step is a method of its own so that the evidence
    scripts can change one of them and leave the rest alone.
    """

    NTH = 360       # crank angles per revolution; the standard counts the reversal in whole degrees

    def __init__(self, R, lab):
        self.R, self.lab = R, lab
        self._gas, self._weight = {}, {}
        self._table = None

    def angles(self):
        n = self.NTH
        return np.radians(np.arange(n) * 360.0 / n), np.arange(n) < n // 2, 360.0 / n

    # --- the plan for the allowance -------------------------------------------------------------------------
    def plan(self):
        self._gas[2] = self.lab.gc(2)
        assert "bypassed at the inlet spool" in self.R["log"]
        self._gas[3] = self._gas[2]
        for cid in self.R["ids"]:
            if self.throw(cid) == self.R["spare_throw"]:
                self._weight[cid] = self.lab.weigh(cid)

    # --- the machine as it now stands -----------------------------------------------------------------------
    def throw(self, cid):
        return int(self.R["schedule"][cid]["throw"])

    def stage(self, cid):
        return int(self.R["schedule"][cid]["stage"])

    def double(self, cid):
        return self.R["schedule"][cid]["acting"] == "double"

    def bore(self, cid):
        return self.R["bore"][cid]

    def rod(self, cid):
        return float(self.R["schedule"][cid]["piston_rod_mm"])

    def swept(self, cid):
        a_he, a_ce = self.areas(cid)
        return a_he * self.R["stroke"] / 1000.0, a_ce * self.R["stroke"] / 1000.0

    def clearance(self, cid):
        """each end's clearance as a fraction of its own swept volume, with the open pocket on the head end"""
        r = self.R["schedule"][cid]
        sw_he, _ = self.swept(cid)
        c_he = float(r["clearance_head_end_sheet"])
        if self.throw(cid) in self.R["pocket_throws"]:
            c_he += float(r["clearance_pocket_cm3"]) / (sw_he * 1e6)
        return c_he, float(r["clearance_crank_end_sheet"])

    def weight(self, cid):
        if cid in self._weight:
            return self._weight[cid]
        w = float(self.R["schedule"][cid]["reciprocating_weight_kg_sheet"])
        if self.throw(cid) == self.R["piston_throw"]:
            w += self.R["piston_diff"]
        return w

    def rod_limit(self, cid):
        base = float(self.R["schedule"][cid]["rated_rod_load_kN_sheet"]) * self.R["bulletin"]
        if self.throw(cid) == self.R["derate_throw"]:
            return min(base, self.R["derate_kn"])
        return base

    def gas_limit(self, cid):
        return float(self.R["schedule"][cid]["allowable_gas_load_kN"])

    def rated_power(self, cid):
        return float(self.R["schedule"][cid]["rated_power_kW"])

    def condensate(self, after_stage):
        return self.R["condensate"][after_stage]

    def suction_t(self, stage):
        tag = self.R["ts_tag"][stage]
        t = self.R["ts_read"][stage]
        return t + (BOTTLE if "bottle" in self.R["inst"][tag]["mounting"] else 0.0)

    def gas(self, stage):
        return self._gas.get(stage, self.R["feed"])

    def kappa_at(self, stage, t):
        g, cp_r = self.gas(stage), self.R["cp_over_R"]
        cp = sum(g[c] * np.interp(t, self.R["cp_T"], cp_r[c]) for c in cp_r) / 100.0
        return cp / (cp - 1.0)

    def ratio(self, ps, pd):
        return (pd + DPD) / (ps - DPS)

    def kappa_td(self, stage, ps, pd):
        """RC-4 clauses 3 and 4.3: the exponent is taken at the mean of the suction and discharge temperatures,
        so the two are found together by iteration."""
        ts = self.suction_t(stage)
        r = self.ratio(ps, pd)
        td = np.full(np.shape(r), float(ts))
        k = self.kappa_at(stage, ts)
        for _ in range(300):
            k = self.kappa_at(stage, 0.5 * (ts + td))
            new = (ts + 273.15) * r ** ((k - 1.0) / k) - 273.15
            if np.max(np.abs(new - td)) < TD_TOL:
                return k, new
            td = new
        return k, td

    def vol_eff(self, cid, ps, pd):
        k = self.kappa_td(self.stage(cid), ps, pd)[0]
        g = self.ratio(ps, pd) ** (1.0 / k) - 1.0
        c_he, c_ce = self.clearance(cid)
        return 1.0 - c_he * g, 1.0 - c_ce * g

    # --- the duty -------------------------------------------------------------------------------------------
    def stage_swept(self, stage, ps, pd):
        tot = 0.0
        for cid in self.R["stage_cyl"][stage]:
            sw_he, sw_ce = self.swept(cid)
            ve_he, ve_ce = self.vol_eff(cid, ps, pd)
            tot = tot + sw_he * ve_he + (sw_ce * ve_ce if self.double(cid) else 0.0)
        return tot

    def molar_per_rev(self, stage, ps, pd):
        return (ps - DPS) * 1e5 * self.stage_swept(stage, ps, pd) / (RGAS * (self.suction_t(stage) + 273.15))

    @staticmethod
    def _bisect(f, lo, hi, n=70):
        lo = np.broadcast_to(np.asarray(lo, float), np.shape(hi)).astype(float).copy()
        hi = np.asarray(hi, float).copy()
        flo = f(lo)
        for _ in range(n):
            mid = 0.5 * (lo + hi)
            fm = f(mid)
            same = np.sign(fm) == np.sign(flo)
            lo = np.where(same, mid, lo)
            flo = np.where(same, fm, flo)
            hi = np.where(same, hi, mid)
        return 0.5 * (lo + hi)

    def split(self, field, sweeps=16):
        """RC-4 2.1: the interstage pressures where each stage passes what the one before it delivers"""
        pipe = self.R["pipe"]
        field = np.asarray(field, float)
        p12 = np.sqrt(field * pipe)
        p23 = np.sqrt(p12 * pipe)
        for _ in range(sweeps):
            p12 = self._bisect(
                lambda x: self.molar_per_rev(1, field, x) * (1.0 - self.condensate(1))
                - self.molar_per_rev(2, x, p23), field + 0.6, p23 - 0.6)
            p23 = self._bisect(
                lambda x: self.molar_per_rev(2, p12, x) * (1.0 - self.condensate(2))
                - self.molar_per_rev(3, x, pipe), p12 + 0.6, np.broadcast_to(pipe - 0.6, np.shape(p12)))
        return p12, p23

    def speed(self, field, p12):
        """RC-4 2.2: the speed the contract flow needs, the flow being what the last stage delivers"""
        per_rev = self.molar_per_rev(1, field, p12) * (1.0 - self.condensate(1)) * (1.0 - self.condensate(2))
        return self.R["contract"] / (60.0 * per_rev)

    def grid(self):
        top = self.R["field"]
        return np.round(np.arange(round(top * FLOOR, 2), top + STEP / 2.0, STEP), 2)

    def table(self):
        """RC-4 2.1 to 2.3: the duty at every field pressure, and which of them the drive can hold"""
        if self._table is None:
            g = self.grid()
            p12, p23 = self.split(g)
            sp = self.speed(g, p12)
            self._table = (g, p12, p23, sp, sp <= self.R["rpm_rated"])
        return self._table

    # --- the requirements -----------------------------------------------------------------------------------
    def areas(self, cid):
        a = np.pi / 4.0 * (self.bore(cid) / 1000.0) ** 2
        return a, a - np.pi / 4.0 * (self.rod(cid) / 1000.0) ** 2

    def inertia(self, cid, speed):
        th, _, _ = self.angles()
        w = speed[:, None] * 2.0 * np.pi / 60.0
        return -self.weight(cid) * w * w * (self.R["stroke"] / 2000.0) * (
            np.cos(th) + np.cos(2.0 * th) / self.R["ratio_L"]) / 1e3

    def margins(self, cid):
        """the relative margin of each requirement at every field pressure of the range"""
        g, p12, p23, speed, _ = self.table()
        st = self.stage(cid)
        ps, pd = {1: (g, p12), 2: (p12, p23), 3: (p23, np.full_like(g, self.R["pipe"]))}[st]
        a_he, a_ce = self.areas(cid)
        _, head_first, per_step = self.angles()
        head = np.where(head_first, pd[:, None], ps[:, None])
        crank = np.where(head_first, ps[:, None], pd[:, None]) * (1.0 if self.double(cid) else 0.0)
        gas = (head * a_he - crank * a_ce) * 1e2
        comb = gas + self.inertia(cid, speed)
        k, td = self.kappa_td(st, ps, pd)
        n = (k - 1.0) / k
        ve_he, ve_ce = self.vol_eff(cid, ps, pd)
        sw_he, sw_ce = self.swept(cid)
        ends = sw_he * ve_he + (sw_ce * ve_ce if self.double(cid) else 0.0)
        kw = (ps - DPS) * 1e5 * ends * speed / 60.0 / n * (self.ratio(ps, pd) ** n - 1.0) / 1e3
        lim = self.rod_limit(cid)
        return {
            "gas_load": self.gas_limit(cid) / np.abs(gas).max(axis=1) - 1.0,
            "rod_load_compression": lim / comb.max(axis=1) - 1.0,
            "rod_load_tension": lim / np.maximum(-comb.min(axis=1), 1e-9) - 1.0,
            "discharge_temperature": TD_LIMIT / td - 1.0,
            "cylinder_power": self.rated_power(cid) / kw - 1.0,
            "pin_reversal": (comb < 0.0).sum(axis=1) * per_step / float(REV_MIN) - 1.0,
        }

    def checked(self):
        return REQS

    def answer(self, cid):
        """RC-4 clause 5: the lowest field pressure acceptable there and at every higher pressure in the range"""
        g, _, _, _, inside = self.table()
        m = self.margins(cid)
        ok = inside.copy()
        for q in self.checked():
            ok &= m[q] >= 0.0
        hold = np.cumprod(ok[::-1])[::-1].astype(bool)
        if not hold.any():
            return None, None
        i = int(np.argmax(hold))
        if i == 0:
            return float(g[0]), None
        return float(g[i]), min(REQS, key=lambda q: m[q][i - 1])

    def sheet(self):
        self.plan()
        return {cid: self.answer(cid) for cid in self.R["ids"]}


def main(data="/app/data", out="/app/output/cylinder_limits.csv"):
    R = load(data)
    M = Model(R, Lab())
    s = M.sheet()
    g, p12, p23, sp, inside = M.table()
    if os.path.dirname(out):
        os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        f.write("cylinder,field_pressure_bar,governing_limit\n")
        for cid in R["ids"]:
            f.write("%s,%.2f,%s\n" % (cid, s[cid][0], s[cid][1]))
    print("readings used: %s" % ", ".join(M.lab.log))
    print("today: interstage %.2f and %.2f bar, speed %.1f rev/min" % (p12[-1], p23[-1], sp[-1]))
    print("the range reaches the rated speed at field %.2f bar" % g[inside][0])
    for cid in R["ids"]:
        print("%-3s %7.2f bar  %s" % (cid, s[cid][0], s[cid][1]))


if __name__ == "__main__":
    a = sys.argv[1:3]
    main(a[0] if a else os.environ.get("DATA_DIR", "/app/data"),
         a[1] if len(a) > 1 else os.environ.get("OUT_CSV", "/app/output/cylinder_limits.csv"))
