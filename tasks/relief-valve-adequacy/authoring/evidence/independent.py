#!/usr/bin/env python3
"""A second assessment, written separately from solution/solve.py and sharing no code with it.

It reads the same records with pandas, builds one table of every (valve, contingency) pair, and reduces that table
to the finding. Where solve.py walks valve by valve through methods, this builds the whole table at once and
selects; where solve.py interpolates with its own helper, this uses numpy. It takes its own choices where the
standard leaves room: the control valve coefficient by a least squares fit through the origin on the whole trend,
the reboiler coefficient-area from a least squares fit of duty against temperature difference, and the pump curve
from a least squares quadratic on the latest test.

    python3 independent.py [--seeds]
"""
import io
import math
import os
import re
import shutil
import sys
import tempfile

import numpy as np
import pandas as pd

import common

SEEDS = list(range(7301, 7321))

ATM = 1.013
RG = 8314.0
ORIFICE = dict(D=71.0, E=126.0, F=198.0, G=325.0, H=506.0, J=830.0, K=1186.0, L=1841.0,
               M=2323.0, N=2800.0, P=4116.0)
KB = np.array([[0.30, 1.00], [0.35, 0.99], [0.40, 0.97], [0.45, 0.95], [0.50, 0.93]])
KW = np.array([[0.10, 1.00], [0.15, 0.99], [0.20, 0.97], [0.25, 0.95], [0.30, 0.93], [0.40, 0.88]])
MW = dict(n2=28.01, co2=44.01, c1=16.04, c2=30.07, c3=44.10, ic4=58.12, nc4=58.12, c5plus=72.15)
FEEDS = {"PSV-401": ("PV-4001", 72.0), "PSV-407": ("PV-4071", 26.0),
         "PSV-408": ("PV-4061", 16.0), "PSV-409": ("PV-4021", 62.0)}
CVSTREAM = {"PV-4001": "feed_gas", "PV-4021": "feed_gas", "PV-4031": "c2_overhead",
            "PV-4061": "c4_product", "PV-4071": "c3_product"}
REB = {"PSV-403": ("E-403", "t401"), "PSV-406": ("E-406", "t402")}
SHARED = {"PSV-403": "PT-4031", "PSV-406": "PT-4061", "PSV-409": "PT-4021", "PSV-401": None}
SIF_CASE = {"V-401 blocked outlet": ("PSV-401", "blocked_outlet"),
            "T-401 loss of overhead cooling": ("PSV-403", "cooling_failure"),
            "T-402 loss of overhead cooling": ("PSV-406", "cooling_failure"),
            "V-402 control valve failure": ("PSV-409", "control_valve_failure")}
GASTEMP = {"PSV-401": "v401_temp_C", "PSV-409": "v402_temp_C"}
BLOCKED_LIQUID = {"PSV-405"}
RUPTURE = {"PSV-402": "E-402"}


def tables(base):
    g = {}
    for n in ("relief_valve_register", "valve_history", "relief_piping", "control_valve_data",
              "control_valve_trend", "operating_record", "instrument_schedule", "sis_register",
              "exchanger_data", "fluid_properties", "gas_properties", "liquid_properties",
              "gas_analysis", "modification_register", "pump_test_record", "pump_data",
              "blocked_in_sections"):
        g[n] = pd.read_csv(os.path.join(base, n + ".csv"))
    for n in ("unit_400", "vessel_data"):
        with open(os.path.join(base, "docs", n + ".md")) as f:
            g[n] = f.read()
    return g


def pipe_tables(text):
    """Every pipe table in a markdown document, as a list of data frames."""
    out = []
    block = []
    for line in text.splitlines() + [""]:
        if line.strip().startswith("|"):
            block.append(line.strip())
            continue
        if len(block) >= 2:
            body = "\n".join(b for b in block if set(b.replace("|", "").strip()) - set("-: "))
            df = pd.read_csv(io.StringIO(body), sep="|", skipinitialspace=True).dropna(axis=1, how="all")
            df.columns = [c.strip() for c in df.columns]
            for c in df.columns:
                try:
                    df[c] = df[c].str.strip()
                except AttributeError:
                    pass          # a numeric column
            out.append(df)
        block = []
    return out


def pick(frames, *need):
    """The one frame that carries all of these columns."""
    for df in frames:
        if all(c in df.columns for c in need):
            return df
    raise KeyError(need)


def lin(xs, ys, x):
    return float(np.interp(x, xs, ys))


class Assessment(object):
    def __init__(self, base):
        self.g = tables(base)
        v = pipe_tables(self.g["vessel_data"])
        self.vessels = pick(v, "item", "liquid held").set_index("item")
        self.insul = pick(v, "item", "system").set_index("item")
        self.cols = pick(v, "column", "trays").set_index("column")
        u = pipe_tables(self.g["unit_400"])
        self.ctrl = pick(u, "control", "measurement")
        self.adj = pick(u, "device", "protects").set_index("device")
        self.pipeline = float(re.search(r"at the unit limit at ([\d.]+) barg",
                                        re.sub(r"\s+", " ", self.g["unit_400"])).group(1))
        self.reg = self.g["relief_valve_register"].set_index("valve")
        self.pipes = self.g["relief_piping"].set_index("valve")
        self.cvd = self.g["control_valve_data"].set_index("tag")
        self.exch = self.g["exchanger_data"].set_index("item")
        self.rec = self.g["operating_record"]
        self.sat = {k: df.sort_values("pressure_bara")
                    for k, df in self.g["fluid_properties"].groupby("stream")}
        self.lq = {k: df.sort_values("temperature_C")
                   for k, df in self.g["liquid_properties"].groupby("stream")}
        self.gp = self.g["gas_properties"].sort_values("pressure_bara")
        self._fm = None

    # -- properties --------------------------------------------------------
    def s(self, stream, p, col):
        t = self.sat[stream]
        return lin(t["pressure_bara"].values, t[col].values, p)

    def l(self, stream, t_C, col):
        t = self.lq[stream]
        return lin(t["temperature_C"].values, t[col].values, t_C)

    def gk(self, p):
        return lin(self.gp["pressure_bara"].values, self.gp["k"].values, p)

    def gz(self, p):
        return lin(self.gp["pressure_bara"].values, self.gp["z"].values, p)

    def feed_m(self):
        if self._fm is None:
            a = self.g["gas_analysis"].sort_values("sample_date").iloc[-1]
            self._fm = float(sum(a[k] * MW[k] for k in MW))
        return self._fm

    def meter_k(self):
        r = self.g["instrument_schedule"].set_index("tag").loc["FE-4011", "flow_computer_density"]
        held = float(re.search(r"([\d.]+)", str(r)).group(1))
        return math.sqrt((self.feed_m() / 28.96) / held)

    # -- the valve as it stands -------------------------------------------
    def now(self, vid):
        h = self.g["valve_history"]
        h = h[h["valve"] == vid].sort_values("work_date")
        if len(h):
            r = h.iloc[-1]
            return float(r["as_left_set_barg"]), str(r["orifice_fitted"])
        return float(self.reg.loc[vid, "set_pressure_barg"]), str(self.reg.loc[vid, "orifice"])

    # -- identified quantities --------------------------------------------
    def cv_full(self, tag):
        c = self.cvd.loc[tag]
        r, xt, fp = float(c["rangeability"]), float(c["xt"]), float(c["fp"])
        stream = CVSTREAM[tag]
        t = self.g["control_valve_trend"]
        t = t[t["tag"] == tag]
        num = den = 0.0
        for _, row in t.iterrows():
            pu, pd_ = float(row["upstream_bara"]), float(row["downstream_bara"])
            w = float(row["flow_kgh"]) * (self.meter_k() if c["flow_measurement"] == "FE-4011" else 1.0)
            h = float(row["travel_pct"]) / 100.0
            if stream == "feed_gas":
                m, k, z, tk = self.feed_m(), self.gk(pu), self.gz(pu), float(row["upstream_temp_C"]) + 273.15
            else:
                m, k, z = self.s(stream, pu, "vapour_molar_mass"), self.s(stream, pu, "vapour_k"), \
                    self.s(stream, pu, "vapour_z")
                tk = self.s(stream, pu, "saturation_temp_C") + 273.15
            rho = pu * 1e5 * m / (z * RG * tk)
            per = self.cv_flow(1.0, xt, fp, k, pu, pd_, rho) * r ** (h - 1.0)
            num += w * per
            den += per * per
        return 1.156 * num / den

    def ua(self, vid):
        name, pre = REB[vid]
        n = name.split("-")[1]
        q, dt = [], []
        for _, r in self.rec.iterrows():
            p = float(r["e%s_steam_barg" % n]) + ATM
            q.append(float(r["e%s_steam_kgh" % n]) * self.s("steam", p, "latent_heat_kj_per_kg") / 3600.0)
            dt.append(self.s("steam", p, "saturation_temp_C") - float(r["%s_bottoms_C" % pre]))
        q, dt = np.array(q), np.array(dt)
        return float((q * dt).sum() / (dt * dt).sum())

    def pump(self):
        d = self.g["pump_data"].set_index("pump").loc["P-401"]
        t = self.g["pump_test_record"]
        t = t[t["test_date"] == t["test_date"].max()]
        x = (t["flow_m3h"].values.astype(float)) ** 2
        y = t["head_m"].values.astype(float)
        a = np.polyfit(x, y, 1)
        h0 = float(a[1])
        return h0, -float(a[0]) / h0, float(d["normal_suction_pressure_barg"]), float(d["temperature_C"])

    # -- sizing ------------------------------------------------------------
    @staticmethod
    def cv_flow(kv, xt, fp, k, pu, pd_, rho):
        if pu <= pd_:
            return 0.0
        xc = (k / 1.40) * xt
        x = min((pu - pd_) / pu, xc)
        return 3.16 * kv * fp * (1.0 - x / (3.0 * xc)) * math.sqrt(x * pu * 100.0 * rho)

    @staticmethod
    def cfac(k):
        return 0.03948 * math.sqrt(k * (2.0 / (k + 1.0)) ** ((k + 1.0) / (k - 1.0)))

    def avap(self, w, p1, tk, m, k, z, kb=1.0, kc=1.0):
        return w * math.sqrt(tk * z / m) / (self.cfac(k) * 0.975 * kb * kc * p1 * 100.0)

    def wvap(self, a, p1, tk, m, k, z, kb=1.0, kc=1.0):
        return a * self.cfac(k) * 0.975 * kb * kc * p1 * 100.0 / math.sqrt(tk * z / m)

    def aliq(self, q, rho, mu, p1g, pbg, kw=1.0, kc=1.0):
        base = 11.78 * q * math.sqrt((rho / 1000.0) / ((p1g - pbg) * 100.0)) / (0.65 * kw * kc)
        a = base
        for _ in range(80):
            re = 2800.0 * q * (rho / 1000.0) / (mu * math.sqrt(a))
            kv = 1.0 if re >= 1e5 else 1.0 / (0.9935 + 2.878 / re ** 0.5 + 342.75 / re ** 1.5) ** (1.0 / 1.5)
            nxt = base / kv
            if abs(nxt - a) < 1e-13:
                break
            a = nxt
        return a

    # -- fire --------------------------------------------------------------
    def lift(self, item):
        up = 0.0
        for _, r in self.g["modification_register"].iterrows():
            m = re.search(re.escape(item) + r" re-set ([\d.]+) m higher", str(r["description"]))
            if m:
                up += float(m.group(1))
        return up

    def aw(self, item):
        v = self.vessels.loc[item]
        d = float(v["diameter"])
        bot = float(v["bottom tangent"]) + self.lift(item)
        lvl = float(v["highest normal level"])
        head = 1.084 * d * d
        if v["shape"] == "vertical":
            return math.pi * d * max(0.0, min(bot + lvl, 7.6) - bot) + (head if bot < 7.6 else 0.0)
        if v["shape"] == "horizontal":
            h = min(lvl, max(0.0, 7.6 - bot))
            if h <= 0:
                return 0.0
            f = math.acos((d / 2 - h) / (d / 2)) / math.pi
            return f * (math.pi * d * float(v["T-T length"]) + 2 * head)
        c = self.cols.loc[item]
        a = 0.0
        top = min(bot + lvl, 7.6)
        if top > bot:
            a += math.pi * d * (top - bot) + head
        first = float(c["lowest tray above grade"]) + self.lift(item)
        n = int(float(c["trays"]))
        sp = float(c["spacing"])
        a += math.pi * d * float(c["tray liquid depth"]) * sum(
            1 for i in range(n) if first + i * sp <= 7.6)
        return a

    def ffac(self, item, tf):
        if item not in self.insul.index:
            return 1.0
        r = self.insul.loc[item]
        if str(r["fire resistance certificate"]).strip().lower() == "none":
            return 1.0
        return (float(r["conductivity, W/m K"]) / float(r["thickness, m"])) * (904.0 - tf) / 21000.0

    # -- credit ------------------------------------------------------------
    def set_aside(self, vid, case):
        for _, r in self.g["sis_register"].iterrows():
            if SIF_CASE.get(str(r["contingency_prevented"])) != (vid, case):
                continue
            if int(str(r["sil"]).split()[-1]) < 2:
                return False
            if float(r["proof_test_interval_months"]) > 18:
                return False
            return str(r["initiating_element"]) != SHARED.get(vid)
        return False

    # -- the table ---------------------------------------------------------
    def rows(self):
        out = []
        for vid in sorted(self.reg.index):
            setp, orif = self.now(vid)
            reg = self.reg.loc[vid]
            bp = float(reg["superimposed_back_pressure_barg"])
            bell = reg["valve_type"] == "bellows"
            kc = 0.90 if reg["rupture_disc_upstream"] == "yes" else 1.0
            best, barea = None, -1.0
            for case in str(reg["contingencies"]).split():
                if self.set_aside(vid, case):
                    continue
                p1 = setp * (1.21 if case == "fire" else 1.10) + ATM
                kb = lin(KB[:, 0], KB[:, 1], bp / p1) if (bell and bp / p1 > 0.30) else 1.0
                kw = lin(KW[:, 0], KW[:, 1], bp / setp) if (bell and bp / setp > 0.10) else 1.0
                a = self.area(vid, case, setp, p1, bp, kb, kw, kc)
                if a is not None and a > barea:
                    best, barea = case, a
            out.append((vid, best, barea, self.finding(vid, best, barea, setp, orif, bp, bell, kc)))
        return out

    def area(self, vid, case, setp, p1, bp, kb, kw, kc):
        reg = self.reg.loc[vid]
        fluid = str(reg["relieving_fluid"])
        if case == "thermal_expansion":
            b = self.g["blocked_in_sections"].set_index("valve").loc[vid]
            st, t = str(b["liquid"]), float(b["liquid_temp_C"])
            qk = 0.80 * float(b["projected_area_m2"])
            rho = self.l(st, t, "density_kg_per_m3")
            q = 3600.0 * self.l(st, t, "cubical_expansion_per_C") * qk / (
                rho * self.l(st, t, "specific_heat_kj_per_kg_K")) * 1000.0 / 60.0
            return self.aliq(q, rho, self.l(st, t, "viscosity_cp"), p1 - ATM, bp, kw, kc)
        if case == "blocked_outlet" and vid in BLOCKED_LIQUID:
            h0, b, suction, temp = self.pump()
            rho = self.l("bottoms_product", temp, "density_kg_per_m3")
            need = (p1 - (suction + ATM)) * 1e5 / (rho * 9.81)
            if need >= h0:
                return None
            q = math.sqrt((1.0 - need / h0) / b) * 1000.0 / 60.0
            return self.aliq(q, rho, self.l("bottoms_product", temp, "viscosity_cp"), p1 - ATM, bp, kw, kc)
        if case == "tube_rupture":
            e = self.exch.loc[RUPTURE[vid]]
            hi, lo = float(e["tube_design_barg"]), float(e["shell_design_barg"])
            if lo / hi >= 0.70:
                return None
            at = math.pi / 4.0 * (float(e["tube_bore_mm"]) / 1000.0) ** 2
            t = float(e["tube_inlet_temp_C"])
            rho = self.l("feed_liquid", t, "density_kg_per_m3")
            w = 3600.0 * 2 * 0.62 * at * math.sqrt(2 * rho * max(0.0, (hi + ATM) - p1) * 1e5)
            return self.aliq(w / rho * 1000.0 / 60.0, rho, self.l("feed_liquid", t, "viscosity_cp"),
                             p1 - ATM, bp, kw, kc)
        if case == "fire":
            item = str(reg["protected_item"])
            st = str(self.vessels.loc[item, "liquid held"])
            tf = self.s(st, p1, "saturation_temp_C")
            a = self.aw(item)
            if a <= 0:
                return None
            q = 43.2 * self.ffac(item, tf) * a ** 0.82
            w = 3600.0 * q / self.s(st, p1, "latent_heat_kj_per_kg")
            return self.avap(w, p1, tf + 273.15, self.s(st, p1, "vapour_molar_mass"),
                             self.s(st, p1, "vapour_k"), self.s(st, p1, "vapour_z"), kb, kc)
        m, k, z, tk = self.vap(vid, fluid, p1)
        if case == "blocked_outlet":
            w = 0.0
            for tag in str(reg["inlet_flow_tags"]).split("+"):
                col = [c for c in self.rec.columns if tag.lower().replace("-", "_") in c][0]
                w += float(self.rec[col].mean()) * (self.meter_k() if tag == "FE-4011" else 1.0)
        elif case == "control_valve_failure":
            tag, src = FEEDS[vid]
            pu = (self.pipeline if src == 72.0 and vid == "PSV-401" else src) + ATM
            st = CVSTREAM[tag]
            if st == "feed_gas":
                mu_, ku, zu = self.feed_m(), self.gk(pu), self.gz(pu)
                tu = float(self.rec["v401_temp_C"].mean()) + 273.15
            else:
                mu_, ku, zu = self.s(st, pu, "vapour_molar_mass"), self.s(st, pu, "vapour_k"), \
                    self.s(st, pu, "vapour_z")
                tu = self.s(st, pu, "saturation_temp_C") + 273.15
            c = self.cvd.loc[tag]
            w = self.cv_flow(self.cv_full(tag) / 1.156, float(c["xt"]), float(c["fp"]), ku, pu, p1,
                             pu * 1e5 * mu_ / (zu * RG * tu))
        elif case == "cooling_failure":
            name, pre = REB[vid]
            ps = float(re.search(r"([\d.]+)", str(self.exch.loc[name, "tube_side"])).group(1)) + ATM
            bot = str(self.vessels.loc[str(reg["protected_item"]), "liquid held"])
            q = self.ua(vid) * max(0.0, self.s("steam", ps, "saturation_temp_C")
                                   - self.s(bot, p1, "saturation_temp_C"))
            w = 3600.0 * q / self.s(fluid, p1, "latent_heat_kj_per_kg")
        else:
            raise ValueError(case)
        if w <= 0:
            return None
        return self.avap(w, p1, tk, m, k, z, kb, kc)

    def vap(self, vid, fluid, p1):
        if fluid == "feed_gas":
            return (self.feed_m(), self.gk(p1), self.gz(p1),
                    float(self.rec[GASTEMP[vid]].mean()) + 273.15)
        return (self.s(fluid, p1, "vapour_molar_mass"), self.s(fluid, p1, "vapour_k"),
                self.s(fluid, p1, "vapour_z"), self.s(fluid, p1, "saturation_temp_C") + 273.15)

    def finding(self, vid, case, need, setp, orif, bp, bell, kc):
        if ORIFICE[orif] < need:
            return "inadequate"
        if not bell and bp > 0.10 * setp:
            return "inadequate"
        if case in ("thermal_expansion", "tube_rupture") or (case == "blocked_outlet"
                                                             and vid in BLOCKED_LIQUID):
            return "adequate"
        reg = self.reg.loc[vid]
        p1 = setp * (1.21 if case == "fire" else 1.10) + ATM
        kb = lin(KB[:, 0], KB[:, 1], bp / p1) if (bell and bp / p1 > 0.30) else 1.0
        if case == "fire":
            st = str(self.vessels.loc[str(reg["protected_item"]), "liquid held"])
            m, k, z = self.s(st, p1, "vapour_molar_mass"), self.s(st, p1, "vapour_k"), \
                self.s(st, p1, "vapour_z")
            tk = self.s(st, p1, "saturation_temp_C") + 273.15
        else:
            m, k, z, tk = self.vap(vid, str(reg["relieving_fluid"]), p1)
        w = self.wvap(ORIFICE[orif], p1, tk, m, k, z, kb, kc)
        rho = p1 * 1e5 * m / (z * RG * tk)
        p = self.pipes.loc[vid]
        d = float(p["inlet_bore_mm"]) / 1000.0
        v = w / 3600.0 / (rho * math.pi / 4.0 * d * d)
        kt = 0.018 * float(p["inlet_developed_length_m"]) / d + 0.30 * float(p["elbows_90deg"]) \
            + 0.20 * float(p["tees_through_run"]) + 0.10 * float(p["full_bore_valves"]) \
            + 0.50 * float(p["vessel_entrances"])
        return "inadequate" if kt * rho * v * v / 2.0 / 1e5 > 0.03 * setp else "adequate"


def main():
    mod, tru = common.truth()
    tol = mod.TOL
    rows = Assessment(common.DATA).rows()
    n, notes = common.compare(rows, tru, tol)
    print("A second assessment, written separately. Area tolerance %.3f relative.\n" % tol)
    print("| valve | governing case | area, mm2 | finding | against the sealed answer |")
    print("|---|---|---|---|---|")
    for vid, case, need, verd in rows:
        rel = (need - tru[vid]["area"]) / tru[vid]["area"]
        print("| %s | %s | %.4f | %s | %s |" % (
            vid, case, need, verd, ("%+.4f" % rel) if not notes[vid] else "; ".join(notes[vid])))
    print("\n%d of %d right on the shipped records" % (n, len(tru)))

    if "--seeds" in sys.argv:
        os.environ["GEN_QUIET"] = "1"
        import gen
        tmp = tempfile.mkdtemp(prefix="rv_ind_")
        ok, worst = 0, 0.0
        try:
            for seed in SEEDS:
                out = os.path.join(tmp, "data")
                shutil.rmtree(out, ignore_errors=True)
                os.makedirs(os.path.join(out, "docs"), exist_ok=True)
                gen.main(out, seed)
                r = Assessment(out).rows()
                k, _ = common.compare(r, tru, tol)
                ok += 1 if k == len(tru) else 0
                worst = max(worst, max(abs((need - tru[v]["area"]) / tru[v]["area"])
                                       for v, _, need, _ in r))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        print("all nine right on %d of %d laboratory seeds; worst relative area %.4f"
              % (ok, len(SEEDS), worst))
    return 0


if __name__ == "__main__":
    sys.exit(main())
