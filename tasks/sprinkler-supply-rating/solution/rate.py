#!/usr/bin/env python3
"""Reference rating of the ten risers under FP-12, from the site's records alone.

    python3 rate.py [DATA_DIR] [OUT_CSV]

The budget of FP-12 is identified element by element and then evaluated at the reference condition:

1. The city main's static S at any moment comes from the utility's record, referred to the site datum.
2. Gauge readings are corrected by the certificate of the gauge that was on the riser that day (register and
   maintenance log). A serial in the round's log that disagrees is kept only if the readings break at it.
3. B comes from the utility's flow tests (pitot flow with the hydrant's outlet coefficient and the number of
   outlets open).
4. The backflow preventer's loss is h_b + (Q/Cv_b)^2, a line in Q^2. Two flows fix it for each era, before and
   after the overhaul: the drain tests of the risers whose own loss is known (ductile iron, no check, the valve
   certainly open) near 400 gpm, and the yard hydrant tests near 1 200 gpm. A yard test that sits off the line
   its era's other tests draw says the gauge it was read on stands off the yard main by that much, and the same
   constant then belongs to every reading of that gauge. What a ductile lead-in with a check leaves over, and
   which does not move with the flow, is its check's opening differential.
5. Each main drain test then gives the riser's own flow-dependent loss at the drain's flow: the main's static at
   that minute, less the residual, less every other element at that flow. Lined ductile iron is C 140, so what
   is left over on such a lead-in is its control valve; cast iron's C is fitted against time and read at the
   audit date.
6. One flow cannot tell friction (q^1.85) from a partly shut valve (q^2). Every valve was open when the records
   begin and a supervised one still is. A locked valve can have been left partly shut by a piece of logged work,
   and the pipe says which: a loss that rises at the work is the valve, with the pipe's own trend carried past
   it; a loss that falls is the pipe improved (a swab), and then the pipe's new C and the valve are both free
   with one flow since. A wall hydrant's tests give C by themselves. The one flow test goes to the riser whose
   pressure the records leave widest, at the highest flow the header can be set to, where the two laws stand
   furthest apart.
"""
import csv
import datetime as dt
import math
import os
import re
import sys

import numpy as np

HW = 1.85
PSI_FT = 0.433
PIT_BELOW_FT = 8.0
HOSE = 500.0
AUDIT = dt.datetime(2026, 10, 5)
REF_FROM, REF_TO = dt.date(2026, 7, 1), dt.date(2026, 9, 30)
PIPE_ID = {("DI-CL", "6"): 6.16, ("DI-CL", "8"): 8.27, ("CI", "6"): 6.00, ("CI", "8"): 8.00}
OUTLET_C = {"H-41": 0.90, "H-42": 0.90, "H-43": 0.80, "YH-1": 0.90, "YH-2": 0.90, "YH-3": 0.80, "WH-6": 0.90}
DRAIN_K = {"2 in. angle": 52.0, "1-1/2 in. globe": 36.0}
VALVE_OPEN = {"6": 5200.0, "8": 9800.0}
CHECK_CV = {"6": 2100.0, "8": 3900.0}
C_NEW_CAST_IRON = 100.0
TEST_FLOW = 1000.0                 # the highest flow the test header can be set to


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def stamp(date, time):
    return dt.datetime.strptime(date + " " + time, "%Y-%m-%d %H:%M")


class Main:
    def __init__(self, rows):
        self.t = np.array([(dt.datetime.strptime(r["timestamp"], "%Y-%m-%d %H:%M") - AUDIT).total_seconds() / 60.0
                           for r in rows])
        self.S = np.array([float(r["pressure_psi"]) for r in rows]) - PSI_FT * PIT_BELOW_FT
        self.when = [dt.datetime.strptime(r["timestamp"], "%Y-%m-%d %H:%M") for r in rows]

    def x(self, t):
        return (t - AUDIT).total_seconds() / 60.0

    def at(self, t):
        return float(np.interp(self.x(t), self.t, self.S))

    def highest(self, t0, t1):
        a, b = self.x(t0), self.x(t1)
        inside = self.S[(self.t >= a) & (self.t <= b)]
        return max([self.at(t0), self.at(t1)] + ([float(inside.max())] if len(inside) else []))

    def reference(self):
        v = [s for s, w in zip(self.S, self.when)
             if REF_FROM <= w.date() <= REF_TO and w.weekday() < 5 and 17 <= w.hour < 20]
        return float(np.mean(v))


def k_lead(L, C, material, size):
    return 4.52 * L / (C ** HW * PIPE_ID[(material, size)] ** 4.87)


def load(data):
    reg = {r["riser"]: r for r in read_csv(os.path.join(data, "riser_register.csv"))}
    cert = {}
    for line in open(os.path.join(data, "gauge_certificates.md")):
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 5 and re.match(r"G-\d+", cells[0]):
            cert[cells[0]] = float(np.mean([float(c) for c in cells[2:]]))
    maint = [dict(when=dt.datetime.strptime(r["date"], "%Y-%m-%d"), item=r["item"], work=r["work"])
             for r in read_csv(os.path.join(data, "maintenance_log.csv"))]
    return dict(reg=reg, cert=cert, maint=maint,
                main=Main(read_csv(os.path.join(data, "utility_pressure.csv"))),
                drain=read_csv(os.path.join(data, "main_drain_log.csv")),
                utility=read_csv(os.path.join(data, "utility_flow_tests.csv")),
                yard=read_csv(os.path.join(data, "yard_flow_tests.csv")))


def history(d):
    """What the maintenance log changes: the gauge on a riser, its drain pattern, the day the backflow preventer
    was overhauled, and the days a control valve was worked on."""
    gauge = {rid: [(r["supply_gauge_serial"], None)] for rid, r in d["reg"].items()}
    drain = {rid: [(r["main_drain"], None)] for rid, r in d["reg"].items()}
    valve_work = {rid: [] for rid in d["reg"]}
    overhaul = None
    for m in d["maint"]:
        w = m["work"]
        g = re.search(r"gauge (G-\d+) .*replaced by (G-\d+)", w)
        if g and m["item"] in gauge:
            gauge[m["item"]] = [(g.group(1), m["when"]), (g.group(2), None)]
        if "drain valve" in w.lower() and "replaced" in w.lower():
            for pattern in DRAIN_K:
                if pattern in w:
                    drain[m["item"]] = [(d["reg"][m["item"]]["main_drain"], m["when"]), (pattern, None)]
        if m["item"] == "connection" and "overhaul" in w.lower():
            overhaul = m["when"]
        if "control valve" in w.lower() and m["item"] in valve_work:
            valve_work[m["item"]].append(m["when"])
    return gauge, drain, valve_work, overhaul


def at(schedule, t):
    for value, until in schedule:
        if until is None or t < until:
            return value
    return schedule[-1][0]


class Audit:
    """The audit, step by step. Each step is a method so that a study can replace one and see what it costs."""

    def __init__(self, data, report=None):
        self.d = load(data)
        self.main, self.reg, self.cert = self.d["main"], self.d["reg"], self.d["cert"]
        self.gauge, self.drain, self.valve_work, self.overhaul = history(self.d)
        self.report = report                       # the contractor's flow test, once ordered
        self.work = {rid: [m["when"] for m in self.d["maint"] if m["item"] == rid] for rid in self.reg}

    # ---- conventions
    def era(self, t):
        return 0 if self.overhaul is not None and t < self.overhaul else 1

    def zero(self, rid, t, logged):
        """The zero error of the gauge that produced a reading: the gauge the register and the maintenance log put
        on the riser that day."""
        return self.cert[at(self.gauge[rid], t)]

    def height(self, rid):
        return PSI_FT * float(self.reg[rid]["supply_gauge_height_ft"])

    def static_main(self, t):
        return self.main.at(t)

    def reference_static(self):
        return self.main.reference()

    def hydrant_flow(self, hydrant, outlets, pitot):
        return int(outlets) * 29.84 * OUTLET_C[hydrant] * 2.5 ** 2 * math.sqrt(float(pitot))

    def drain_k(self, rid, t):
        return DRAIN_K[at(self.drain[rid], t)]

    # ---- the round's tests, corrected and at the datum
    def tests(self):
        out = []
        for r in self.d["drain"]:
            t = stamp(r["date"], r["time"])
            rid = r["riser"]
            z, h = self.zero(rid, t, r["gauge_serial"]), self.height(rid)
            out.append(dict(riser=rid, t=t, resid_gauge=float(r["residual_psi"]) - z,
                            resid=float(r["residual_psi"]) - z + h))
        out.sort(key=lambda x: x["t"])
        return out

    # ---- the connection: h_b and Cv_b of each era from two flows, and the gauges the yard tests contradict
    def known_riser_tests(self, tests, B):
        """(era, flow^2, loss across the backflow preventer) from the drain tests of risers whose own loss is
        known: ductile iron, no check, and the valve certainly open (supervised, or locked and not yet worked on)."""
        pts = []
        for x in tests:
            r = self.reg[x["riser"]]
            if r["lead_in_material"] != "DI-CL" or r["lead_in_check"]:
                continue
            if self.locked(x["riser"]) and self.work[x["riser"]] and x["t"] >= min(self.work[x["riser"]]):
                continue
            size = r["lead_in_size_in"]
            q = self.drain_k(x["riser"], x["t"]) * math.sqrt(x["resid_gauge"])
            own = k_lead(float(r["lead_in_equiv_length_ft"]), 140.0, "DI-CL", size) * q ** HW + (q / VALVE_OPEN[size]) ** 2
            pts.append((self.era(x["t"]), q ** 2, self.static_main(x["t"]) - x["resid"] - own - B * (q / 1000.0) ** HW))
        return pts

    def yard_points(self, B):
        """(era, flow^2, loss across the backflow preventer as the gauge riser's gauge puts it, gauge riser)."""
        on_lead_in = {r["wall_hydrant"] for r in self.reg.values() if r.get("wall_hydrant")}
        pts = []
        for y in self.d["yard"]:
            if y["flow_hydrant"] in on_lead_in:
                continue                               # a wall hydrant's test takes in its lead-in's loss
            t = stamp(y["date"], y["time"])
            rid = y["gauge_riser"]
            Q = self.hydrant_flow(y["flow_hydrant"], y["outlets_flowing"], y["pitot_psi"])
            p_yard = float(y["residual_psi"]) - self.zero(rid, t, None) + self.height(rid)
            pts.append((self.era(t), Q ** 2, self.static_main(t) - p_yard - B * (Q / 1000.0) ** HW, rid))
        return pts

    GAUGE_OFF = 0.8          # psi: a gauge riser whose yard tests sit this far off the line is itself off

    def common_path(self, tests, B):
        """h_b and Cv_b for each era, and for each riser the constant by which its gauge stands off the yard main
        (zero unless its yard tests say otherwise). The loss across the assembly is h_b + flow^2 / Cv_b^2, a line
        in flow^2: the known risers' drain tests fix it near 400 gpm and the yard tests near 1 200. A yard test
        that sits off the line its era's other tests draw is a statement about the gauge it was read on."""
        known, yard = self.known_riser_tests(tests, B), self.yard_points(B)
        suspect = set()
        while True:
            fit = {}
            for e in (0, 1):
                x = [p[1] for p in known if p[0] == e] + [p[1] for p in yard if p[0] == e and p[3] not in suspect]
                y = [p[2] for p in known if p[0] == e] + [p[2] for p in yard if p[0] == e and p[3] not in suspect]
                slope, h = np.polyfit(x, y, 1)
                fit[e] = (float(h), float(slope))
            off = {}
            for e, x, y, rid in yard:
                off.setdefault(rid, []).append(y - (fit[e][0] + fit[e][1] * x))
            worst = max((rid for rid in off if rid not in suspect), key=lambda rid: abs(np.mean(off[rid])), default=None)
            if worst is None or abs(np.mean(off[worst])) < self.GAUGE_OFF:
                break
            suspect.add(worst)
        h_b = [fit[0][0], fit[1][0]]
        Cv_b = [1.0 / math.sqrt(fit[0][1]), 1.0 / math.sqrt(fit[1][1])]
        const = {rid: (float(np.mean(off[rid])) if rid in suspect else 0.0) for rid in self.reg}
        return h_b, Cv_b, const

    def check_openings(self, tests, B, h_b, Cv_b):
        """h_c of each lead-in check: what a ductile lead-in's drain tests leave over, which does not move with
        the flow."""
        h_c = {}
        for rid, r in self.reg.items():
            if not r["lead_in_check"]:
                continue
            size = r["lead_in_size_in"]
            left = []
            for x in tests:
                if x["riser"] != rid:
                    continue
                e = self.era(x["t"])
                q = self.drain_k(rid, x["t"]) * math.sqrt(x["resid_gauge"])
                left.append(self.static_main(x["t"]) - x["resid"] - B * (q / 1000.0) ** HW - h_b[e] - (q / Cv_b[e]) ** 2
                            - k_lead(float(r["lead_in_equiv_length_ft"]), 140.0, "DI-CL", size) * q ** HW
                            - (q / VALVE_OPEN[size]) ** 2 - (q / CHECK_CV[size]) ** 2)
            h_c[rid] = float(np.mean(left))
        return h_c

    # ---- the city main
    def main_B(self):
        Bs = []
        for u in self.d["utility"]:
            Q = self.hydrant_flow(u["flow_hydrant"], u["outlets_flowing"], u["pitot_psi"])
            Bs.append((float(u["static_psi"]) - float(u["residual_psi"])) / (Q / 1000.0) ** HW)
        return float(np.mean(Bs))

    # ---- one riser's own flow-dependent loss at each of its tests
    def own_series(self, rid, tests, B, h_b, Cv_b, h_c):
        size = self.reg[rid]["lead_in_size_in"]
        rows = []
        for x in tests:
            if x["riser"] != rid:
                continue
            e = self.era(x["t"])
            q = self.drain_k(rid, x["t"]) * math.sqrt(x["resid_gauge"])
            own = self.static_main(x["t"]) - x["resid"] - B * (q / 1000.0) ** HW - h_b[e] - (q / Cv_b[e]) ** 2
            if rid in h_c:
                own -= h_c[rid] + (q / CHECK_CV[size]) ** 2
            rows.append((x["t"], q, own))
        return rows

    # ---- what the own loss is made of: the lead-in's C and the control valve's Cv, as they stand
    def locked(self, rid):
        return self.reg[rid]["valve_supervision"] == "lock"

    def since_last_work(self, rid, rows):
        """The tests since the last logged work on the riser (all of them where the log records none)."""
        since = max(self.work[rid]) if self.work[rid] else None
        keep = np.array([since is None or t >= since for t, _q, _o in rows])
        return keep if keep.sum() >= 6 else np.ones(len(rows), bool)

    def hydrant_C(self, rid, B, h_b, Cv_b):
        """The lead-in's C from the flow tests of its wall hydrant, read at the audit date; None without one."""
        r = self.reg[rid]
        if not r.get("wall_hydrant"):
            return None
        size, material = r["lead_in_size_in"], r["lead_in_material"]
        years, Cs = [], []
        for y in self.d["yard"]:
            if y["flow_hydrant"] != r["wall_hydrant"] or y["gauge_riser"] != rid:
                continue
            t = stamp(y["date"], y["time"])
            e = self.era(t)
            Q = self.hydrant_flow(y["flow_hydrant"], y["outlets_flowing"], y["pitot_psi"])
            tee = float(y["residual_psi"]) - self.zero(rid, t, None) + self.height(rid) + self.const.get(rid, 0.0)
            loss = self.static_main(t) - tee - B * (Q / 1000.0) ** HW - h_b[e] - (Q / Cv_b[e]) ** 2
            k = loss / Q ** HW
            Cs.append((4.52 * float(r["wall_hydrant_at_equiv_ft"]) / (k * PIPE_ID[(material, size)] ** 4.87)) ** (1 / HW))
            years.append((t - AUDIT).total_seconds() / (365.25 * 86400))
        if len(Cs) < 2:
            return float(np.mean(Cs)) if Cs else None
        return self.cast_iron_C(np.array(years), np.array(Cs))

    def attribute(self, rid, rows, site=None):
        """(C, Cv of the control valve, how the split was settled).

        Every valve was fully open when the records begin (clause 3.4). A supervised valve still is. A locked one
        can have been left partly shut by a piece of logged work on its riser, and the pipe tells which: a lead-in
        only gets worse slowly, so a loss that rises at a piece of work is the valve, and one that falls is the
        pipe improved (a swab), after which the pipe's new C is unknown and the valve may have been left partly
        shut as well."""
        r = self.reg[rid]
        size, material, L = r["lead_in_size_in"], r["lead_in_material"], float(r["lead_in_equiv_length_ft"])
        when = np.array([t for t, _q, _o in rows])
        years = np.array([(t - AUDIT).total_seconds() / (365.25 * 86400) for t in when])
        q = np.array([v for _t, v, _o in rows])
        own = np.array([v for _t, _q, v in rows])
        cv_open = VALVE_OPEN[size]
        d487 = PIPE_ID[(material, size)] ** 4.87
        self.open_rows = getattr(self, "open_rows", {})

        def valve_from(C, keep):
            """The valve's Cv from what the lead-in at C leaves over on the tests kept."""
            left = own[keep] - 4.52 * L / (C ** HW * d487) * q[keep] ** HW
            excess = left - (q[keep] / cv_open) ** 2
            se = excess.std(ddof=1) / math.sqrt(len(excess))
            if excess.mean() > max(0.3, 4 * se):
                return 1.0 / math.sqrt(np.mean(left / q[keep] ** 2))
            return cv_open

        if material == "DI-CL":
            keep = self.since_last_work(rid, rows)
            return 140.0, (valve_from(140.0, keep) if self.locked(rid) else cv_open), "ductile iron"

        # cast iron: each test read as friction alone
        C_each = (4.52 * L / ((own - (q / cv_open) ** 2) / q ** HW * d487)) ** (1 / HW)
        improved, shut = None, None
        for D in sorted(self.work[rid]):
            before, after = when < D, when >= D
            if improved is not None:
                before = before & (when >= improved)
            if before.sum() < 6 or after.sum() < 2:
                continue
            slope, at0 = np.polyfit(years[before], C_each[before], 1)
            scatter = (C_each[before] - (at0 + slope * years[before])).std(ddof=2)
            step = float(np.mean(C_each[after] - (at0 + slope * years[after])))
            bar = max(3.0, 4 * scatter / math.sqrt(after.sum()))
            if step > bar:
                improved, shut = D, None                   # the pipe was improved here
            elif step < -bar:
                shut = (D, slope, at0)                     # the loss rose here: the valve
        seg = when >= improved if improved is not None else np.ones(len(rows), bool)

        def fitted(keep):
            return self.cast_iron_C(years[keep], C_each[keep]) if keep.sum() >= 8 else float(np.mean(C_each[keep]))

        C_h = self.hydrant_C(rid, *site) if site else None
        if C_h is not None:
            return C_h, (valve_from(C_h, self.since_last_work(rid, rows)) if self.locked(rid) else cv_open), \
                "wall hydrant"
        if not self.locked(rid):
            return fitted(seg), cv_open, "supervised"
        if improved is None:
            if shut is None:
                return fitted(seg), cv_open, "records"
            D, slope, at0 = shut                           # the pipe's own trend carried past the work
            return float(at0), valve_from(float(at0), when >= D), "records"
        # a locked valve on a lead-in improved by the last work: C and Cv both free, one flow since
        self.open_rows[rid] = [row for row, k in zip(rows, seg) if k]
        if self.report and self.report["riser"] == rid and site:
            return self.split_by_test(rid, self.open_rows[rid], site) + ("flow test",)
        return float(np.mean(C_each[seg])), cv_open, "open"

    def split_by_test(self, rid, rows, site):
        """Valve and lead-in from the ordered flow test: the fall from the flange gauge to the supply gauge is the
        valve's loss, and the fall from the main to the flange, less the backflow preventer's, is the lead-in's.
        The transmitter stands on the main, so with the test flowing it already shows the main drawn down."""
        B, h_b, Cv_b = site
        r, rep = self.reg[rid], self.report
        size, material, L = r["lead_in_size_in"], r["lead_in_material"], float(r["lead_in_equiv_length_ft"])
        t = stamp(rep["date"], rep["time"])
        q2 = float(rep["flow_gpm"])
        main_now = float(rep["transmitter_psi"]) - PSI_FT * PIT_BELOW_FT
        p2 = (float(rep["residual_psi"]) - self.zero(rid, t, rep["gauge_serial"]) + self.height(rid)
              + self.const.get(rid, 0.0))
        flange = float(rep["flange_psi"])
        v = max(max(flange - p2, 0.0) / q2 ** 2, 1.0 / VALVE_OPEN[size] ** 2)
        k = max(main_now - flange - h_b[1] - (q2 / Cv_b[1]) ** 2, 1e-6) / q2 ** HW
        k = max(k, 4.52 * L / (C_NEW_CAST_IRON ** HW * PIPE_ID[(material, size)] ** 4.87))
        C = (4.52 * L / (k * PIPE_ID[(material, size)] ** 4.87)) ** (1 / HW)
        return float(C), 1.0 / math.sqrt(v)

    def cast_iron_C(self, years, C_each):
        """C against the years before the audit date, read at the audit date."""
        _slope, C = np.polyfit(years, C_each, 1)
        return float(C)

    def flows(self, qr):
        """(flow through the lead-in, flow through the connection) with the riser taking qr."""
        return qr, qr + HOSE

    # ---- the budget at the reference condition
    def rate(self):
        tests = self.tests()
        B = self.main_B()
        h_b, Cv_b, self.const = self.common_path(tests, B)
        for x in tests:
            x["resid"] += self.const[x["riser"]]
        h_c = self.check_openings(tests, B, h_b, Cv_b)
        S_ref = self.reference_static()
        out = {}
        for rid, r in self.reg.items():
            size, material, L = r["lead_in_size_in"], r["lead_in_material"], float(r["lead_in_equiv_length_ft"])
            rows = self.own_series(rid, tests, B, h_b, Cv_b, h_c)
            C, cv_valve, settled = self.attribute(rid, rows, (B, h_b, Cv_b))
            kl = k_lead(L, C, material, size)

            def base(qr):
                q, Q = self.flows(qr)
                loss = {"city-main": B * (Q / 1000.0) ** HW, "backflow": h_b[1] + (Q / Cv_b[1]) ** 2,
                        "lead-in": kl * q ** HW, "valve": (q / cv_valve) ** 2,
                        "check": (h_c[rid] + (q / CHECK_CV[size]) ** 2) if rid in h_c else 0.0}
                return S_ref - sum(loss.values()), loss

            qd = float(r["placard_flow_gpm"])
            p_base, loss = base(qd)
            lo, hi = 0.0, qd
            for _ in range(60):
                mid = 0.5 * (lo + hi)
                if base(mid)[0] > float(r["placard_pressure_psi"]):
                    lo = mid
                else:
                    hi = mid
            out[rid] = dict(limit=max(loss, key=loss.get), p_base_psi=p_base, q_avail_gpm=0.5 * (lo + hi),
                            loss=loss, C=C, cv_valve=cv_valve, settled=settled)
            if settled == "open":
                # the other end of what the records admit: the lead-in as new and the valve taking the rest
                q1 = float(np.mean([q for _t, q, _o in self.open_rows[rid]]))
                own1 = float(np.mean([o for _t, _q, o in self.open_rows[rid]]))
                k_new = k_lead(L, C_NEW_CAST_IRON, material, size)
                v = max((own1 - k_new * q1 ** HW) / q1 ** 2, 0.0)
                q, _Q = self.flows(qd)
                other = p_base + kl * q ** HW + (q / cv_valve) ** 2 - k_new * q ** HW - v * q ** 2
                out[rid]["open_by"] = abs(other - p_base) / p_base
        out["_site"] = dict(S_ref=S_ref, B=B, h_b=h_b, Cv_b=Cv_b, h_c=h_c,
                            gauges_off={k: round(v, 2) for k, v in self.const.items() if v})
        return out


def rate(data, report=None):
    return Audit(data, report).rate()


def plan(data):
    """The order: the riser the records leave widest open, at the highest flow. None when nothing is open."""
    res = Audit(data).rate()
    widest = max((rid for rid in res if not rid.startswith("_")), key=lambda rid: res[rid].get("open_by", 0.0))
    if res[widest].get("open_by", 0.0) <= 0.0:
        return None, res
    return {"riser": widest, "flow_gpm": TEST_FLOW}, res


def write(res, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["riser", "limit", "p_base_psi", "q_avail_gpm"])
        for rid in sorted(k for k in res if not k.startswith("_")):
            w.writerow([rid, res[rid]["limit"], "%.2f" % res[rid]["p_base_psi"], "%.1f" % res[rid]["q_avail_gpm"]])


def main(argv):
    """rate.py [--plan] [DATA_DIR] [OUT_CSV]. The order is placed with the command in FLOWTEST (default
    `flowtest`) and its report read from FLOWTEST_REPORTS (default /app/flowtest)."""
    import json
    import subprocess
    args = [a for a in argv[1:] if a != "--plan"]
    data = args[0] if len(args) > 0 else "/app/data"
    path = args[1] if len(args) > 1 else "/app/output/rating.csv"
    order, first = plan(data)
    for rid in sorted(k for k in first if not k.startswith("_")):
        print("%s settled by %-12s open by %4.1f per cent" % (rid, first[rid]["settled"],
                                                              100 * first[rid].get("open_by", 0.0)), file=sys.stderr)
    print("order: %s" % json.dumps(order), file=sys.stderr)
    if "--plan" in argv:
        return
    report = None
    if order:
        cmd = os.environ.get("FLOWTEST", "flowtest")
        subprocess.run([cmd, "submit"], input=json.dumps(order), text=True, check=True)
        with open(os.path.join(os.environ.get("FLOWTEST_REPORTS", "/app/flowtest"), "flow_test_report.json")) as f:
            report = json.load(f)
    res = rate(data, report)
    write(res, path)
    site = res["_site"]
    print("S_ref %.2f  B %.3f  h_b %.2f -> %.2f  Cv_b %.0f -> %.0f  h_c %s  gauges off %s" % (
        site["S_ref"], site["B"], site["h_b"][0], site["h_b"][1], site["Cv_b"][0], site["Cv_b"][1],
        {k: round(v, 2) for k, v in site["h_c"].items()}, site["gauges_off"]), file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv)
