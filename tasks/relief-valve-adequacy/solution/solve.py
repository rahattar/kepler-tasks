#!/usr/bin/env python3
"""Reference solution for relief-valve-adequacy.

Assesses unit 400's nine relief valves to plant standard RP-7 from the records in /app/data and writes
/app/output/relief.csv.

The work is in the Model class, one method per step, so that the authoring evidence scripts can replace a single
step and leave the rest alone.
"""
import csv
import math
import os
import re
import sys

DATA = os.environ.get("DATA_DIR", "/app/data")
OUT = os.environ.get("OUT_FILE", "/app/output/relief.csv")

# ----------------------------------------------------------------------------- constants from RP-7
ATM = 1.013
RGAS = 8314.0
KD_VAP, KD_LIQ = 0.975, 0.65
KC_DISC = 0.90
CD_TUBE = 0.62
TWO_THIRDS = 0.70
FIRE_C_DRAINED, FIRE_C_BARE = 43.2, 70.9
FIRE_H, FIRE_EXP = 7.6, 0.82
F_DARCY = 0.018
INLET_LIMIT = 0.03
CONV_BP_LIMIT = 0.10
SOLAR = 0.80
OVER_FIRE, OVER_OTHER = 0.21, 0.10
SIL_MIN, PROOF_MAX = 2, 18
K_FIT = {"elbows_90deg": 0.30, "tees_through_run": 0.20, "full_bore_valves": 0.10, "vessel_entrances": 0.50}
ORIFICE = {"D": 71.0, "E": 126.0, "F": 198.0, "G": 325.0, "H": 506.0, "J": 830.0,
           "K": 1186.0, "L": 1841.0, "M": 2323.0, "N": 2800.0, "P": 4116.0}
KB_TABLE = [(0.30, 1.00), (0.35, 0.99), (0.40, 0.97), (0.45, 0.95), (0.50, 0.93)]
KW_TABLE = [(0.10, 1.00), (0.15, 0.99), (0.20, 0.97), (0.25, 0.95), (0.30, 0.93), (0.40, 0.88)]
MW_AIR = 28.96
COMP_M = {"n2": 28.01, "co2": 44.01, "c1": 16.04, "c2": 30.07, "c3": 44.10,
          "ic4": 58.12, "nc4": 58.12, "c5plus": 72.15}

# the unit's topology, as the unit description gives it: which control valve admits fluid to which item, and
# where the stream comes from
ADMITS = {"PSV-401": ("PV-4001", "pipeline"), "PSV-407": ("PV-4071", "PSV-411"),
          "PSV-408": ("PV-4061", "PSV-406"), "PSV-409": ("PV-4021", "PSV-401")}
REBOILER = {"PSV-403": ("E-403", "c3_product", "t401"), "PSV-406": ("E-406", "c4_product", "t402")}
EXCHANGER = {"PSV-402": "E-402"}
PUMPED = {"PSV-405": "P-401"}
# the measurement each regulatory control uses, from the control table in the unit description
CONTROL_TAG = {("PSV-401", "blocked_outlet"): (), ("PSV-403", "cooling_failure"): ("PT-4031",),
               ("PSV-406", "cooling_failure"): ("PT-4061",), ("PSV-409", "control_valve_failure"): ("PT-4021",)}
PREVENTS = {"V-401 blocked outlet": ("PSV-401", "blocked_outlet"),
            "T-401 loss of overhead cooling": ("PSV-403", "cooling_failure"),
            "T-402 loss of overhead cooling": ("PSV-406", "cooling_failure"),
            "V-402 control valve failure": ("PSV-409", "control_valve_failure")}


# ----------------------------------------------------------------------------- reading the records
def _rows(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def _num(x):
    try:
        return float(str(x).strip())
    except (TypeError, ValueError):
        return None


def _md_table(text, after):
    """The first pipe table following a line that contains `after`."""
    lines = text.splitlines()
    i = next(j for j, ln in enumerate(lines) if after in ln)
    head = None
    out = []
    for ln in lines[i:]:
        if not ln.strip().startswith("|"):
            if head is not None and out:
                break
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if head is None:
            head = cells
            continue
        if set("".join(cells)) <= set("-: "):
            continue
        out.append(dict(zip(head, cells)))
    return out


def load(data=DATA):
    d = {}
    for name in ("relief_valve_register", "valve_history", "relief_piping", "control_valve_data",
                 "control_valve_trend", "operating_record", "instrument_schedule", "sis_register",
                 "exchanger_data", "fluid_properties", "gas_properties", "liquid_properties",
                 "gas_analysis", "modification_register", "pump_test_record", "pump_data",
                 "blocked_in_sections", "maintenance_log"):
        d[name] = _rows(os.path.join(data, name + ".csv"))
    for name in ("standard", "unit_400", "vessel_data", "relief_study_2019"):
        with open(os.path.join(data, "docs", name + ".md")) as f:
            d[name] = f.read()

    d["sat"] = {}
    for r in d["fluid_properties"]:
        d["sat"].setdefault(r["stream"], []).append(
            (_num(r["pressure_bara"]), _num(r["saturation_temp_C"]), _num(r["latent_heat_kj_per_kg"]),
             _num(r["vapour_molar_mass"]), _num(r["vapour_k"]), _num(r["vapour_z"]),
             _num(r["liquid_density_kg_per_m3"]), _num(r["liquid_viscosity_cp"])))
    d["gasp"] = {}
    for r in d["gas_properties"]:
        d["gasp"].setdefault(r["stream"], []).append((_num(r["pressure_bara"]), _num(r["k"]), _num(r["z"])))
    d["liq"] = {}
    for r in d["liquid_properties"]:
        d["liq"].setdefault(r["stream"], []).append(
            (_num(r["temperature_C"]), _num(r["density_kg_per_m3"]), _num(r["viscosity_cp"]),
             _num(r["cubical_expansion_per_C"]), _num(r["specific_heat_kj_per_kg_K"])))
    for t in (d["sat"], d["gasp"], d["liq"]):
        for k in t:
            t[k].sort()

    # the vessel data book
    d["vessel"] = {r["item"]: r for r in _md_table(d["vessel_data"], "| item | service |")}
    d["insul"] = {r["item"]: r for r in _md_table(d["vessel_data"], "| item | system |")}
    d["column"] = {r["column"]: r for r in _md_table(d["vessel_data"], "| column | trays |")}
    d["adjacent"] = {r["device"]: r for r in _md_table(d["unit_400"], "| device | protects |")}
    flat = re.sub(r"\s+", " ", d["unit_400"])
    d["pipeline_cap"] = float(re.search(
        r"caps the delivery pressure at the unit limit at ([\d.]+) barg", flat).group(1))
    d["drained"] = "confirmed drainage and firewater coverage over the whole unit" \
        in re.sub(r"\s+", " ", d["vessel_data"])
    return d


def interp(rows, x, col):
    if x <= rows[0][0]:
        return rows[0][col]
    if x >= rows[-1][0]:
        return rows[-1][col]
    for a, b in zip(rows, rows[1:]):
        if a[0] <= x <= b[0]:
            return a[col] + (x - a[0]) / (b[0] - a[0]) * (b[col] - a[col])
    raise ValueError(x)


# ----------------------------------------------------------------------------- the assessment
class Model(object):
    SAT_COL = {"t": 1, "latent": 2, "mw": 3, "k": 4, "z": 5, "rho_l": 6, "visc": 7}
    LIQ_COL = {"rho": 1, "visc": 2, "exp": 3, "cp": 4}

    def __init__(self, d):
        self.d = d
        self._cache = {}
        self.valves = sorted(r["valve"] for r in d["relief_valve_register"])
        self.reg = {r["valve"]: r for r in d["relief_valve_register"]}
        self.pipe = {r["valve"]: r for r in d["relief_piping"]}
        self.cvd = {r["tag"]: r for r in d["control_valve_data"]}
        self.blocked_in = {r["valve"]: r for r in d["blocked_in_sections"]}
        self.exch = {r["item"]: r for r in d["exchanger_data"]}

    # -- properties ---------------------------------------------------------
    def sat(self, stream, p_bara, what):
        return interp(self.d["sat"][stream], p_bara, self.SAT_COL[what])

    def gasp(self, stream, p_bara, what):
        return interp(self.d["gasp"][stream], p_bara, {"k": 1, "z": 2}[what])

    def liq(self, stream, t_C, what):
        return interp(self.d["liq"][stream], t_C, self.LIQ_COL[what])

    def feed_mw(self):
        """The molar mass of the feed from the most recent analysis."""
        def go():
            last = max(self.d["gas_analysis"], key=lambda r: r["sample_date"])
            return sum(_num(last[k]) * COMP_M[k] for k in COMP_M)
        return self.cached(("feed_mw",), go)

    # -- step 1: the valve as it now stands ---------------------------------
    def as_built(self, vid):
        """Set pressure and orifice: the register was issued with the plant, the shop record says what the
        valve carries now."""
        reg = self.reg[vid]
        setp, orif = _num(reg["set_pressure_barg"]), reg["orifice"]
        hist = [r for r in self.d["valve_history"] if r["valve"] == vid]
        if hist:
            last = max(hist, key=lambda r: r["work_date"])
            setp, orif = _num(last["as_left_set_barg"]), last["orifice_fitted"]
        return setp, orif

    # -- step 2: the feed meter --------------------------------------------
    def feed_factor(self):
        """FE-4011 is an orifice meter whose flow computer holds a fixed relative density. Its indication moves
        with the square root of the density ratio, so the true flow is the indication times sqrt(actual/held)."""
        row = next(r for r in self.d["instrument_schedule"] if r["tag"] == "FE-4011")
        m = re.search(r"([\d.]+)", row["flow_computer_density"])
        if not m:
            return 1.0
        return math.sqrt((self.feed_mw() / MW_AIR) / float(m.group(1)))

    def mean(self, col):
        key = ("mean", col)
        if key not in self._cache:
            vals = [_num(r[col]) for r in self.d["operating_record"]]
            self._cache[key] = sum(vals) / len(vals)
        return self._cache[key]

    def cached(self, key, fn):
        if key not in self._cache:
            self._cache[key] = fn()
        return self._cache[key]

    def inlet_flow(self, vid):
        """The total normal inlet flow to the protected item, kg/h, as the unit's meters show it, corrected."""
        tags = self.reg[vid]["inlet_flow_tags"]
        if not tags:
            return None
        cols = {r["tag"]: c for c in [None] for r in []}
        total = 0.0
        for tag in tags.split("+"):
            col = self.column_for(tag)
            w = self.mean(col)
            if tag == "FE-4011":
                w *= self.feed_factor()
            total += w
        return total

    def column_for(self, tag):
        key = tag.lower().replace("-", "_")
        for c in self.d["operating_record"][0]:
            if key in c:
                return c
        raise KeyError(tag)

    # -- step 3: what the control valves actually pass ----------------------
    def cv_rated(self, tag):
        """The coefficient at full travel, from the valve's own operating record. Each logged point gives the
        coefficient at its travel; the equal percentage characteristic refers it to full travel."""
        return self.cached(("cv_rated", tag), lambda: self._cv_rated(tag))

    def _cv_rated(self, tag):
        c = self.cvd[tag]
        r, xt, fp = _num(c["rangeability"]), _num(c["xt"]), _num(c["fp"])
        stream = self.cv_stream(tag)
        vals = []
        for row in self.d["control_valve_trend"]:
            if row["tag"] != tag:
                continue
            p_up, p_dn = _num(row["upstream_bara"]), _num(row["downstream_bara"])
            h = _num(row["travel_pct"]) / 100.0
            w = _num(row["flow_kgh"])
            if c["flow_measurement"] == "FE-4011":
                w *= self.feed_factor()
            mw, k, z, t_K = self.upstream_state(stream, p_up, _num(row["upstream_temp_C"]))
            unit = self.valve_flow(1.0, xt, fp, k, p_up, p_dn, self.gas_density(p_up, t_K, mw, z))
            if unit <= 0.0:
                continue
            vals.append((w / unit) * 1.156 / r ** (h - 1.0))
        return sum(vals) / len(vals)

    def cv_stream(self, tag):
        """The stream each control valve passes, from the unit description and the register."""
        return {"PV-4001": "feed_gas", "PV-4021": "feed_gas", "PV-4031": "c2_overhead",
                "PV-4061": "c4_product", "PV-4071": "c3_product"}[tag]

    def upstream_state(self, stream, p_bara, t_C):
        if stream == "feed_gas":
            return self.feed_mw(), self.gasp(stream, p_bara, "k"), self.gasp(stream, p_bara, "z"), t_C + 273.15
        return (self.sat(stream, p_bara, "mw"), self.sat(stream, p_bara, "k"),
                self.sat(stream, p_bara, "z"), self.sat(stream, p_bara, "t") + 273.15)

    # -- step 4: the reboilers ---------------------------------------------
    def reb_ua(self, vid):
        """The coefficient-area the reboiler has now, day by day from the operating record."""
        return self.cached(("reb_ua", vid), lambda: self._reb_ua(vid))

    def _reb_ua(self, vid):
        name, _, prefix = REBOILER[vid]
        pcol = "%s_steam_barg" % name.lower().replace("-", "_").replace("e_", "e")
        pcol = "e%s_steam_barg" % name.split("-")[1]
        wcol = "e%s_steam_kgh" % name.split("-")[1]
        tcol = "%s_bottoms_C" % prefix
        vals = []
        for r in self.d["operating_record"]:
            p = _num(r[pcol]) + ATM
            q = _num(r[wcol]) * self.sat("steam", p, "latent") / 3600.0
            dt = self.sat("steam", p, "t") - _num(r[tcol])
            if dt > 0:
                vals.append(q / dt)
        return sum(vals) / len(vals)

    def steam_supply_barg(self, vid):
        """The header the reboiler is supplied from, from the exchanger data."""
        name = REBOILER[vid][0]
        return _num(re.search(r"([\d.]+)", self.exch[name]["tube_side"]).group(1))

    # -- step 5: the pump --------------------------------------------------
    def pump_curve(self, vid):
        """The head curve from the latest performance test, h = h0 (1 - b q^2), with b from the data sheet."""
        name = PUMPED[vid]
        sheet = next(r for r in self.d["pump_data"] if r["pump"] == name)
        b = (1.0 - _num(sheet["rated_head_m"]) / _num(sheet["data_sheet_shutoff_head_m"])) \
            / _num(sheet["rated_flow_m3h"]) ** 2
        tests = [r for r in self.d["pump_test_record"] if r["pump"] == name]
        last = max(r["test_date"] for r in tests)
        pts = [(_num(r["flow_m3h"]), _num(r["head_m"])) for r in tests if r["test_date"] == last]
        num = sum(h * (1.0 - b * q * q) for q, h in pts)
        den = sum((1.0 - b * q * q) ** 2 for q in [p[0] for p in pts])
        return num / den, b, float(sheet["normal_suction_pressure_barg"])

    # -- step 6: geometry ---------------------------------------------------
    def raised(self, item):
        """Elevation changes since the vessel data book was issued."""
        total = 0.0
        for r in self.d["modification_register"]:
            m = re.search(r"%s re-set ([\d.]+) m higher" % re.escape(item), r["description"])
            if m:
                total += float(m.group(1))
        return total

    def wetted_area(self, item):
        v = self.d["vessel"][item]
        d = _num(v["diameter"])
        bottom = _num(v["bottom tangent"]) + self.raised(item)
        level = _num(v["highest normal level"])
        head = 1.084 * d * d
        shape = v["shape"]
        if shape == "vertical":
            h = max(0.0, min(bottom + level, FIRE_H) - bottom)
            return math.pi * d * h + (head if bottom < FIRE_H else 0.0)
        if shape == "horizontal":
            lv = min(level, max(0.0, FIRE_H - bottom))
            if lv <= 0.0:
                return 0.0
            frac = math.acos((d / 2.0 - lv) / (d / 2.0)) / math.pi
            return math.pi * d * _num(v["T-T length"]) * frac + 2 * head * frac
        c = self.d["column"][item]
        a = 0.0
        top = min(bottom + level, FIRE_H)
        if top > bottom:
            a += math.pi * d * (top - bottom) + head
        first = _num(c["lowest tray above grade"]) + self.raised(item)
        for i in range(int(_num(c["trays"]))):
            if first + i * _num(c["spacing"]) <= FIRE_H:
                a += math.pi * d * _num(c["tray liquid depth"])
        return a

    def f_factor(self, item, t_relief_C):
        ins = self.d["insul"].get(item)
        if not ins or ins["fire resistance certificate"].strip().lower() == "none":
            return 1.0
        return (_num(ins["conductivity, W/m K"]) / _num(ins["thickness, m"])) \
            * (904.0 - t_relief_C) / 21000.0

    def fire_constant(self):
        return FIRE_C_DRAINED if self.d["drained"] else FIRE_C_BARE

    # -- step 7: credit for instrumented protection -------------------------
    def credited(self, vid, case):
        for r in self.d["sis_register"]:
            if PREVENTS.get(r["contingency_prevented"]) != (vid, case):
                continue
            if _num(r["sil"].split()[-1]) < SIL_MIN:
                return False
            if _num(r["proof_test_interval_months"]) > PROOF_MAX:
                return False
            return r["initiating_element"] not in CONTROL_TAG.get((vid, case), ())
        return False

    # -- sizing -------------------------------------------------------------
    def kc_factor(self, vid):
        """The combination factor: a rupture disc upstream of the valve derates it."""
        return KC_DISC if self.reg[vid]["rupture_disc_upstream"] == "yes" else 1.0

    def relieving(self, set_barg, case):
        return set_barg * (1.0 + (OVER_FIRE if case == "fire" else OVER_OTHER)) + ATM

    def c_factor(self, k):
        return 0.03948 * math.sqrt(k * (2.0 / (k + 1.0)) ** ((k + 1.0) / (k - 1.0)))

    def kb(self, ratio):
        return interp([(a, b) for a, b in KB_TABLE], ratio, 1) if ratio > KB_TABLE[0][0] else 1.0

    def kw(self, ratio):
        return interp([(a, b) for a, b in KW_TABLE], ratio, 1) if ratio > KW_TABLE[0][0] else 1.0

    def gas_density(self, p_bara, t_K, mw, z):
        return p_bara * 1.0e5 * mw / (z * RGAS * t_K)

    def valve_flow(self, kv, xt, fp, k, p_up, p_dn, rho_up):
        if p_up <= p_dn:
            return 0.0
        xc = (k / 1.40) * xt
        x = min((p_up - p_dn) / p_up, xc)
        return 3.16 * kv * fp * (1.0 - x / (3.0 * xc)) * math.sqrt(x * p_up * 100.0 * rho_up)

    def area_vapour(self, w, p1, t_K, mw, k, z, kb_=1.0, kc=1.0):
        return w / (self.c_factor(k) * KD_VAP * kb_ * kc * p1 * 100.0) * math.sqrt(t_K * z / mw)

    def cap_vapour(self, a, p1, t_K, mw, k, z, kb_=1.0, kc=1.0):
        return a * self.c_factor(k) * KD_VAP * kb_ * kc * p1 * 100.0 / math.sqrt(t_K * z / mw)

    def kv_visc(self, a, q, rho, visc):
        if a <= 0.0:
            return 1.0
        re = 2800.0 * q * (rho / 1000.0) / (visc * math.sqrt(a))
        if re >= 1.0e5:
            return 1.0
        return 1.0 / (0.9935 + 2.878 / re ** 0.5 + 342.75 / re ** 1.5) ** (1.0 / 1.5)

    def area_liquid(self, q, rho, visc, p1_barg, pb_barg, kw_=1.0, kc=1.0):
        def once(kv):
            return 11.78 * q * math.sqrt((rho / 1000.0) / ((p1_barg - pb_barg) * 100.0)) / (KD_LIQ * kw_ * kc * kv)
        a = once(1.0)
        for _ in range(60):
            new = once(self.kv_visc(a, q, rho, visc))
            if abs(new - a) < 1.0e-12:
                return new
            a = new
        return a

    # -- the relieving fluid ------------------------------------------------
    def relief_temp(self, vid):
        """The relieving temperature of a non-condensing gas is the item's own temperature."""
        col = {"PSV-401": "v401_temp_C", "PSV-409": "v402_temp_C"}[vid]
        return self.mean(col)

    def vapour_state(self, vid, p1):
        fluid = self.reg[vid]["relieving_fluid"]
        if fluid == "feed_gas":
            return (self.feed_mw(), self.gasp(fluid, p1, "k"), self.gasp(fluid, p1, "z"),
                    self.relief_temp(vid) + 273.15)
        return (self.sat(fluid, p1, "mw"), self.sat(fluid, p1, "k"), self.sat(fluid, p1, "z"),
                self.sat(fluid, p1, "t") + 273.15)

    # -- the cases ----------------------------------------------------------
    def case_area(self, vid, case):
        if self.credited(vid, case):
            return None
        reg = self.reg[vid]
        setp, orif = self.as_built(vid)
        p1 = self.relieving(setp, case)
        kc = self.kc_factor(vid)
        bellows = reg["valve_type"] == "bellows"
        bp = _num(reg["superimposed_back_pressure_barg"])
        kw_ = self.kw(bp / setp) if bellows else 1.0
        kb_ = self.kb(bp / p1) if bellows else 1.0

        if case == "thermal_expansion":
            s = self.blocked_in[vid]
            stream, t = s["liquid"], _num(s["liquid_temp_C"])
            q_kw = SOLAR * _num(s["projected_area_m2"])
            rho, cp = self.liq(stream, t, "rho"), self.liq(stream, t, "cp")
            q = 3600.0 * self.liq(stream, t, "exp") * q_kw / (rho * cp) * 1000.0 / 60.0
            return self.area_liquid(q, rho, self.liq(stream, t, "visc"), p1 - ATM, bp, kw_, kc)

        if case == "blocked_outlet" and vid in PUMPED:
            shutoff, b, suction = self.pump_curve(vid)
            rho = self.liq("bottoms_product", _num(
                next(r for r in self.d["pump_data"] if r["pump"] == PUMPED[vid])["temperature_C"]), "rho")
            h_req = (p1 - (suction + ATM)) * 1.0e5 / (rho * 9.81)
            if h_req >= shutoff:
                return None
            q = math.sqrt((1.0 - h_req / shutoff) / b) * 1000.0 / 60.0
            t = _num(next(r for r in self.d["pump_data"] if r["pump"] == PUMPED[vid])["temperature_C"])
            return self.area_liquid(q, rho, self.liq("bottoms_product", t, "visc"), p1 - ATM, bp, kw_, kc)

        if case == "tube_rupture":
            e = self.exch[EXCHANGER[vid]]
            hi, lo = _num(e["tube_design_barg"]), _num(e["shell_design_barg"])
            if lo / hi >= TWO_THIRDS:
                return None
            at = math.pi / 4.0 * (_num(e["tube_bore_mm"]) / 1000.0) ** 2
            dp = max(0.0, (hi + ATM) - p1) * 1.0e5
            stream = "feed_liquid"
            t = _num(e["tube_inlet_temp_C"])
            rho = self.liq(stream, t, "rho")
            w = 3600.0 * 2.0 * CD_TUBE * at * math.sqrt(2.0 * rho * dp)
            return self.area_liquid(w / rho * 1000.0 / 60.0, rho, self.liq(stream, t, "visc"),
                                    p1 - ATM, bp, kw_, kc)

        if case == "fire":
            item = reg["protected_item"]
            stream = self.fire_stream(vid)
            t_rel = self.sat(stream, p1, "t")
            aw = self.wetted_area(item)
            if aw <= 0.0:
                return None
            q = self.fire_constant() * self.f_factor(item, t_rel) * aw ** FIRE_EXP
            w = 3600.0 * q / self.sat(stream, p1, "latent")
            mw, k, z = (self.sat(stream, p1, "mw"), self.sat(stream, p1, "k"), self.sat(stream, p1, "z"))
            return self.area_vapour(w, p1, t_rel + 273.15, mw, k, z, kb_, kc)

        if case == "blocked_outlet":
            w = self.inlet_flow(vid)
        elif case == "control_valve_failure":
            tag, src = ADMITS[vid]
            p_up = (self.d["pipeline_cap"] if src == "pipeline" else
                    _num(self.reg[src]["set_pressure_barg"]) if src in self.reg else
                    _num(self.d["adjacent"][src]["set, barg"])) + ATM
            stream = self.cv_stream(tag)
            t_up = self.mean("v401_temp_C") if stream == "feed_gas" else None
            mw, k, z, t_K = self.upstream_state(stream, p_up, t_up)
            c = self.cvd[tag]
            w = self.valve_flow(self.cv_rated(tag) / 1.156, _num(c["xt"]), _num(c["fp"]), k,
                                p_up, p1, self.gas_density(p_up, t_K, mw, z))
        elif case == "cooling_failure":
            name, bot_stream, _ = REBOILER[vid]
            ps = self.steam_supply_barg(vid) + ATM
            ua = self.reb_ua(vid)
            q = ua * max(0.0, self.sat("steam", ps, "t") - self.sat(bot_stream, p1, "t"))
            w = 3600.0 * q / self.sat(reg["relieving_fluid"], p1, "latent")
        else:
            raise ValueError(case)
        if w is None or w <= 0.0:
            return None
        mw, k, z, t_K = self.vapour_state(vid, p1)
        return self.area_vapour(w, p1, t_K, mw, k, z, kb_, kc)

    def fire_stream(self, vid):
        """The liquid the item holds, which the vessel data book names."""
        return self.d["vessel"][self.reg[vid]["protected_item"]]["liquid held"]

    # -- the finding --------------------------------------------------------
    def governing(self, vid):
        best, best_a = None, -1.0
        for case in self.reg[vid]["contingencies"].split():
            a = self.case_area(vid, case)
            if a is not None and a > best_a:
                best, best_a = case, a
        return best, best_a

    def vapour_case(self, vid, case):
        """Whether the contingency relieves vapour. RP-7 section 16 applies to vapour service only."""
        if case in ("thermal_expansion", "tube_rupture"):
            return False
        if case == "blocked_outlet" and vid in PUMPED:
            return False
        return True

    def inlet_drop(self, vid, case):
        reg = self.reg[vid]
        setp, orif = self.as_built(vid)
        if not self.vapour_case(vid, case):
            return 0.0
        p1 = self.relieving(setp, case)
        bp = _num(reg["superimposed_back_pressure_barg"])
        bellows = reg["valve_type"] == "bellows"
        kb_ = self.kb(bp / p1) if bellows else 1.0
        kc = self.kc_factor(vid)
        if case == "fire":
            stream = self.fire_stream(vid)
            mw, k, z = (self.sat(stream, p1, "mw"), self.sat(stream, p1, "k"), self.sat(stream, p1, "z"))
            t_K = self.sat(stream, p1, "t") + 273.15
        else:
            mw, k, z, t_K = self.vapour_state(vid, p1)
        w = self.cap_vapour(ORIFICE[orif], p1, t_K, mw, k, z, kb_, kc)
        rho = self.gas_density(p1, t_K, mw, z)
        p = self.pipe[vid]
        d = _num(p["inlet_bore_mm"]) / 1000.0
        v = w / 3600.0 / (rho * math.pi / 4.0 * d * d)
        kt = F_DARCY * _num(p["inlet_developed_length_m"]) / d + sum(K_FIT[f] * _num(p[f]) for f in K_FIT)
        return kt * rho * v * v / 2.0 / 1.0e5

    def verdict(self, vid, case, need):
        reg = self.reg[vid]
        setp, orif = self.as_built(vid)
        if ORIFICE[orif] < need:
            return "inadequate"
        if reg["valve_type"] == "conventional" and \
                _num(reg["superimposed_back_pressure_barg"]) > CONV_BP_LIMIT * setp:
            return "inadequate"
        if self.inlet_drop(vid, case) > INLET_LIMIT * setp:
            return "inadequate"
        return "adequate"

    def sheet(self):
        out = []
        for vid in self.valves:
            case, need = self.governing(vid)
            out.append((vid, case, need, self.verdict(vid, case, need)))
        return out


def main():
    m = Model(load())
    rows = m.sheet()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["valve", "governing_case", "required_area_mm2", "verdict"])
        for vid, case, need, verd in rows:
            w.writerow([vid, case, "%.4f" % need, verd])
    for vid, case, need, verd in rows:
        print("%s %-22s %12.4f  %s" % (vid, case, need, verd))
    return 0


if __name__ == "__main__":
    sys.exit(main())
