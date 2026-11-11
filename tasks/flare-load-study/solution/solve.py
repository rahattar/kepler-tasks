#!/usr/bin/env python3
"""Reference solution for flare-load-study.

Works out, for each contingency RP-7 names, which of unit 400's relief devices discharge, the load they put on
the flare header together, and the pressure that load raises at the header's inlet. Reads /app/data and the field reports of the tests it orders itself, and
writes /app/output/flare_load.csv.

The work is in the Study class, one method per step, so that the authoring evidence scripts can replace a single
step and leave the rest of the study alone.
"""
import csv
import math
import os
import re
import subprocess
import sys

DATA = os.environ.get("DATA_DIR", "/app/data")
REPORTS = os.environ.get("REPORT_DIR", "/app/field_reports")
OUT = os.environ.get("OUT_FILE", "/app/output/flare_load.csv")
SIZING_OUT = os.environ.get("SIZING_FILE", "/app/output/tip_sizing.csv")
SETTLE = 1.0e-4            # bar: the sweeps stop when no tie-in pressure moves by more than this
SWEEP_CAP = 500

# ----------------------------------------------------------------------------- constants from RP-7
ATM = 1.013
RGAS = 8314.0
FIRE_DRAINED, FIRE_BARE = 43.2, 70.9
FIRE_H, FIRE_EXP = 7.6, 0.82
F_DARCY = 0.018
OVER_FIRE, OVER_OTHER = 0.21, 0.10
SIL_MIN, PROOF_MAX = 2, 18
K_FIT = {"90 degree elbow": 0.30, "tee, flow through the run": 0.20}
MW_AIR = 28.96
PURGE_MW = 28.01            # nitrogen, what the tip back pressure test is run on

# the unit's topology, as the unit description and the drive schedule give it
ADMITS = {"PSV-401": ("PV-4001", "pipeline"), "PSV-407": ("PV-4071", "PSV-411"),
          "PSV-409": ("PV-4021", "PSV-401")}
REBOILER = {"PSV-403": ("E-403", "t401"), "PSV-406": ("E-406", "t402")}
CONDENSER = {"T-401": "E-404", "T-402": "E-407"}
PUMPED = {"PSV-405": "P-401"}
PUMP_DISCHARGE_VALVE = "FV-4051"
CVSTREAM = {"PV-4001": "feed_gas", "PV-4021": "feed_gas", "PV-4031": "c2_overhead",
            "PV-4061": "c4_product", "PV-4071": "c3_product"}
GASTEMP = {"PSV-401": "v401_temp_C", "PSV-409": "v402_temp_C"}
PREVENTS = {"V-401 control valve failure": ("PSV-401", "control_valve_failure"),
            "T-401 loss of overhead cooling": ("PSV-403", "cooling_failure"),
            "T-402 loss of overhead cooling": ("PSV-406", "cooling_failure"),
            "V-402 control valve failure": ("PSV-409", "control_valve_failure")}
AIR_COMPRESSOR, SIS = "K-901", "SIS"


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
    head, out = None, []
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


def _report_table(path):
    """A crew report: the commented first line, then a CSV of what was measured."""
    rows = []
    with open(path) as handle:
        head = None
        for line in handle:
            if line.startswith("#") or not line.strip():
                continue
            cells = [c.strip() for c in line.rstrip("\n").split(",")]
            if head is None:
                head = cells
            else:
                rows.append(dict(zip(head, cells)))
    return rows


def field_reports(reports=REPORTS):
    """What the crew has measured so far, keyed by the test that measured it."""
    out = {}
    if not os.path.isdir(reports):
        return out
    for name in sorted(os.listdir(reports)):
        m = re.match(r"order_\d+_(.+)\.csv$", name)
        if m:
            out[m.group(1).replace("_", "-")] = _report_table(os.path.join(reports, name))
    return out


def order(tests, reports=REPORTS):
    """Place the orders this study needs, skipping any the crew has already run."""
    have = field_reports(reports)
    for test in tests:
        if test not in have:
            subprocess.run(["fieldtest", test], check=True)
    return field_reports(reports)


def load(data=DATA):
    d = {}
    for name in ("relief_valve_register", "valve_history", "control_valve_data", "control_valve_trend",
                 "operating_record", "instrument_schedule", "sis_register", "exchanger_data",
                 "fluid_properties", "gas_properties", "liquid_properties", "gas_analysis",
                 "modification_register", "pump_test_record", "pump_data", "fire_zones",
                 "drive_schedule", "maintenance_log", "flare_tie_ins", "component_properties"):
        d[name] = _rows(os.path.join(data, name + ".csv"))
    for name in ("standard", "unit_400", "vessel_data", "flare_system", "flare_load_study_2019"):
        with open(os.path.join(data, "docs", name + ".md")) as f:
            d[name] = f.read()

    d["sat"], d["gasp"], d["liq"] = {}, {}, {}
    for r in d["fluid_properties"]:
        d["sat"].setdefault(r["stream"], []).append(
            (_num(r["pressure_bara"]), _num(r["saturation_temp_C"]), _num(r["latent_heat_kj_per_kg"]),
             _num(r["vapour_molar_mass"]), _num(r["vapour_k"]), _num(r["vapour_z"]),
             _num(r["liquid_density_kg_per_m3"]), _num(r["liquid_viscosity_cp"])))
    for r in d["gas_properties"]:
        d["gasp"].setdefault(r["stream"], []).append((_num(r["pressure_bara"]), _num(r["k"]), _num(r["z"])))
    for r in d["liquid_properties"]:
        d["liq"].setdefault(r["stream"], []).append(
            (_num(r["temperature_C"]), _num(r["density_kg_per_m3"]), _num(r["viscosity_cp"]),
             _num(r["cubical_expansion_per_C"]), _num(r["specific_heat_kj_per_kg_K"])))
    for table in (d["sat"], d["gasp"], d["liq"]):
        for k in table:
            table[k].sort()

    d["vessel"] = {r["item"]: r for r in _md_table(d["vessel_data"], "| item | service |")}
    d["insul"] = {r["item"]: r for r in _md_table(d["vessel_data"], "| item | system |")}
    d["column"] = {r["column"]: r for r in _md_table(d["vessel_data"], "| column | trays |")}
    d["adjacent"] = {r["device"]: r for r in _md_table(d["unit_400"], "| device | protects |")}
    d["header"] = {r["item"]: r["value"] for r in _md_table(d["flare_system"], "## The header")}
    d["comp_m"] = {r["component"]: _num(r["molar_mass_kg_per_kmol"]) for r in d["component_properties"]}
    # the fittings keep their order along the header, so they are a list, not a dict: three are tees
    d["fitting"] = [(r["fitting"], _num(r["distance from the stack base, m"]))
                    for r in _md_table(d["flare_system"], "## Fittings")]
    d["tip"] = {r["item"]: r["value"] for r in _md_table(d["flare_system"], "## The stack tip")}
    flat = re.sub(r"\s+", " ", d["unit_400"])
    d["pipeline_cap"] = float(re.search(r"at the unit limit at ([\d.]+) barg", flat).group(1))
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


def _mm(text):
    return float(re.search(r"([\d.]+)", text).group(1))


# ----------------------------------------------------------------------------- the study
class Study(object):
    SAT_COL = {"t": 1, "latent": 2, "mw": 3, "k": 4, "z": 5, "rho_l": 6, "visc": 7}
    LIQ_COL = {"rho": 1, "visc": 2, "exp": 3, "cp": 4}

    def __init__(self, d, reports=None):
        self.reports = {} if reports is None else reports
        self.back = {}                 # what each device stands against while the system is being converged
        self.d = d
        self._cache = {}
        self.reg = {r["valve"]: r for r in d["relief_valve_register"]}
        self.cvd = {r["tag"]: r for r in d["control_valve_data"]}
        self.exch = {r["item"]: r for r in d["exchanger_data"]}
        self.driven = {r["tag"]: r for r in d["drive_schedule"]}
        self.zones = {r["zone"]: r["items"].split() for r in d["fire_zones"]}
        self.contingencies = ["power_failure", "cooling_water_failure", "instrument_air_failure"] + \
            ["fire_zone_%s" % z.lower() for z in sorted(self.zones)]

    def cached(self, key, fn):
        if key not in self._cache:
            self._cache[key] = fn()
        return self._cache[key]

    # -- properties ---------------------------------------------------------
    def sat(self, stream, p, what):
        return interp(self.d["sat"][stream], p, self.SAT_COL[what])

    def gasp(self, stream, p, what):
        return interp(self.d["gasp"][stream], p, {"k": 1, "z": 2}[what])

    def liq(self, stream, t, what):
        return interp(self.d["liq"][stream], t, self.LIQ_COL[what])

    def mean(self, col):
        return self.cached(("mean", col), lambda: sum(
            _num(r[col]) for r in self.d["operating_record"]) / len(self.d["operating_record"]))

    def feed_mw(self):
        def go():
            last = max(self.d["gas_analysis"], key=lambda r: r["sample_date"])
            return sum(_num(last[k]) * self.d["comp_m"][k] for k in self.d["comp_m"])
        return self.cached(("feed_mw",), go)

    def feed_factor(self):
        """FE-4011's flow computer holds a fixed relative density, so its indication moves with the square root
        of the density ratio."""
        row = next(r for r in self.d["instrument_schedule"] if r["tag"] == "FE-4011")
        m = re.search(r"([\d.]+)", row["flow_computer_density"])
        return math.sqrt((self.feed_mw() / MW_AIR) / float(m.group(1))) if m else 1.0

    # -- the device as it stands -------------------------------------------
    def set_pressure(self, vid):
        """The valve's present setting: the register was issued with the plant, the shop record says what the
        valve now carries."""
        hist = [r for r in self.d["valve_history"] if r["valve"] == vid]
        if hist:
            return _num(max(hist, key=lambda r: r["work_date"])["as_left_set_barg"])
        return _num(self.reg[vid]["set_pressure_barg"])

    def last_work(self, item):
        """The day of the last work the maintenance log records on the item, or None if it records none.

        Section 1: only the part of a record that describes the item in its present condition may be used, and
        this is the day that divides the two.
        """
        days = [r["date"] for r in self.d["maintenance_log"] if r["item"] == item]
        return max(days) if days else None

    def since_work(self, item, rows, column):
        """Only those rows of a record that were taken after the last work on the item."""
        cut = self.last_work(item)
        if cut is None:
            return rows
        return [r for r in rows if r[column][:10] >= cut] or rows

    def bellows(self, vid):
        """Whether the device has a balanced bonnet, which isolates it from whatever stands at its outlet."""
        return "bellows" in self.reg[vid]["bonnet"].lower()

    def felt(self, vid):
        """The built-up pressure the device stands against, zero where a bellows balances it out."""
        return 0.0 if self.bellows(vid) else self.back.get(vid, 0.0)

    def relieving(self, vid, cause):
        over = OVER_FIRE if cause == "fire" else OVER_OTHER
        return (self.set_pressure(vid) + self.felt(vid)) * (1.0 + over) + ATM

    # -- what the contingency reaches --------------------------------------
    def supply_of(self, tag):
        return self.driven[tag]["electrical_supply"]

    def air_lost(self, contingency):
        """Air goes on its own, and with the power while its compressor is on the normal supply."""
        if contingency == "instrument_air_failure":
            return True
        return contingency == "power_failure" and self.supply_of(AIR_COMPRESSOR) == "normal"

    def cooling_lost(self, item, contingency):
        cooler = CONDENSER.get(item)
        if cooler is None:
            return False
        row = self.driven[cooler]
        if contingency == "power_failure":
            return row["electrical_supply"] == "normal"
        if contingency == "cooling_water_failure":
            return "water" in row["cooling_medium"]
        return False

    def pump_runs(self, contingency):
        return not (contingency == "power_failure"
                    and self.supply_of(PUMPED["PSV-405"]) == "normal")

    def sis_holds(self, contingency):
        return not (contingency == "power_failure" and self.supply_of(SIS) == "normal")

    def fails_open(self, tag):
        return self.cvd[tag]["position_on_air_failure"] == "open"

    def cause_of(self, vid, contingency):
        """The cause this contingency puts at this device, or None where the device does not discharge."""
        admitted = self.reg[vid]["causes_admitted"].split()
        item = self.reg[vid]["protected_item"]
        if contingency.startswith("fire_zone_"):
            zone = contingency[-1].upper()
            if item not in self.zones.get(zone, []) or "fire" not in admitted:
                return None
            return "fire"
        if self.cooling_lost(item, contingency) and "cooling_failure" in admitted:
            return "cooling_failure"
        if self.air_lost(contingency):
            tag = ADMITS.get(vid, (None, None))[0]
            if tag and self.fails_open(tag) and "control_valve_failure" in admitted:
                return "control_valve_failure"
            if vid in PUMPED and "blocked_outlet" in admitted \
                    and not self.fails_open(PUMP_DISCHARGE_VALVE) and self.pump_runs(contingency):
                return "blocked_outlet"
        return None

    # -- credit -------------------------------------------------------------
    def controls(self, item, tag):
        """Whether a control function on this item works from that measurement.

        The instrument schedule says what each transmitter is for: a service naming the item and the word
        control is a control measurement on it, and a protective function initiated from one of those shares an
        instrument with control on the very item it protects.
        """
        for r in self.d["instrument_schedule"]:
            if r["tag"] != tag:
                continue
            service = r["service"].lower()
            return item.lower() in service and "control" in service
        return False

    def credited(self, vid, cause, contingency):
        for r in self.d["sis_register"]:
            if PREVENTS.get(r["contingency_prevented"]) != (vid, cause):
                continue
            if _num(r["sil"].split()[-1]) < SIL_MIN:
                return False
            if _num(r["proof_test_interval_months"]) > PROOF_MAX:
                return False
            if self.controls(self.reg[vid]["protected_item"], r["initiating_element"]):
                return False
            return self.sis_holds(contingency)
        return False

    # -- the identified quantities ------------------------------------------
    def cv_rated(self, tag):
        return self.cached(("cv", tag), lambda: self._cv_rated(tag))

    def _cv_rated(self, tag):
        c = self.cvd[tag]
        r, xt, fp = _num(c["rangeability"]), _num(c["xt"]), _num(c["fp"])
        stream = CVSTREAM[tag]
        vals = []
        # only the readings taken since the valve's trim was last worked on describe the valve in service
        for row in self.since_work(tag, [r for r in self.d["control_valve_trend"] if r["tag"] == tag],
                                   "timestamp"):
            p_up, p_dn = _num(row["upstream_bara"]), _num(row["downstream_bara"])
            w = _num(row["flow_kgh"])
            if c["flow_measurement"] == "FE-4011":
                w *= self.feed_factor()
            mw, k, z, t_K = self.upstream(stream, p_up, _num(row["upstream_temp_C"]))
            unit = self.valve_flow(1.0, xt, fp, k, p_up, p_dn, self.density(p_up, t_K, mw, z))
            if unit > 0.0:
                vals.append((w / unit) * 1.156 / r ** (_num(row["travel_pct"]) / 100.0 - 1.0))
        return sum(vals) / len(vals)

    def reb_ua(self, vid):
        return self.cached(("ua", vid), lambda: self._reb_ua(vid))

    def _reb_ua(self, vid):
        name, prefix = REBOILER[vid]
        n = name.split("-")[1]
        vals = []
        # and only the days since the exchanger was last worked on describe the exchanger in service
        for r in self.since_work(name, self.d["operating_record"], "date"):
            p = _num(r["e%s_steam_barg" % n]) + ATM
            q = _num(r["e%s_steam_kgh" % n]) * self.sat("steam", p, "latent") / 3600.0
            dt = self.sat("steam", p, "t") - _num(r["%s_bottoms_C" % prefix])
            if dt > 0:
                vals.append(q / dt)
        return sum(vals) / len(vals)

    def steam_supply_barg(self, vid):
        return _mm(self.exch[REBOILER[vid][0]]["tube_side"])

    def pump_curve(self, vid):
        """The head curve of the pump as it now stands, h = h0 (1 - b q^2), b from the data sheet.

        The record's last performance test was made before the rotating element was renewed, so it describes a
        different pump; the crew's test is the one that describes this one.
        """
        name = PUMPED[vid]
        sheet = next(r for r in self.d["pump_data"] if r["pump"] == name)
        b = (1.0 - _num(sheet["rated_head_m"]) / _num(sheet["data_sheet_shutoff_head_m"])) \
            / _num(sheet["rated_flow_m3h"]) ** 2
        fresh = self.reports.get("pump-shutoff")
        if fresh:
            pts = [(_num(r["flow_m3h"]), _num(r["head_m"])) for r in fresh]
        else:
            tests = [r for r in self.d["pump_test_record"] if r["pump"] == name]
            last = max(r["test_date"] for r in tests)
            pts = [(_num(r["flow_m3h"]), _num(r["head_m"])) for r in tests if r["test_date"] == last]
        num = sum(h * (1.0 - b * q * q) for q, h in pts)
        den = sum((1.0 - b * q * q) ** 2 for q, _ in pts)
        return num / den, b, _num(sheet["normal_suction_pressure_barg"]), _num(sheet["temperature_C"])

    # -- geometry -----------------------------------------------------------
    def raised(self, item):
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
        if v["shape"] == "vertical":
            h = max(0.0, min(bottom + level, FIRE_H) - bottom)
            return math.pi * d * h + (head if bottom < FIRE_H else 0.0)
        if v["shape"] == "horizontal":
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

    def f_factor(self, item, t_relief):
        ins = self.d["insul"].get(item)
        if not ins or ins["fire resistance certificate"].strip().lower() == "none":
            return 1.0
        return (_num(ins["conductivity, W/m K"]) / _num(ins["thickness, m"])) * (904.0 - t_relief) / 21000.0

    def fire_constant(self):
        return FIRE_DRAINED if self.d["drained"] else FIRE_BARE

    # -- flow relations -----------------------------------------------------
    def density(self, p_bara, t_K, mw, z):
        return p_bara * 1.0e5 * mw / (z * RGAS * t_K)

    def valve_flow(self, kv, xt, fp, k, p_up, p_dn, rho_up):
        if p_up <= p_dn:
            return 0.0
        xc = (k / 1.40) * xt
        x = min((p_up - p_dn) / p_up, xc)
        return 3.16 * kv * fp * (1.0 - x / (3.0 * xc)) * math.sqrt(x * p_up * 100.0 * rho_up)

    def upstream(self, stream, p_bara, t_C):
        if stream == "feed_gas":
            return self.feed_mw(), self.gasp(stream, p_bara, "k"), self.gasp(stream, p_bara, "z"), t_C + 273.15
        return (self.sat(stream, p_bara, "mw"), self.sat(stream, p_bara, "k"),
                self.sat(stream, p_bara, "z"), self.sat(stream, p_bara, "t") + 273.15)

    def vapour_state(self, vid, p1):
        fluid = self.reg[vid]["relieving_fluid"]
        if fluid == "feed_gas":
            return (self.feed_mw(), self.gasp(fluid, p1, "k"), self.gasp(fluid, p1, "z"),
                    self.mean(GASTEMP[vid]) + 273.15)
        return (self.sat(fluid, p1, "mw"), self.sat(fluid, p1, "k"), self.sat(fluid, p1, "z"),
                self.sat(fluid, p1, "t") + 273.15)

    # -- the rate under each cause ------------------------------------------
    def rate(self, vid, cause):
        """(mass flow kg/h, molar mass, k, Z, temperature K), or None where the cause cannot be realised."""
        p1 = self.relieving(vid, cause)
        if cause == "fire":
            item = self.reg[vid]["protected_item"]
            stream = self.d["vessel"][item]["liquid held"]
            t_rel = self.sat(stream, p1, "t")
            aw = self.wetted_area(item)
            if aw <= 0.0:
                return None
            q = self.fire_constant() * self.f_factor(item, t_rel) * aw ** FIRE_EXP
            w = 3600.0 * q / self.sat(stream, p1, "latent")
            return (w, self.sat(stream, p1, "mw"), self.sat(stream, p1, "k"),
                    self.sat(stream, p1, "z"), t_rel + 273.15)
        if cause == "cooling_failure":
            bot = self.d["vessel"][self.reg[vid]["protected_item"]]["liquid held"]
            ps = self.steam_supply_barg(vid) + ATM
            q = self.reb_ua(vid) * max(0.0, self.sat("steam", ps, "t") - self.sat(bot, p1, "t"))
            w = 3600.0 * q / self.sat(bot, p1, "latent")
            return (w,) + self.vapour_state(vid, p1)
        if cause == "control_valve_failure":
            tag, src = ADMITS[vid]
            p_up = (self.d["pipeline_cap"] if src == "pipeline" else
                    _num(self.reg[src]["set_pressure_barg"]) if src in self.reg else
                    _num(self.d["adjacent"][src]["set, barg"])) + ATM
            stream = CVSTREAM[tag]
            t_up = self.mean("v401_temp_C") if stream == "feed_gas" else None
            mw, k, z, t_K = self.upstream(stream, p_up, t_up)
            c = self.cvd[tag]
            w = self.valve_flow(self.cv_rated(tag) / 1.156, _num(c["xt"]), _num(c["fp"]), k,
                                p_up, p1, self.density(p_up, t_K, mw, z))
            return (w,) + self.vapour_state(vid, p1)
        if cause == "blocked_outlet":
            shutoff, b, suction, temp = self.pump_curve(vid)
            rho = self.liq("bottoms_product", temp, "rho")
            need = (p1 - (suction + ATM)) * 1.0e5 / (rho * 9.81)
            if need >= shutoff:
                return None
            q = math.sqrt((1.0 - need / shutoff) / b)
            # a liquid enters the mixture on the molar mass of what it passes, k 1.05 and Z 1, at its
            # pumped temperature, as section 5 directs
            return (q * rho, self.sat("bottoms_product", p1, "mw"), 1.05, 1.0, temp + 273.15)
        raise ValueError(cause)

    # -- the study ----------------------------------------------------------
    def discharging(self, contingency):
        out = {}
        for vid in sorted(self.reg):
            cause = self.cause_of(vid, contingency)
            if cause is None or self.credited(vid, cause, contingency):
                continue
            got = self.rate(vid, cause)
            if got is None or got[0] <= 0.0:
                continue
            out[vid] = got
        return out

    def mixed(self, parts):
        total = sum(v[0] for v in parts.values())
        moles = sum(v[0] / v[1] for v in parts.values())
        k = sum(v[0] * v[2] for v in parts.values()) / total
        z = sum(v[0] * v[3] for v in parts.values()) / total
        t = sum(v[0] * v[4] for v in parts.values()) / total
        return total, total / moles, k, z, t

    def tip_k(self):
        """The coefficient of the tip as installed, from the crew's back pressure test.

        RP-7 takes the tip's loss with the density of what flows at atmospheric pressure, so the coefficient is
        the slope of the measured rise against rho v^2 / 2, by least squares through the origin. The 1.80 in the
        2019 study belongs to the tip this one replaced and is not used.
        """
        def go():
            rows = self.reports.get("tip-backpressure")
            if not rows:
                raise SystemExit("the tip back pressure test has not been run: its coefficient is on no record")
            d = _mm(self.d["tip"]["bore"]) / 1000.0
            a = math.pi / 4.0 * d * d
            num = den = 0.0
            for r in rows:
                w = _num(r["nitrogen_flow_kg_per_h"])
                t_K = _num(r["nitrogen_temp_C"]) + 273.15
                rho = self.density(ATM, t_K, PURGE_MW, 1.0)
                x = rho * (w / 3600.0 / (rho * a)) ** 2 / 2.0 / 1.0e5
                num += _num(r["stack_base_gauge_bar"]) * x
                den += x * x
            return num / den
        return self.cached(("tip_k",), go)

    def tie_in(self, device):
        """Where the device ties into the header: the isometrics, moved on by any later modification."""
        row = next(r for r in self.d["flare_tie_ins"] if r["device"] == device)
        x = _num(row["tie_in_m_from_stack_base"])
        for r in self.d["modification_register"]:
            m = re.search(r"%s\b.*?tie-in on the main header from [\d.]+ m to ([\d.]+) m"
                          % re.escape(device), re.sub(r"\s+", " ", r["description"]))
            if m:
                x = float(m.group(1))
        return x

    def header_profile(self, parts, tip_mm=None):
        """(pressure at the blinded end, {device: the pressure reached at its own tie-in}), bar gauge."""
        at = {}
        if not parts:
            return 0.0, {}
        total, mw, k, z, t_K = self.mixed(parts)
        d_tip = (_mm(self.d["tip"]["bore"]) if tip_mm is None else tip_mm) / 1000.0
        rho = self.density(ATM, t_K, mw, z)
        v = total / 3600.0 / (rho * math.pi / 4.0 * d_tip * d_tip)
        p = ATM + self.tip_k() * rho * v * v / 2.0 / 1.0e5
        d = _mm(self.d["header"]["bore"]) / 1000.0
        a = math.pi / 4.0 * d * d
        tie = {r["device"]: self.tie_in(r["device"]) for r in self.d["flare_tie_ins"]}
        end = _mm(self.d["header"]["developed length, blinded end to the stack base"])
        cuts = sorted(set([0.0, end] + list(tie.values())))
        for lo, hi in zip(cuts, cuts[1:]):
            carried = {vid: part for vid, part in parts.items() if tie[vid] >= hi - 1.0e-9}
            if carried:
                w, mw, k, z, t_K = self.mixed(carried)
                rho = self.density(p, t_K, mw, z)
                v = w / 3600.0 / (rho * a)
                kt = F_DARCY * (hi - lo) / d \
                    + sum(K_FIT[f] for f, x in self.d["fitting"] if lo < x <= hi)
                p += kt * rho * v * v / 2.0 / 1.0e5
            for vid in parts:
                if abs(tie[vid] - hi) < 1.0e-9:
                    at[vid] = p - ATM
        return p - ATM, {vid: at.get(vid, p - ATM) for vid in parts}

    def converge(self, contingency, tip_mm=None):
        """The contingency brought out as one system: rates, relieving pressures and header together.

        Section 4.1 lifts a conventional device's relieving pressure by the pressure at its own tie-in, and
        that pressure is built up by the flow those devices are putting into the header, so neither can be had
        before the other. Section 6 says to start with no built-up pressure and sweep until nothing moves by
        more than SETTLE; passing less as the back pressure rises, the sweeps close on one answer from below.
        """
        keep = dict(self.back)
        try:
            self.back = {}
            parts, inlet, at = {}, 0.0, {}
            for _ in range(SWEEP_CAP):
                parts = self.discharging(contingency)
                inlet, at = self.header_profile(parts, tip_mm)
                moved = max([abs(at.get(v, 0.0) - self.back.get(v, 0.0))
                             for v in set(at) | set(self.back)] or [0.0])
                self.back = at
                if moved <= SETTLE:
                    break
            return parts, inlet, at
        finally:
            self.back = keep

    def header_pressure(self, parts):
        """The pressure at the blinded end, walking out from the tip one length of header at a time.

        Each length between two tie-ins carries only the devices that tie in beyond it, so both the flow and
        the mixture change from length to length; the density of each is taken at the pressure already
        reached at its downstream end, which is what lets the walk run without iterating.
        """
        if not parts:
            return 0.0
        total, mw, k, z, t_K = self.mixed(parts)
        d_tip = _mm(self.d["tip"]["bore"]) / 1000.0
        rho = self.density(ATM, t_K, mw, z)
        v = total / 3600.0 / (rho * math.pi / 4.0 * d_tip * d_tip)
        p = ATM + self.tip_k() * rho * v * v / 2.0 / 1.0e5
        d = _mm(self.d["header"]["bore"]) / 1000.0
        a = math.pi / 4.0 * d * d
        tie = {r["device"]: self.tie_in(r["device"]) for r in self.d["flare_tie_ins"]}
        end = _mm(self.d["header"]["developed length, blinded end to the stack base"])
        cuts = sorted(set([0.0, end] + list(tie.values())))
        for lo, hi in zip(cuts, cuts[1:]):
            carried = {vid: part for vid, part in parts.items() if tie[vid] >= hi - 1.0e-9}
            if not carried:
                continue
            w, mw, k, z, t_K = self.mixed(carried)
            rho = self.density(p, t_K, mw, z)
            v = w / 3600.0 / (rho * a)
            kt = F_DARCY * (hi - lo) / d + sum(K_FIT[f] for f, x in self.d["fitting"] if lo < x <= hi)
            p += kt * rho * v * v / 2.0 / 1.0e5
        return p - ATM

    def sheet(self):
        out = []
        for contingency in self.contingencies:
            parts, inlet, at = self.converge(contingency)
            load = sum(v[0] for v in parts.values())
            out.append((contingency, tuple(sorted(parts)), load, inlet))
        return out

    def worst_felt(self, tip_mm=None):
        """The largest share of its own set pressure any conventional device is left standing against."""
        worst, who, where = 0.0, "", ""
        for contingency in self.contingencies:
            parts, inlet, at = self.converge(contingency, tip_mm)
            for vid, felt in at.items():
                if self.bellows(vid):
                    continue
                share = felt / self.set_pressure(vid)
                if share > worst:
                    worst, who, where = share, vid, contingency
        return worst, who, where

    def sizing(self):
        """Section 9: the smallest tip the vendor supplies that leaves no conventional device over the limit.

        The bore changes the tip's loss, which changes every back pressure, which changes the relieving
        pressures and so the rates, so each candidate has to be brought out as its own converged system.
        """
        flat = " ".join(self.d["flare_system"].split())
        bores = sorted(float(x) for x in
                       re.search(r"Tip bores the vendor supplies ([\d.,and ]+?) mm", flat).group(1)
                       .replace("and", " ").replace(",", " ").split())
        limit = _num(re.search(r"more than ([\d.]+) per cent of", " ".join(self.d["standard"].split()))
                     .group(1)) / 100.0
        for bore in bores:
            share, who, where = self.worst_felt(bore)
            if share <= limit:
                return bore, who, share, where
        return None, "", 0.0, ""


# The two tests that reach a graded value. The tip's coefficient enters every pressure, and P-401's present
# shutoff decides whether its blocked discharge is credible at all, so which devices discharge under a loss of
# air. The other four tests on the crew's list cannot reach any row: E-406's coefficient-area is only ever used
# for T-402's loss of cooling, which the credit for SIF-4061 sets aside; no device admits a cause PV-4031 could
# create; a loss of cooling is total, so E-404's duty does not enter a rate; and PSV-404's set pressure is
# already in the shop record.
NEEDED = ("tip-backpressure", "pump-shutoff")


def main():
    reports = order(NEEDED)
    study = Study(load(), reports)
    rows = study.sheet()
    bore, who, share, where = study.sizing()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["contingency", "devices", "load_kg_per_h", "header_inlet_barg"])
        for name, devices, total, back in rows:
            w.writerow([name, ";".join(devices), "%.1f" % total, "%.4f" % back])
    with open(SIZING_OUT, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["tip_bore_mm", "binding_device", "back_pressure_pct"])
        w.writerow(["%.1f" % bore, who, "%.3f" % (100.0 * share)])
    for name, devices, total, back in rows:
        print("%-24s %-34s %11.1f kg/h %8.4f barg" % (name, " ".join(devices) or "none", total, back))
    print("re-rating: tip %.1f mm, %s binding at %.3f%% of set under %s" % (bore, who, 100.0 * share, where))
    return 0


if __name__ == "__main__":
    sys.exit(main())
