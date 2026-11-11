"""Shared machinery for the evidence scripts.

Agent is the reference solution with one switch per step, so a study can replace a single decision and leave the
rest of the assessment alone. Each switch is named in the table below; an unset switch means the reference's own
choice.

    cv        "sheet"    the data sheet coefficient instead of the one the operating record gives
              "linear"   a linear characteristic in place of the equal percentage one
              "maxflow"  the largest flow in the trend taken as the relieving rate
    meter     "raw"      the feed meter read as indicated, with no density correction
    ua        "design"   the reboiler coefficient-area from the data sheet duty and the record temperatures
              "duty"     the data sheet duty taken as the relieving duty itself
    credit    "none"     no credit for instrumented protection
              "all"      credit taken without testing the independence of the initiating element
              "sil"      credit taken without the SIL floor
              "proof"    credit taken without the proof test interval
    rupture   "skip"     the two-thirds rule applied to the wrong ratio (low over low)
              "one"      one tube area discharging instead of two
    orifice   "register" the register's orifice letter instead of the one the valve carries
    setp      "register" the register's set pressure instead of the valve's present setting
    disc      "ignore"   the rupture disc combination factor left out
    raised    "ignore"   elevation changes since the vessel data book left out
    insul     "none"     no insulation credit anywhere
              "always"   insulation credit without a fire resistance certificate
    kv        "one"      the viscosity correction left at 1
    pump      "sheet"    the pump's data sheet curve instead of its latest test
    props     "normal"   relieving fluid properties at the item's normal pressure
    inlet     "skip"     the inlet line rule not checked
    accum     "flat"     10 per cent accumulation for the fire case as well
    firecut   "none"     wetted area not cut at 7.6 m above grade
    firec     "bare"     no drainage or firefighting credit
    level     "full"     the whole shell taken as wetted
    kb        "one"      the back pressure correction left at 1
    kdliq     "vap"      the vapour discharge coefficient used for liquid relief

Sound variations, which the standard permits and which must all pass:

    fit       "ls"       the trend fitted by least squares through the origin instead of averaging per-point values
              "high"     only the trend points above 60 per cent travel used
    uaw       "ratio"    the reboiler coefficient-area from the record's mean duty over its mean difference
    pumpfit   "ls"       the pump curve by least squares on all four points of the latest test
    kviter    2          the viscosity iteration stopped after two passes
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "solution"))
sys.path.insert(0, os.path.join(ROOT, "authoring", "provenance"))
import solve  # noqa: E402

DATA = os.path.join(ROOT, "environment", "data")


def truth():
    """The sealed definition's answer, loaded fresh so a study cannot disturb it."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "isim_truth", os.path.join(ROOT, "authoring", "provenance", "isim.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m, m.truth()


class Agent(solve.Model):
    def __init__(self, d, **sw):
        solve.Model.__init__(self, d)
        self.sw = sw

    # -- the valve as it stands --------------------------------------------
    def as_built(self, vid):
        setp, orif = solve.Model.as_built(self, vid)
        if self.sw.get("setp") == "register":
            setp = solve._num(self.reg[vid]["set_pressure_barg"])
        if self.sw.get("orifice") == "register":
            orif = self.reg[vid]["orifice"]
        return setp, orif

    # -- the feed meter ----------------------------------------------------
    def feed_factor(self):
        if self.sw.get("meter") == "raw":
            return 1.0
        return solve.Model.feed_factor(self)

    # -- control valves ----------------------------------------------------
    def cv_rated(self, tag):
        return self.cached(("agent_cv", tag), lambda: self._agent_cv(tag))

    def _agent_cv(self, tag):
        fit = self.sw.get("fit")
        if fit in ("ls", "high") and not self.sw.get("cv"):
            c = self.cvd[tag]
            r, xt, fp = solve._num(c["rangeability"]), solve._num(c["xt"]), solve._num(c["fp"])
            stream = self.cv_stream(tag)
            num = den = 0.0
            vals = []
            for row in self.d["control_valve_trend"]:
                if row["tag"] != tag:
                    continue
                h = solve._num(row["travel_pct"]) / 100.0
                if fit == "high" and h < 0.60:
                    continue
                p_up, p_dn = solve._num(row["upstream_bara"]), solve._num(row["downstream_bara"])
                w = solve._num(row["flow_kgh"])
                if c["flow_measurement"] == "FE-4011":
                    w *= self.feed_factor()
                mw, k, z, t_K = self.upstream_state(stream, p_up, solve._num(row["upstream_temp_C"]))
                unit = self.valve_flow(1.0, xt, fp, k, p_up, p_dn, self.gas_density(p_up, t_K, mw, z))
                if unit <= 0.0:
                    continue
                if fit == "high":
                    vals.append((w / unit) * 1.156 / r ** (h - 1.0))
                else:
                    x = unit * r ** (h - 1.0) / 1.156      # flow per unit of the rated coefficient
                    num += w * x
                    den += x * x
            return (sum(vals) / len(vals)) if fit == "high" else num / den
        mode = self.sw.get("cv")
        if mode == "sheet":
            return solve._num(self.cvd[tag]["data_sheet_cv_rated"])
        if mode == "linear":
            c = self.cvd[tag]
            xt, fp = solve._num(c["xt"]), solve._num(c["fp"])
            stream = self.cv_stream(tag)
            vals = []
            for row in self.d["control_valve_trend"]:
                if row["tag"] != tag:
                    continue
                p_up, p_dn = solve._num(row["upstream_bara"]), solve._num(row["downstream_bara"])
                h = solve._num(row["travel_pct"]) / 100.0
                w = solve._num(row["flow_kgh"])
                if c["flow_measurement"] == "FE-4011":
                    w *= self.feed_factor()
                mw, k, z, t_K = self.upstream_state(stream, p_up, solve._num(row["upstream_temp_C"]))
                unit = self.valve_flow(1.0, xt, fp, k, p_up, p_dn, self.gas_density(p_up, t_K, mw, z))
                if unit > 0.0:
                    vals.append((w / unit) * 1.156 / h)
            return sum(vals) / len(vals)
        return solve.Model.cv_rated(self, tag)

    # -- reboilers ---------------------------------------------------------
    def reb_ua(self, vid):
        return self.cached(("agent_ua", vid), lambda: self._agent_ua(vid))

    def _agent_ua(self, vid):
        if self.sw.get("uaw") == "ratio" and not self.sw.get("ua"):
            name, bot_stream, prefix = solve.REBOILER[vid]
            wcol = "e%s_steam_kgh" % name.split("-")[1]
            pcol = "e%s_steam_barg" % name.split("-")[1]
            qs, dts = [], []
            for r in self.d["operating_record"]:
                p = solve._num(r[pcol]) + solve.ATM
                qs.append(solve._num(r[wcol]) * self.sat("steam", p, "latent") / 3600.0)
                dts.append(self.sat("steam", p, "t") - solve._num(r["%s_bottoms_C" % prefix]))
            return (sum(qs) / len(qs)) / (sum(dts) / len(dts))
        mode = self.sw.get("ua")
        if mode in ("design", "duty"):
            name, bot_stream, prefix = solve.REBOILER[vid]
            duty = solve._num(self.exch[name]["design_duty_kw"])
            ps = self.steam_supply_barg(vid) + solve.ATM
            dt = self.sat("steam", ps, "t") - self.mean("%s_bottoms_C" % prefix)
            return duty / dt
        return solve.Model.reb_ua(self, vid)

    # -- instrumented protection -------------------------------------------
    def credited(self, vid, case):
        mode = self.sw.get("credit")
        if mode == "none":
            return False
        for r in self.d["sis_register"]:
            if solve.PREVENTS.get(r["contingency_prevented"]) != (vid, case):
                continue
            if mode == "all":
                return True
            if mode == "sil":
                return solve._num(r["proof_test_interval_months"]) <= solve.PROOF_MAX and \
                    r["initiating_element"] not in solve.CONTROL_TAG.get((vid, case), ())
            if mode == "proof":
                return solve._num(r["sil"].split()[-1]) >= solve.SIL_MIN and \
                    r["initiating_element"] not in solve.CONTROL_TAG.get((vid, case), ())
            break
        return solve.Model.credited(self, vid, case)

    # -- geometry ----------------------------------------------------------
    def raised(self, item):
        if self.sw.get("raised") == "ignore":
            return 0.0
        return solve.Model.raised(self, item)

    def wetted_area(self, item):
        if self.sw.get("level") == "full":
            v = dict(self.d["vessel"][item])
            v["highest normal level"] = v["diameter"] if v["shape"] == "horizontal" else v["T-T length"]
            saved = self.d["vessel"][item]
            self.d["vessel"][item] = v
            try:
                return solve.Model.wetted_area(self, item)
            finally:
                self.d["vessel"][item] = saved
        return solve.Model.wetted_area(self, item)

    def f_factor(self, item, t_relief_C):
        mode = self.sw.get("insul")
        if mode == "none":
            return 1.0
        if mode == "always":
            ins = self.d["insul"].get(item)
            if not ins:
                return 1.0
            return (solve._num(ins["conductivity, W/m K"]) / solve._num(ins["thickness, m"])) \
                * (904.0 - t_relief_C) / 21000.0
        return solve.Model.f_factor(self, item, t_relief_C)

    def fire_constant(self):
        if self.sw.get("firec") == "bare":
            return solve.FIRE_C_BARE
        return solve.Model.fire_constant(self)

    # -- sizing ------------------------------------------------------------
    def relieving(self, set_barg, case):
        if self.sw.get("accum") == "flat":
            return set_barg * (1.0 + solve.OVER_OTHER) + solve.ATM
        return solve.Model.relieving(self, set_barg, case)

    def kb(self, ratio):
        if self.sw.get("kb") == "one":
            return 1.0
        return solve.Model.kb(self, ratio)

    def kw(self, ratio):
        if self.sw.get("kb") == "one":
            return 1.0
        return solve.Model.kw(self, ratio)

    def kv_visc(self, a, q, rho, visc):
        if self.sw.get("kv") == "one":
            return 1.0
        return solve.Model.kv_visc(self, a, q, rho, visc)

    def area_liquid(self, q, rho, visc, p1_barg, pb_barg, kw_=1.0, kc=1.0):
        n = self.sw.get("kviter")
        if n and not self.sw.get("kdliq"):
            def once(kv):
                return 11.78 * q * ((rho / 1000.0) / ((p1_barg - pb_barg) * 100.0)) ** 0.5 \
                    / (solve.KD_LIQ * kw_ * kc * kv)
            a = once(1.0)
            for _ in range(int(n)):
                a = once(self.kv_visc(a, q, rho, visc))
            return a
        if self.sw.get("kdliq") == "vap":
            kd = solve.KD_VAP

            def once(kv):
                return 11.78 * q * ((rho / 1000.0) / ((p1_barg - pb_barg) * 100.0)) ** 0.5 / (kd * kw_ * kc * kv)
            a = once(1.0)
            for _ in range(60):
                new = once(self.kv_visc(a, q, rho, visc))
                if abs(new - a) < 1.0e-12:
                    return new
                a = new
            return a
        return solve.Model.area_liquid(self, q, rho, visc, p1_barg, pb_barg, kw_, kc)

    def pump_curve(self, vid):
        if self.sw.get("pumpfit") == "ls":
            name = solve.PUMPED[vid]
            sheet = next(r for r in self.d["pump_data"] if r["pump"] == name)
            tests = [r for r in self.d["pump_test_record"] if r["pump"] == name]
            last = max(r["test_date"] for r in tests)
            pts = [(solve._num(r["flow_m3h"]), solve._num(r["head_m"])) for r in tests
                   if r["test_date"] == last]
            # least squares on h = h0 + c q^2, then b = -c / h0
            n = len(pts)
            sx = sum(q * q for q, _ in pts)
            sxx = sum((q * q) ** 2 for q, _ in pts)
            sy = sum(h for _, h in pts)
            sxy = sum(q * q * h for q, h in pts)
            det = n * sxx - sx * sx
            c = (n * sxy - sx * sy) / det
            h0 = (sy - c * sx) / n
            return h0, -c / h0, solve._num(sheet["normal_suction_pressure_barg"])
        shutoff, b, suction = solve.Model.pump_curve(self, vid)
        if self.sw.get("pump") == "sheet":
            sheet = next(r for r in self.d["pump_data"] if r["pump"] == solve.PUMPED[vid])
            shutoff = solve._num(sheet["data_sheet_shutoff_head_m"])
        return shutoff, b, suction

    def kc_factor(self, vid):
        if self.sw.get("disc") == "ignore":
            return 1.0
        return solve.Model.kc_factor(self, vid)

    def vapour_state(self, vid, p1):
        if self.sw.get("props") == "normal":
            p1 = self.item_normal_pressure(vid) + solve.ATM
        return solve.Model.vapour_state(self, vid, p1)

    def item_normal_pressure(self, vid):
        item = self.reg[vid]["protected_item"].lower().replace("-", "")
        for c in self.d["operating_record"][0]:
            if c.startswith(item) and c.endswith("pressure_barg"):
                return self.mean(c)
        return self.mean("p401_discharge_barg")

    # -- cases -------------------------------------------------------------
    def case_area(self, vid, case):
        if case == "tube_rupture" and self.sw.get("rupture") == "skip":
            e = self.exch[solve.EXCHANGER[vid]]
            if solve._num(e["shell_design_barg"]) / solve._num(e["shell_design_barg"]) >= solve.TWO_THIRDS:
                return None
        if case == "tube_rupture" and self.sw.get("rupture") == "one":
            a = solve.Model.case_area(self, vid, case)
            return None if a is None else a / 2.0
        if case == "control_valve_failure" and self.sw.get("cv") == "maxflow":
            tag, _ = solve.ADMITS[vid]
            w = max(solve._num(r["flow_kgh"]) for r in self.d["control_valve_trend"] if r["tag"] == tag)
            setp, _ = self.as_built(vid)
            p1 = self.relieving(setp, case)
            reg = self.reg[vid]
            bp = solve._num(reg["superimposed_back_pressure_barg"])
            kb_ = self.kb(bp / p1) if reg["valve_type"] == "bellows" else 1.0
            kc = solve.KC_DISC if reg["rupture_disc_upstream"] == "yes" else 1.0
            mw, k, z, t_K = self.vapour_state(vid, p1)
            return self.area_vapour(w, p1, t_K, mw, k, z, kb_, kc)
        if case == "cooling_failure" and self.sw.get("props") == "normal":
            name, bot_stream, prefix = solve.REBOILER[vid]
            setp, _ = self.as_built(vid)
            pn = self.item_normal_pressure(vid) + solve.ATM
            ps = self.steam_supply_barg(vid) + solve.ATM
            q = self.reb_ua(vid) * max(0.0, self.sat("steam", ps, "t") - self.sat(bot_stream, pn, "t"))
            w = 3600.0 * q / self.sat(self.reg[vid]["relieving_fluid"], pn, "latent")
            p1 = self.relieving(setp, case)
            reg = self.reg[vid]
            bp = solve._num(reg["superimposed_back_pressure_barg"])
            kb_ = self.kb(bp / p1) if reg["valve_type"] == "bellows" else 1.0
            mw, k, z, t_K = self.vapour_state(vid, p1)
            return self.area_vapour(w, p1, t_K, mw, k, z, kb_, self.kc_factor(vid))
        if case == "cooling_failure" and self.sw.get("ua") == "duty":
            name, bot_stream, prefix = solve.REBOILER[vid]
            setp, _ = self.as_built(vid)
            p1 = self.relieving(setp, case)
            q = solve._num(self.exch[name]["design_duty_kw"])
            w = 3600.0 * q / self.sat(self.reg[vid]["relieving_fluid"], p1, "latent")
            reg = self.reg[vid]
            bp = solve._num(reg["superimposed_back_pressure_barg"])
            kb_ = self.kb(bp / p1) if reg["valve_type"] == "bellows" else 1.0
            mw, k, z, t_K = self.vapour_state(vid, p1)
            return self.area_vapour(w, p1, t_K, mw, k, z, kb_, 1.0)
        return solve.Model.case_area(self, vid, case)

    def inlet_drop(self, vid, case):
        if self.sw.get("inlet") == "skip":
            return 0.0
        if self.sw.get("inletcase") == "fire" and "fire" in self.reg[vid]["contingencies"].split() \
                and self.vapour_case(vid, "fire"):
            case = "fire"
        return solve.Model.inlet_drop(self, vid, case)

    def f_dummy(self):
        return None


def compare(rows, tru, tol):
    """Rows as the sheet gives them against the sealed answer. Returns (n_right, per-valve notes)."""
    notes = {}
    n = 0
    for vid, case, need, verd in rows:
        t = tru[vid]
        why = []
        if case != t["case"]:
            why.append("case %s" % case)
        rel = (need - t["area"]) / t["area"] if t["area"] else 0.0
        if abs(rel) > tol + 1.0e-12:
            why.append("area %+.1f%%" % (100.0 * rel))
        if verd != t["verdict"]:
            why.append("verdict %s" % verd)
        notes[vid] = why
        if not why:
            n += 1
    return n, notes


def worst(notes):
    for vid in sorted(notes):
        if notes[vid]:
            return "%s %s" % (vid, "; ".join(notes[vid]))
    return ""


def run(d, **sw):
    return Agent(d, **sw).sheet()
