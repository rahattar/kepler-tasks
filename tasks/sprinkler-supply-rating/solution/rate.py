#!/usr/bin/env python3
"""Reference rating of the ten risers under FP-12, from the site's records alone.

    python3 rate.py [DATA_DIR] [OUT_CSV]

The budget of FP-12 is identified element by element and then evaluated at the reference condition:

1. The city main's static S at any moment comes from the utility's record, referred to the site datum.
2. Gauge readings are corrected by the certificate of the gauge that was on the riser that day (register and
   maintenance log). A serial in the round's log that disagrees is kept only if the readings break at it.
3. With nothing flowing the backflow preventer holds the yard at the highest the main has stood since the last
   flow, less its opening differential h_b. So h_b (and a lead-in check's h_c) come from the statics of tests that
   follow another test of the same round closely, against the main's highest pressure in between; the first
   static of a round, held since the round before, is not used.
4. B comes from the utility's flow tests (pitot flow with the hydrant's outlet coefficient and the number of
   outlets open), Cv_b from the yard flow tests, each for the assembly before and after its overhaul.
5. Each main drain test then gives the riser's own flow-dependent loss at the drain's flow: the main's static at
   that minute, less the residual, less every other element at that flow. Lined ductile iron is C 140, so what
   is left over on such a lead-in is its control valve; cast iron's C is fitted against time and read at the
   audit date.
6. One flow cannot tell friction (q^1.85) from a partly shut valve (q^2). A supervised valve is open by clause
   3.4. A locked valve on ductile iron follows from the one flow; a locked valve on cast iron with a wall hydrant
   follows once the hydrant's tests have given the lead-in's C. A locked valve on cast iron with neither is open
   to every split between the two, and the one flow test goes to the riser whose pressure that leaves widest, at
   the highest flow the header can be set to, where the two laws stand furthest apart.
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
FOLLOW_MIN = 90                    # a static is usable when another test of the round ended this recently
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
            out.append(dict(riser=rid, t=t, static=float(r["static_psi"]) - z + h,
                            resid_gauge=float(r["residual_psi"]) - z, resid=float(r["residual_psi"]) - z + h))
        out.sort(key=lambda x: x["t"])
        return out

    # ---- opening differentials, from the statics that follow another test closely
    def usable_statics(self, tests):
        for prev, cur in zip(tests, tests[1:]):
            gap = (cur["t"] - prev["t"]).total_seconds() / 60.0
            if 0 < gap <= FOLLOW_MIN:
                yield cur, self.main.highest(prev["t"], cur["t"])

    def opening(self, tests):
        held = {}
        for cur, S_high in self.usable_statics(tests):
            held.setdefault((cur["riser"], self.era(cur["t"])), []).append(S_high - cur["static"])
        plain = [rid for rid in self.reg if not self.reg[rid]["lead_in_check"]]
        h_b = [float(np.mean([v for rid in plain for v in held.get((rid, e), [])])) for e in (0, 1)]
        h_c = {rid: float(np.mean([v - h_b[e] for e in (0, 1) for v in held.get((rid, e), [])]))
               for rid in self.reg if self.reg[rid]["lead_in_check"]}
        return h_b, h_c

    # ---- the city main
    def main_B(self):
        Bs = []
        for u in self.d["utility"]:
            Q = self.hydrant_flow(u["flow_hydrant"], u["outlets_flowing"], u["pitot_psi"])
            Bs.append((float(u["static_psi"]) - float(u["residual_psi"])) / (Q / 1000.0) ** HW)
        return float(np.mean(Bs))

    # ---- the backflow preventer's flow coefficient, before and after the overhaul
    def bfp_cv(self, B, h_b, h_c):
        inv = {0: [], 1: []}
        on_lead_in = {r["wall_hydrant"] for r in self.reg.values() if r.get("wall_hydrant")}
        for y in self.d["yard"]:
            if y["flow_hydrant"] in on_lead_in:
                continue                               # a wall hydrant's test takes in its lead-in's loss
            t = stamp(y["date"], y["time"])
            rid = y["gauge_riser"]
            Q = self.hydrant_flow(y["flow_hydrant"], y["outlets_flowing"], y["pitot_psi"])
            p_yard = float(y["residual_psi"]) - self.zero(rid, t, None) + self.height(rid) + h_c.get(rid, 0.0)
            left = self.static_main(t) - p_yard - B * (Q / 1000.0) ** HW - h_b[self.era(t)]
            inv[self.era(t)].append(left / Q ** 2)
        return [1.0 / math.sqrt(np.mean(inv[e])) if inv[e] else float("nan") for e in (0, 1)]

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
            tee = float(y["residual_psi"]) - self.zero(rid, t, None) + self.height(rid)
            loss = self.static_main(t) - tee - B * (Q / 1000.0) ** HW - h_b[e] - (Q / Cv_b[e]) ** 2
            k = loss / Q ** HW
            Cs.append((4.52 * float(r["wall_hydrant_at_equiv_ft"]) / (k * PIPE_ID[(material, size)] ** 4.87)) ** (1 / HW))
            years.append((t - AUDIT).total_seconds() / (365.25 * 86400))
        if len(Cs) < 2:
            return float(np.mean(Cs)) if Cs else None
        return self.cast_iron_C(np.array(years), np.array(Cs))

    def attribute(self, rid, rows, site=None):
        """(C, Cv of the control valve, how the split was settled)."""
        r = self.reg[rid]
        size, material, L = r["lead_in_size_in"], r["lead_in_material"], float(r["lead_in_equiv_length_ft"])
        years = np.array([(t - AUDIT).total_seconds() / (365.25 * 86400) for t, _q, _o in rows])
        q = np.array([v for _t, v, _o in rows])
        own = np.array([v for _t, _q, v in rows])
        cv_open = VALVE_OPEN[size]
        d487 = PIPE_ID[(material, size)] ** 4.87

        def valve_from(C):
            """The valve's Cv from what the lead-in at C leaves over, on the tests since the last work."""
            keep = self.since_last_work(rid, rows)
            left = own[keep] - k_lead(L, C, material, size) * q[keep] ** HW
            excess = left - (q[keep] / cv_open) ** 2
            se = excess.std(ddof=1) / math.sqrt(len(excess))
            if excess.mean() > max(0.3, 4 * se):
                return 1.0 / math.sqrt(np.mean(left / q[keep] ** 2))
            return cv_open

        def friction_only():
            k = (own - (q / cv_open) ** 2) / q ** HW
            return self.cast_iron_C(years, (4.52 * L / (k * d487)) ** (1 / HW))

        if material == "DI-CL":
            return 140.0, (valve_from(140.0) if self.locked(rid) else cv_open), "ductile iron"
        if not self.locked(rid):
            return friction_only(), cv_open, "supervised"
        C_h = self.hydrant_C(rid, *site) if site else None
        if C_h is not None:
            return C_h, valve_from(C_h), "wall hydrant"
        if self.report and self.report["riser"] == rid and site:
            return self.split_by_test(rid, rows, site) + ("flow test",)
        return friction_only(), cv_open, "open"

    def split_by_test(self, rid, rows, site):
        """Friction and valve from two flows: the last year's main drain tests and the ordered flow test."""
        B, h_b, Cv_b = site
        r, rep = self.reg[rid], self.report
        size, material, L = r["lead_in_size_in"], r["lead_in_material"], float(r["lead_in_equiv_length_ft"])
        t = stamp(rep["date"], rep["time"])
        q2 = float(rep["flow_gpm"])
        S = float(rep["transmitter_psi"]) - PSI_FT * PIT_BELOW_FT
        p2 = float(rep["residual_psi"]) - self.zero(rid, t, rep["gauge_serial"]) + self.height(rid)
        own2 = S - p2 - B * (q2 / 1000.0) ** HW - h_b[1] - (q2 / Cv_b[1]) ** 2
        recent = [(q, o) for when, q, o in rows if (AUDIT - when).days <= 366]
        q1 = float(np.mean([q for q, _o in recent]))
        own1 = float(np.mean([o for _q, o in recent]))
        A = np.array([[q1 ** HW, q1 ** 2], [q2 ** HW, q2 ** 2]])
        k, v = np.linalg.solve(A, np.array([own1, own2]))
        v = max(v, 1.0 / VALVE_OPEN[size] ** 2)
        k = max(k, 1e-9)
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
        h_b, h_c = self.opening(tests)
        B = self.main_B()
        Cv_b = self.bfp_cv(B, h_b, h_c)
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
                q1 = float(np.mean([q for _t, q, _o in rows]))
                own1 = float(np.mean([o for _t, _q, o in rows]))
                k_new = k_lead(L, C_NEW_CAST_IRON, material, size)
                v = max((own1 - k_new * q1 ** HW) / q1 ** 2, 0.0)
                q, _Q = self.flows(qd)
                other = p_base + kl * q ** HW + (q / cv_valve) ** 2 - k_new * q ** HW - v * q ** 2
                out[rid]["open_by"] = abs(other - p_base) / p_base
        out["_site"] = dict(S_ref=S_ref, B=B, h_b=h_b, Cv_b=Cv_b, h_c=h_c)
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
    print("S_ref %.2f  B %.3f  h_b %.2f -> %.2f  Cv_b %.0f -> %.0f  h_c %s" % (
        site["S_ref"], site["B"], site["h_b"][0], site["h_b"][1], site["Cv_b"][0], site["Cv_b"][1],
        {k: round(v, 2) for k, v in site["h_c"].items()}), file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv)
