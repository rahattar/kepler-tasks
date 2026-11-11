"""Shared machinery for the evidence scripts.

Agent is the reference solution with one switch per decision, so a study can change a single reading of the
standard or of the records and leave the rest of the study alone. Each switch is named below; an unset switch
means the reference's own reading.

Defective readings, every one of which must fail:

    setp      "register" the register's set pressure instead of the setting the valve now carries
    air       "essential" the air compressor taken on the essential supply, so power does not carry air
    sis       "normal"   the safety system taken onto the normal supply with the compressor
    failpos   "closed"   every control valve taken to close on a loss of air
    screen    "rated"    section 7 not applied: the pump's rated flow taken as its blocked outlet rate
    credit    "none"     no credit for instrumented protection
              "all"      credit taken without testing any of the four conditions
              "sil"      credit taken without the SIL floor
              "proof"    credit taken without the proof test interval
    cv        "sheet"    the data sheet coefficient instead of the one the operating record gives
              "linear"   a linear characteristic in place of the equal percentage one
              "maxflow"  the largest flow in the trend taken as the relieving rate
    meter     "raw"      the feed meter read as indicated, with no density correction
    ua        "design"   the reboiler coefficient-area from the data sheet duty
              "duty"     the data sheet duty taken as the relieving duty itself
    latent    "overhead" the reboiler duty divided by the overhead vapour's latent heat
    duty      "latent"   the steam taken to give up its latent heat only, with the condensate's sub-cooling left out
    indication "shown"   the level transmitter's indication read as the level in the vessel
    pool      "trend"    the whole control valve trend fitted, across the work on the trim
              "record"   the whole operating record averaged, across the work on the exchanger
              "both"     both records read whole
    couple    "none"     the rates taken at no built-up back pressure, the system never brought together
              "once"      one sweep only, stopped before anything has settled
              "inlet"     every conventional device taken to stand against the pressure at the blinded end
    bonnet    "all"       every device taken as conventional
              "none"      every device taken as balanced
    size      "static"   the tip sized without bringing each candidate out as its own system
              "inlet"    the tip sized on the pressure at the blinded end rather than per device
    pump      "sheet"    the pump's data sheet curve
              "record"   the last performance test on record, made before the rotating element was renewed
    tip       "old"      the loss coefficient of the tip this one replaced, as the 2019 study gives it
    raised    "ignore"   elevation changes since the vessel data book left out
    firecut   "none"     wetted area not cut at 7.6 m above grade
    firec     "bare"     no drainage or firefighting credit
    level     "full"     the whole shell taken as wetted
    insul     "none"     no insulation credit anywhere
              "always"   insulation credit without a fire resistance certificate
    accum     "flat"     10 per cent accumulation for the fire case as well
    tiein     "sheet"    the tie-in the isometrics show, the later modification missed
    header    "whole"    the whole load carried along the whole header, in one length
              "flow"     only the tie-ins of the discharging devices dividing the header
    mixprops  "total"    every length taken with the whole mixture's properties
    tip       "skip"     the loss through the tip left out
    rho       "atm"      every density taken at atmospheric pressure

Sound variations, which the standard permits and which must all pass:

    fit       "ls"       the trend fitted by least squares through the origin instead of averaging
              "high"     only the trend points above 60 per cent travel used
    uaw       "ratio"    the reboiler coefficient-area from the record's mean duty over its mean difference
    pumpfit   "ls"       the pump curve by least squares on all four points of the latest test
"""
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "solution"))
sys.path.insert(0, os.path.join(ROOT, "authoring", "provenance"))
import solve  # noqa: E402

DATA = os.path.join(ROOT, "environment", "data")
SEALED_SEED = os.path.join(ROOT, "environment", "rig", "sealed", "seed.json")
NEEDED = ("tip-backpressure", "pump-shutoff")


def crew_reports(sealed, tests=NEEDED):
    """What the crew's reports hold, built from the sealed model exactly as the crew builds them, so the
    evidence scripts need no rig installed."""
    import json
    seed = json.load(open(SEALED_SEED))["test_seed"]
    out = {}
    for test in tests:
        head, rows, _ = sealed.run_test(test, seed)
        out[test] = [dict(zip(head, row)) for row in rows]
    return out


def truth():
    """The sealed definition's answer, loaded fresh so a study cannot disturb it."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "isim_truth", os.path.join(ROOT, "authoring", "provenance", "isim.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m, m.truth()


class Agent(solve.Study):
    def __init__(self, d, reports=None, **sw):
        solve.Study.__init__(self, d, reports)
        self.sw = sw

    # -- what the records are taken to say ----------------------------------
    def steam_drop(self, name, p_bara):
        if self.sw.get("duty") == "latent":
            return self.sat("steam", p_bara, "latent")      # the latent heat alone, as section 4.4 names it
        return solve.Study.steam_drop(self, name, p_bara)

    def level(self, item):
        if self.sw.get("indication") == "shown":
            return solve._num(self.d["vessel"][item]["highest normal level"])   # the indication read as the level
        return solve.Study.level(self, item)

    # -- the bonnet, and how the system is brought out ----------------------
    def bellows(self, vid):
        mode = self.sw.get("bonnet")
        if mode == "all":
            return False
        if mode == "none":
            return True
        return solve.Study.bellows(self, vid)

    def converge(self, contingency, tip_mm=None):
        mode = self.sw.get("couple")
        if mode == "none":
            keep, self.back = dict(self.back), {}
            try:
                parts = self.discharging(contingency)
                inlet, at = self.header_profile(parts, tip_mm)
                return parts, inlet, at
            finally:
                self.back = keep
        if mode == "once":
            keep, self.back = dict(self.back), {}
            try:
                parts = self.discharging(contingency)
                inlet, at = self.header_profile(parts, tip_mm)
                self.back = at
                parts = self.discharging(contingency)
                inlet, at = self.header_profile(parts, tip_mm)
                return parts, inlet, at
            finally:
                self.back = keep
        if mode == "inlet":
            keep = dict(self.back)
            try:
                self.back = {}
                parts, inlet, at = {}, 0.0, {}
                for _ in range(solve.SWEEP_CAP):
                    parts = self.discharging(contingency)
                    inlet, at = self.header_profile(parts, tip_mm)
                    flat = {vid: inlet for vid in at}      # the blinded end for everyone, not each tie-in
                    moved = max([abs(flat.get(v, 0.0) - self.back.get(v, 0.0))
                                 for v in set(flat) | set(self.back)] or [0.0])
                    self.back = flat
                    if moved <= solve.SETTLE:
                        break
                return parts, inlet, at
            finally:
                self.back = keep
        return solve.Study.converge(self, contingency, tip_mm)

    def sizing(self):
        mode = self.sw.get("size")
        if mode == "static":
            # the shares scaled off the tip as installed, rather than re-converged at each candidate bore
            bores, limit = self._bores_and_limit()
            share0, who, where = self.worst_felt()
            here = solve._mm(self.d["tip"]["bore"])
            for bore in bores:
                if share0 * (here / bore) ** 4 <= limit:
                    return bore, who, share0 * (here / bore) ** 4, where
            return None, "", 0.0, ""
        if mode == "inlet":
            bores, limit = self._bores_and_limit()
            for bore in bores:
                worst = max(self.converge(c, bore)[1] / 10.0 for c in self.contingencies)
                if worst <= limit:
                    who, where = "PSV-409", "power_failure"
                    return bore, who, worst, where
            return None, "", 0.0, ""
        return solve.Study.sizing(self)

    def _bores_and_limit(self):
        flat = " ".join(self.d["flare_system"].split())
        bores = sorted(float(x) for x in
                       re.search(r"Tip bores the vendor supplies ([\d.,and ]+?) mm", flat).group(1)
                       .replace("and", " ").replace(",", " ").split())
        limit = solve._num(re.search(r"more than ([\d.]+) per cent of",
                                     " ".join(self.d["standard"].split())).group(1)) / 100.0
        return bores, limit

    # -- what the crew measured ---------------------------------------------
    def since_work(self, item, rows, column):
        mode = self.sw.get("pool")
        if mode == "both" or (mode == "trend" and column == "timestamp") \
                or (mode == "record" and column == "date"):
            return rows                       # the record read whole, across the work the log records
        return solve.Study.since_work(self, item, rows, column)

    def tip_k(self):
        if self.sw.get("tip") == "old":
            flat = " ".join(self.d["flare_load_study_2019"].split())
            return float(re.search(r"Stack tip loss coefficient ([\d.]+)", flat).group(1))
        return solve.Study.tip_k(self)

    # -- the valve as it stands --------------------------------------------
    def set_pressure(self, vid):
        if self.sw.get("setp") == "register":
            return solve._num(self.reg[vid]["set_pressure_barg"])
        return solve.Study.set_pressure(self, vid)

    def relieving(self, vid, cause):
        if self.sw.get("accum") == "flat":
            return self.set_pressure(vid) * (1.0 + solve.OVER_OTHER) + solve.ATM
        return solve.Study.relieving(self, vid, cause)

    # -- what the contingency reaches --------------------------------------
    def supply_of(self, tag):
        if self.sw.get("air") == "essential" and tag == solve.AIR_COMPRESSOR:
            return "essential"
        return solve.Study.supply_of(self, tag)

    def fails_open(self, tag):
        if self.sw.get("failpos") == "closed":
            return False
        return solve.Study.fails_open(self, tag)

    def sis_holds(self, contingency):
        if self.sw.get("sis") == "normal":
            return contingency != "power_failure"
        return solve.Study.sis_holds(self, contingency)

    def cause_of(self, vid, contingency):
        return solve.Study.cause_of(self, vid, contingency)

    # -- credit -------------------------------------------------------------
    def credited(self, vid, cause, contingency):
        mode = self.sw.get("credit")
        if mode == "none":
            return False
        for r in self.d["sis_register"]:
            if solve.PREVENTS.get(r["contingency_prevented"]) != (vid, cause):
                continue
            if mode == "all":
                return True
            if mode == "sil":
                return solve._num(r["proof_test_interval_months"]) <= solve.PROOF_MAX \
                    and not self.controls(self.reg[vid]["protected_item"], r["initiating_element"]) \
                    and self.sis_holds(contingency)
            if mode == "proof":
                return solve._num(r["sil"].split()[-1]) >= solve.SIL_MIN \
                    and not self.controls(self.reg[vid]["protected_item"], r["initiating_element"]) \
                    and self.sis_holds(contingency)
            break
        return solve.Study.credited(self, vid, cause, contingency)

    # -- the feed meter ----------------------------------------------------
    def feed_factor(self):
        if self.sw.get("meter") == "raw":
            return 1.0
        return solve.Study.feed_factor(self)

    # -- control valves ----------------------------------------------------
    def cv_rated(self, tag):
        return self.cached(("agent_cv", tag), lambda: self._agent_cv(tag))

    def _agent_cv(self, tag):
        mode, fit = self.sw.get("cv"), self.sw.get("fit")
        if mode == "sheet":
            return solve._num(self.cvd[tag]["data_sheet_cv_rated"])
        if mode is None and fit in ("ls", "high"):
            return self._fitted_cv(tag, fit)
        if mode == "linear":
            return self._fitted_cv(tag, "linear")
        return solve.Study.cv_rated(self, tag)

    def _fitted_cv(self, tag, how):
        """The same trend read three other ways the standard's wording allows, or one it does not."""
        c = self.cvd[tag]
        r = solve._num(c["rangeability"])
        xt, fp = solve._num(c["xt"]), solve._num(c["fp"])
        stream = solve.CVSTREAM[tag]
        num = den = 0.0
        vals = []
        for row in self.since_work(tag, [r for r in self.d["control_valve_trend"] if r["tag"] == tag],
                                   "timestamp"):
            h = solve._num(row["travel_pct"]) / 100.0
            if how == "high" and h < 0.60:
                continue
            p_up, p_dn = solve._num(row["upstream_bara"]), solve._num(row["downstream_bara"])
            w = solve._num(row["flow_kgh"])
            if c["flow_measurement"] == "FE-4011":
                w *= self.feed_factor()
            mw, k, z, t_K = self.upstream(stream, p_up, solve._num(row["upstream_temp_C"]))
            unit = self.valve_flow(1.0, xt, fp, k, p_up, p_dn, self.density(p_up, t_K, mw, z))
            if unit <= 0.0:
                continue
            shape = h if how == "linear" else r ** (h - 1.0)
            if how == "ls":
                x = unit * shape / 1.156          # flow per unit of the rated coefficient
                num += w * x
                den += x * x
            else:
                vals.append((w / unit) * 1.156 / shape)
        return num / den if how == "ls" else sum(vals) / len(vals)

    # -- reboilers ---------------------------------------------------------
    def reb_ua(self, vid):
        return self.cached(("agent_ua", vid), lambda: self._agent_ua(vid))

    def _agent_ua(self, vid):
        name, prefix = solve.REBOILER[vid]
        if self.sw.get("uaw") == "ratio" and not self.sw.get("ua"):
            wcol = "e%s_steam_kgh" % name.split("-")[1]
            pcol = "e%s_steam_barg" % name.split("-")[1]
            qs, dts = [], []
            for r in self.since_work(name, self.d["operating_record"], "date"):
                p = solve._num(r[pcol]) + solve.ATM
                qs.append(solve._num(r[wcol]) * self.steam_drop(name, p) / 3600.0)
                dts.append(self.sat("steam", p, "t") - solve._num(r["%s_bottoms_C" % prefix]))
            return (sum(qs) / len(qs)) / (sum(dts) / len(dts))
        if self.sw.get("ua") in ("design", "duty"):
            duty = solve._num(self.exch[name]["design_duty_kw"])
            ps = self.steam_supply_barg(vid) + solve.ATM
            return duty / (self.sat("steam", ps, "t") - self.mean("%s_bottoms_C" % prefix))
        return solve.Study.reb_ua(self, vid)

    # -- geometry ----------------------------------------------------------
    def raised(self, item):
        if self.sw.get("raised") == "ignore":
            return 0.0
        return solve.Study.raised(self, item)

    def wetted_area(self, item):
        if self.sw.get("firecut") == "none":
            saved = solve.FIRE_H
            solve.FIRE_H = 1.0e9
            try:
                return solve.Study.wetted_area(self, item)
            finally:
                solve.FIRE_H = saved
        if self.sw.get("level") == "full":
            v = dict(self.d["vessel"][item])
            v["highest normal level"] = v["diameter"] if v["shape"] == "horizontal" else v["T-T length"]
            saved, shown = self.d["vessel"][item], self.sw.get("indication")
            self.d["vessel"][item] = v
            self.sw["indication"] = "shown"   # the level is being set outright, not read off a transmitter
            try:
                return solve.Study.wetted_area(self, item)
            finally:
                self.d["vessel"][item] = saved
                self.sw["indication"] = shown
        return solve.Study.wetted_area(self, item)

    def f_factor(self, item, t_relief):
        mode = self.sw.get("insul")
        if mode == "none":
            return 1.0
        if mode == "always":
            ins = self.d["insul"].get(item)
            if not ins:
                return 1.0
            return (solve._num(ins["conductivity, W/m K"]) / solve._num(ins["thickness, m"])) \
                * (904.0 - t_relief) / 21000.0
        return solve.Study.f_factor(self, item, t_relief)

    def fire_constant(self):
        if self.sw.get("firec") == "bare":
            return solve.FIRE_BARE
        return solve.Study.fire_constant(self)

    # -- pumps -------------------------------------------------------------
    def pump_curve(self, vid):
        if self.sw.get("pump") == "record":
            saved, self.reports = self.reports, {k: v for k, v in self.reports.items()
                                                 if k != "pump-shutoff"}
            try:
                return solve.Study.pump_curve(self, vid)
            finally:
                self.reports = saved
        if self.sw.get("pumpfit") == "ls":
            name = solve.PUMPED[vid]
            sheet = next(r for r in self.d["pump_data"] if r["pump"] == name)
            fresh = self.reports.get("pump-shutoff")
            if fresh and self.sw.get("pump") != "record":
                pts = [(solve._num(r["flow_m3h"]), solve._num(r["head_m"])) for r in fresh]
            else:
                tests = [r for r in self.d["pump_test_record"] if r["pump"] == name]
                last = max(r["test_date"] for r in tests)
                pts = [(solve._num(r["flow_m3h"]), solve._num(r["head_m"])) for r in tests
                       if r["test_date"] == last]
            n = len(pts)
            sx = sum(q * q for q, _ in pts)
            sxx = sum((q * q) ** 2 for q, _ in pts)
            sy = sum(h for _, h in pts)
            sxy = sum(q * q * h for q, h in pts)
            det = n * sxx - sx * sx
            c = (n * sxy - sx * sy) / det
            h0 = (sy - c * sx) / n
            return h0, -c / h0, solve._num(sheet["normal_suction_pressure_barg"]), \
                solve._num(sheet["temperature_C"])
        shutoff, b, suction, temp = solve.Study.pump_curve(self, vid)
        if self.sw.get("pump") == "sheet":
            sheet = next(r for r in self.d["pump_data"] if r["pump"] == solve.PUMPED[vid])
            shutoff = solve._num(sheet["data_sheet_shutoff_head_m"])
        return shutoff, b, suction, temp

    # -- rates -------------------------------------------------------------
    def rate(self, vid, cause):
        if cause == "control_valve_failure" and self.sw.get("cv") == "maxflow":
            tag, _src = solve.ADMITS[vid]
            w = max(solve._num(r["flow_kgh"]) for r in self.d["control_valve_trend"] if r["tag"] == tag)
            c = self.cvd[tag]
            if c["flow_measurement"] == "FE-4011":
                w *= self.feed_factor()
            return (w,) + self.vapour_state(vid, self.relieving(vid, cause))
        if cause == "blocked_outlet" and self.sw.get("screen") == "rated":
            sheet = next(r for r in self.d["pump_data"] if r["pump"] == solve.PUMPED[vid])
            temp = solve._num(sheet["temperature_C"])
            w = solve._num(sheet["rated_flow_m3h"]) * self.liq("bottoms_product", temp, "rho")
            return (w, 86.0, 1.05, 1.0, temp + 273.15)
        if cause == "cooling_failure" and self.sw.get("latent") == "overhead":
            name, prefix = solve.REBOILER[vid]
            p1 = self.relieving(vid, cause)
            bot = self.d["vessel"][self.reg[vid]["protected_item"]]["liquid held"]
            ps = self.steam_supply_barg(vid) + solve.ATM
            q = self.reb_ua(vid) * max(0.0, self.sat("steam", ps, "t") - self.sat(bot, p1, "t"))
            over = {"PSV-403": "c2_overhead", "PSV-406": "c4_product"}[vid]
            w = 3600.0 * q / self.sat(over, p1, "latent")   # the overhead's latent heat, not the liquid's
            return (w,) + self.vapour_state(vid, p1)
        return solve.Study.rate(self, vid, cause)

    # -- the header --------------------------------------------------------
    def tie_in(self, device):
        if self.sw.get("tiein") == "sheet":
            row = next(r for r in self.d["flare_tie_ins"] if r["device"] == device)
            return solve._num(row["tie_in_m_from_stack_base"])
        return solve.Study.tie_in(self, device)

    def header_profile(self, parts, tip_mm=None):
        """The march, with every reading of section 6 the study tries, returning the inlet and each tie-in."""
        mode = self.sw.get("header")
        at = {}
        if not parts:
            return 0.0, {}
        total, mw_all, k_all, z_all, t_all = self.mixed(parts)
        d_tip = (solve._mm(self.d["tip"]["bore"]) if tip_mm is None else tip_mm) / 1000.0
        rho = self.density(solve.ATM, t_all, mw_all, z_all)
        v = total / 3600.0 / (rho * math.pi / 4.0 * d_tip * d_tip)
        p = solve.ATM
        if self.sw.get("tip") != "skip":
            p += self.tip_k() * rho * v * v / 2.0 / 1.0e5
        d = solve._mm(self.d["header"]["bore"]) / 1000.0
        a = math.pi / 4.0 * d * d
        end = solve._mm(self.d["header"]["developed length, blinded end to the stack base"])
        tie = {r["device"]: self.tie_in(r["device"]) for r in self.d["flare_tie_ins"]}
        if mode == "whole":
            rho = self.density(solve.ATM if self.sw.get("rho") == "atm" else p, t_all, mw_all, z_all)
            v = total / 3600.0 / (rho * a)
            kt = solve.F_DARCY * end / d + sum(solve.K_FIT[f] for f, _ in self.d["fitting"])
            p += kt * rho * v * v / 2.0 / 1.0e5
            return p - solve.ATM, {vid: p - solve.ATM for vid in parts}
        pts = [tie[vid] for vid in parts] if mode == "flow" else list(tie.values())
        cuts = sorted(set([0.0, end] + pts))
        for lo, hi in zip(cuts, cuts[1:]):
            carried = {vid: part for vid, part in parts.items() if tie[vid] >= hi - 1.0e-9}
            if carried:
                w, mw, k, z, t_K = self.mixed(carried)
                if self.sw.get("mixprops") == "total":
                    mw, z, t_K = mw_all, z_all, t_all
                rho = self.density(solve.ATM if self.sw.get("rho") == "atm" else p, t_K, mw, z)
                v = w / 3600.0 / (rho * a)
                kt = solve.F_DARCY * (hi - lo) / d \
                    + sum(solve.K_FIT[f] for f, x in self.d["fitting"] if lo < x <= hi)
                p += kt * rho * v * v / 2.0 / 1.0e5
            for vid in parts:
                if abs(tie[vid] - hi) < 1.0e-9:
                    at[vid] = p - solve.ATM
        return p - solve.ATM, {vid: at.get(vid, p - solve.ATM) for vid in parts}

    def header_pressure(self, parts):
        return self.header_profile(parts)[0]


def compare(rows, sealed, tru, sizing=None):
    """The study and the re-rating against the sealed answer: (n_right, notes), over seven parts."""
    notes, n = {}, 0
    if sizing is not None:
        bore, who, share, _where = sizing
        why = []
        if bore is None:
            why.append("no bore met the limit")
        else:
            ok, how = sealed.sizing_ok(bore, who, share)
            if not how["bore"]:
                why.append("tip %.1f mm, wanted %.1f" % (bore, sealed.sizing()["bore_mm"]))
            if not how["device"]:
                why.append("binding %s, wanted %s" % (who, sealed.sizing()["device"]))
            if how["bore"] and how["device"] and not ok:
                why.append("share %+.1f%%" % (100.0 * how["share"]))
        notes["re-rating"] = why
        if not why:
            n += 1
    for contingency, devices, total, back in rows:
        ok, how = sealed.row_ok(contingency, devices, total, back)
        why = []
        if how["valves"] != 1.0:
            want = tru[contingency]["valves"]
            why.append("devices %s" % (" ".join(devices) if devices else "none"))
            why.append("wanted %s" % " ".join(want))
        else:
            if abs(how["load"]) > sealed.TOL:
                why.append("load %+.1f%%" % (100.0 * how["load"]))
            if not ok and not why:
                why.append("pressure %+.1f%%" % (100.0 * how["back"]))
        notes[contingency] = why
        if ok:
            n += 1
    return n, notes


def worst(notes):
    for name in sorted(notes):
        if notes[name]:
            return "%s %s" % (name, "; ".join(notes[name]))
    return ""


def run(d, reports=None, **sw):
    """The study and the re-rating as this agent gives them."""
    a = Agent(d, reports, **sw)
    return a.sheet(), a.sizing()
