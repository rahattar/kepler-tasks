#!/usr/bin/env python3
"""A second study, written separately from solution/solve.py and sharing no code with it.

It reads the same records with pandas, builds one table of every (device, contingency) pair that the standard
could put in play, reduces that table to the relieving sets, and marches the header once per set with numpy. Where
solve.py walks device by device through methods, this builds the whole table at once and groups it; where solve.py
interpolates with its own helper, this uses numpy.interp. It takes its own choices where the standard leaves room:
the control valve coefficient by a least squares fit through the origin on the whole trend, the reboiler
coefficient-area by a least squares fit of duty against temperature difference, and the pump curve from a least
squares quadratic on the latest test.

    python3 independent.py [--seeds]
"""
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
AIR = 28.96
PURGE_MW = 28.01
CUT = 7.6
EXPONENT = 0.82
DARCY = 0.018
KFIT = {"90 degree elbow": 0.30, "tee, flow through the run": 0.20}
ACCUM = {"fire": 1.21}
FLOOR = 1.10
SETTLE = 1.0e-4
SWEEP_CAP = 500
SIL_FLOOR, PROOF_CEILING = 2, 18

# the plant's shape, as the unit description and the drive schedule describe it
ADMIT = {"PSV-401": ("PV-4001", None), "PSV-407": ("PV-4071", "PSV-411"), "PSV-409": ("PV-4021", "PSV-401")}
BOILS = {"PSV-403": ("E-403", "t401"), "PSV-406": ("E-406", "t402")}
CONDENSES = {"T-401": "E-404", "T-402": "E-407"}
PUMPS = {"PSV-405": "P-401"}
DISCHARGE_VALVE = "FV-4051"
VALVE_STREAM = {"PV-4001": "feed_gas", "PV-4021": "feed_gas", "PV-4031": "c2_overhead",
                "PV-4061": "c4_product", "PV-4071": "c3_product"}
VESSEL_TEMP = {"PSV-401": "v401_temp_C", "PSV-409": "v402_temp_C"}
CONTROL_ELEMENT = {("PSV-401", "control_valve_failure"): "PT-4012",
                   ("PSV-403", "cooling_failure"): "PT-4031",
                   ("PSV-406", "cooling_failure"): "PT-4061",
                   ("PSV-409", "control_valve_failure"): "PT-4021"}
PREVENTED = {"V-401 control valve failure": ("PSV-401", "control_valve_failure"),
             "T-401 loss of overhead cooling": ("PSV-403", "cooling_failure"),
             "T-402 loss of overhead cooling": ("PSV-406", "cooling_failure"),
             "V-402 control valve failure": ("PSV-409", "control_valve_failure")}
COMPRESSOR, SAFETY = "K-901", "SIS"


# --------------------------------------------------------------------------- the records
def tables(text, first):
    """Every pipe table in a document, keyed by its first column name; `first` picks one out."""
    out, head, rows = {}, None, []
    for line in text.splitlines() + ["."]:
        if line.strip().startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if set("".join(cells)) <= set("-: "):
                continue
            if head is None:
                head = cells
            else:
                rows.append(cells)
            continue
        if head is not None:
            out.setdefault(head[0], []).append(pd.DataFrame(rows, columns=head))
            head, rows = None, []
    return out[first]


class Records(object):
    def __init__(self, data, reports=None):
        self.data = data
        self.reports = {} if reports is None else reports
        self.standing = {}        # the built-up pressure each device is against, while the system is swept
        for name in ("relief_valve_register", "valve_history", "control_valve_data", "control_valve_trend",
                     "operating_record", "instrument_schedule", "sis_register", "exchanger_data",
                     "fluid_properties", "gas_properties", "liquid_properties", "gas_analysis",
                     "modification_register", "pump_test_record", "pump_data", "fire_zones",
                     "drive_schedule", "maintenance_log", "flare_tie_ins", "component_properties"):
            setattr(self, name, pd.read_csv(os.path.join(data, name + ".csv"), dtype=str))
        self.doc = {}
        for name in ("standard", "unit_400", "vessel_data", "flare_system", "flare_load_study_2019"):
            with open(os.path.join(data, "docs", name + ".md")) as handle:
                self.doc[name] = handle.read()

        self.reg = self.relief_valve_register.set_index("valve")
        self.cv = self.control_valve_data.set_index("tag")
        self.exch = self.exchanger_data.set_index("item")
        self.drive = self.drive_schedule.set_index("tag")
        self.tie = self.flare_tie_ins.set_index("device")
        self.comp = dict(zip(self.component_properties["component"],
                             self.component_properties["molar_mass_kg_per_kmol"].astype(float)))
        self.vessel = tables(self.doc["vessel_data"], "item")[0].set_index("item")
        self.insul = tables(self.doc["vessel_data"], "item")[1].set_index("item")
        self.column = tables(self.doc["vessel_data"], "column")[0].set_index("column")
        self.other = tables(self.doc["unit_400"], "device")[0].set_index("device")
        self.header = dict(zip(*tables(self.doc["flare_system"], "item")[0].values.T))
        self.tip = dict(zip(*tables(self.doc["flare_system"], "item")[1].values.T))
        fit = tables(self.doc["flare_system"], "fitting")[0]
        self.fittings = list(zip(fit.iloc[:, 0], fit.iloc[:, 1].astype(float)))
        flat = " ".join(self.doc["unit_400"].split())
        self.cap = float(re.search(r"at the unit limit at ([\d.]+) barg", flat).group(1))
        self.drained = "confirmed drainage and firewater coverage over the whole unit" \
            in " ".join(self.doc["vessel_data"].split())
        self.zone = {r["zone"]: str(r["items"]).split() for _, r in self.fire_zones.iterrows()}
        # the names the standard itself lists, in the order it lists them
        section = self.doc["standard"].split("## 2 ")[1].split("## 3 ")[0]
        self.contingencies = []
        for name in re.findall(r"`([a-z_0-9]+)`", section):
            if name not in self.contingencies:
                self.contingencies.append(name)

        self.record = self.operating_record.apply(pd.to_numeric, errors="coerce")
        self.sat = {}
        for stream, part in self.fluid_properties.groupby("stream"):
            part = part.apply(pd.to_numeric, errors="coerce").sort_values("pressure_bara")
            self.sat[stream] = part
        self.gas = {}
        for stream, part in self.gas_properties.groupby("stream"):
            self.gas[stream] = part.apply(pd.to_numeric, errors="coerce").sort_values("pressure_bara")
        self.liquid = {}
        for stream, part in self.liquid_properties.groupby("stream"):
            self.liquid[stream] = part.apply(pd.to_numeric, errors="coerce").sort_values("temperature_C")

    # -- properties, by interpolation on the published tables --------------
    def sat_at(self, stream, p, column):
        t = self.sat[stream]
        return float(np.interp(p, t["pressure_bara"].values, t[column].values))

    def gas_at(self, stream, p, column):
        t = self.gas[stream]
        return float(np.interp(p, t["pressure_bara"].values, t[column].values))

    def liquid_at(self, stream, temp, column):
        t = self.liquid[stream]
        return float(np.interp(temp, t["temperature_C"].values, t[column].values))

    def mean(self, column):
        return float(self.record[column].mean())

    # -- the feed -----------------------------------------------------------
    def feed_molar_mass(self):
        last = self.gas_analysis.sort_values("sample_date").iloc[-1]
        return float(sum(float(last[c]) * m for c, m in self.comp.items()))

    def meter_factor(self):
        """FE-4011's computer holds a fixed relative density, so its reading moves as the square root of the
        ratio of the true density to the one it holds."""
        row = self.instrument_schedule.set_index("tag").loc["FE-4011", "flow_computer_density"]
        held = re.search(r"([\d.]+)", str(row))
        if not held:
            return 1.0
        return math.sqrt((self.feed_molar_mass() / AIR) / float(held.group(1)))

    def vapour(self, stream, p, temp=None):
        """(molar mass, k, Z, T) of a vapour at p bara: the feed from its analysis, the rest from saturation."""
        if stream == "feed_gas":
            return (self.feed_molar_mass(), self.gas_at(stream, p, "k"),
                    self.gas_at(stream, p, "z"), temp + 273.15)
        return (self.sat_at(stream, p, "vapour_molar_mass"), self.sat_at(stream, p, "vapour_k"),
                self.sat_at(stream, p, "vapour_z"), self.sat_at(stream, p, "saturation_temp_C") + 273.15)

    # -- the devices as they stand -----------------------------------------
    def setting(self, device):
        work = self.valve_history[self.valve_history["valve"] == device]
        if len(work):
            return float(work.sort_values("work_date").iloc[-1]["as_left_set_barg"])
        return float(self.reg.loc[device, "set_pressure_barg"])

    def balanced(self, device):
        """A balanced bonnet isolates the disc from the header; a conventional one does not."""
        return "bellows" in str(self.reg.loc[device, "bonnet"]).lower()

    def relieving(self, device, cause):
        """Section 4.1: what stands at a conventional device's outlet is added to its set pressure."""
        standing = 0.0 if self.balanced(device) else self.standing.get(device, 0.0)
        return (self.setting(device) + standing) * ACCUM.get(cause, FLOOR) + ATM

    def moved(self, item):
        """How far an item has been re-set since the data book, from the modification register."""
        total = 0.0
        for text in self.modification_register["description"]:
            found = re.search(r"%s re-set ([\d.]+) m higher" % re.escape(item), " ".join(str(text).split()))
            if found:
                total += float(found.group(1))
        return total

    def tie_in(self, device):
        """The isometrics, overtaken by any later modification."""
        where = float(self.tie.loc[device, "tie_in_m_from_stack_base"])
        for text in self.modification_register["description"]:
            found = re.search(r"%s\b.*?tie-in on the main header from [\d.]+ m to ([\d.]+) m"
                              % re.escape(device), " ".join(str(text).split()))
            if found:
                where = float(found.group(1))
        return where

    # -- the quantities the records only imply -----------------------------
    def coefficient(self, tag):
        """Rated Cv by least squares through the origin: minimise sum (w - Cv x)^2 over the trend."""
        rows = self.control_valve_trend[self.control_valve_trend["tag"] == tag]
        spec = self.cv.loc[tag]
        xt, fp, r = float(spec["xt"]), float(spec["fp"]), float(spec["rangeability"])
        correction = self.meter_factor() if spec["flow_measurement"] == "FE-4011" else 1.0
        stream = VALVE_STREAM[tag]
        num = den = 0.0
        for _, row in rows.iterrows():
            p_up, p_dn = float(row["upstream_bara"]), float(row["downstream_bara"])
            travel = float(row["travel_pct"]) / 100.0
            molar, k, z, temp = self.vapour(stream, p_up, float(row["upstream_temp_C"]))
            unit = self.flow(1.0, xt, fp, k, p_up, p_dn, self.rho(p_up, temp, molar, z))
            if unit <= 0.0:
                continue
            x = unit * r ** (travel - 1.0) / 1.156
            w = float(row["flow_kgh"]) * correction
            num += w * x
            den += x * x
        return num / den

    def coefficient_area(self, device):
        """UA by least squares of the record's duty against its temperature difference, through the origin."""
        name, prefix = BOILS[device]
        number = name.split("-")[1]
        pressure = self.record["e%s_steam_barg" % number] + ATM
        latent = np.interp(pressure, self.sat["steam"]["pressure_bara"].values,
                           self.sat["steam"]["latent_heat_kj_per_kg"].values)
        duty = self.record["e%s_steam_kgh" % number].values * latent / 3600.0
        steam_t = np.interp(pressure, self.sat["steam"]["pressure_bara"].values,
                            self.sat["steam"]["saturation_temp_C"].values)
        gap = steam_t - self.record["%s_bottoms_C" % prefix].values
        keep = gap > 0.0
        return float((duty[keep] * gap[keep]).sum() / (gap[keep] ** 2).sum())

    def tip_coefficient(self):
        """The slope of the measured rise against rho v^2 / 2, by a polynomial fit with no constant term.

        The tip now on the stack came from another vendor with no data, so the only figure that describes it is
        the crew's back pressure test; the 1.80 in the 2019 study belongs to the tip it replaced.
        """
        rows = self.reports.get("tip-backpressure")
        if not rows:
            raise SystemExit("no tip back pressure test: the coefficient of the tip installed is on no record")
        bore = float(re.search(r"([\d.]+)", self.tip["bore"]).group(1)) / 1000.0
        area = math.pi / 4.0 * bore ** 2
        x, y = [], []
        for row in rows:
            flow = float(row["nitrogen_flow_kg_per_h"])
            temp = float(row["nitrogen_temp_C"]) + 273.15
            density = self.rho(ATM, temp, PURGE_MW, 1.0)
            x.append(density * (flow / 3600.0 / (density * area)) ** 2 / 2.0 / 1.0e5)
            y.append(float(row["stack_base_gauge_bar"]))
        return float(np.linalg.lstsq(np.array(x).reshape(-1, 1), np.array(y), rcond=None)[0][0])

    def curve(self, device):
        """h = h0 (1 - b q^2) with both constants by least squares on the pump as it now stands."""
        name = PUMPS[device]
        sheet = self.pump_data.set_index("pump").loc[name]
        fresh = self.reports.get("pump-shutoff")
        if fresh:
            q = np.array([float(r["flow_m3h"]) for r in fresh])
            h = np.array([float(r["head_m"]) for r in fresh])
        else:
            tests = self.pump_test_record[self.pump_test_record["pump"] == name]
            tests = tests[tests["test_date"] == tests["test_date"].max()]
            q = tests["flow_m3h"].astype(float).values
            h = tests["head_m"].astype(float).values
        slope, intercept = np.polyfit(q ** 2, h, 1)
        return intercept, -slope / intercept, float(sheet["normal_suction_pressure_barg"]), \
            float(sheet["temperature_C"])

    # -- flow relations -----------------------------------------------------
    def rho(self, p_bara, temp_k, molar, z):
        return p_bara * 1.0e5 * molar / (z * RG * temp_k)

    def flow(self, kv, xt, fp, k, p_up, p_dn, rho_up):
        if p_up <= p_dn:
            return 0.0
        critical = (k / 1.40) * xt
        x = min((p_up - p_dn) / p_up, critical)
        return 3.16 * kv * fp * (1.0 - x / (3.0 * critical)) * math.sqrt(x * p_up * 100.0 * rho_up)

    def wetted(self, item):
        """Shell and heads up to the 7.6 m cut, with a band for each tray at or below it."""
        shape = self.vessel.loc[item, "shape"]
        bore = float(self.vessel.loc[item, "diameter"])
        foot = float(self.vessel.loc[item, "bottom tangent"]) + self.moved(item)
        depth = float(self.vessel.loc[item, "highest normal level"])
        head = 1.084 * bore * bore
        if shape == "vertical":
            wet = max(0.0, min(foot + depth, CUT) - foot)
            return math.pi * bore * wet + (head if foot < CUT else 0.0)
        if shape == "horizontal":
            wet = min(depth, max(0.0, CUT - foot))
            if wet <= 0.0:
                return 0.0
            share = math.acos((bore / 2.0 - wet) / (bore / 2.0)) / math.pi
            return share * (math.pi * bore * float(self.vessel.loc[item, "T-T length"]) + 2.0 * head)
        trays = self.column.loc[item]
        area = 0.0
        top = min(foot + depth, CUT)
        if top > foot:
            area += math.pi * bore * (top - foot) + head
        lowest = float(trays["lowest tray above grade"]) + self.moved(item)
        pitch, band = float(trays["spacing"]), float(trays["tray liquid depth"])
        for i in range(int(float(trays["trays"]))):
            if lowest + i * pitch <= CUT:
                area += math.pi * bore * band
        return area

    def environment_factor(self, item, relief_temp):
        row = self.insul.loc[item] if item in self.insul.index else None
        if row is None or str(row["fire resistance certificate"]).strip().lower() == "none":
            return 1.0
        return (float(row["conductivity, W/m K"]) / float(row["thickness, m"])) \
            * (904.0 - relief_temp) / 21000.0

    def absorbed(self, item, relief_temp):
        constant = 43.2 if self.drained else 70.9
        return constant * self.environment_factor(item, relief_temp) * self.wetted(item) ** EXPONENT


# --------------------------------------------------------------------------- what each contingency reaches
def supply(R, tag):
    return R.drive.loc[tag, "electrical_supply"]


def air_gone(R, contingency):
    if contingency == "instrument_air_failure":
        return True
    return contingency == "power_failure" and supply(R, COMPRESSOR) == "normal"


def cooling_gone(R, item, contingency):
    cooler = CONDENSES.get(item)
    if cooler is None:
        return False
    if contingency == "power_failure":
        return supply(R, cooler) == "normal"
    if contingency == "cooling_water_failure":
        return "water" in str(R.drive.loc[cooler, "cooling_medium"])
    return False


def opens(R, tag):
    return R.cv.loc[tag, "position_on_air_failure"] == "open"


def cause(R, device, contingency):
    """The cause the contingency puts at the device, or None."""
    admitted = R.reg.loc[device, "causes_admitted"].split()
    item = R.reg.loc[device, "protected_item"]
    if contingency.startswith("fire_zone_"):
        if item in R.zone.get(contingency[-1].upper(), []) and "fire" in admitted:
            return "fire"
        return None
    if cooling_gone(R, item, contingency) and "cooling_failure" in admitted:
        return "cooling_failure"
    if air_gone(R, contingency):
        tag = ADMIT.get(device, (None, None))[0]
        if tag and opens(R, tag) and "control_valve_failure" in admitted:
            return "control_valve_failure"
        running = not (contingency == "power_failure" and supply(R, PUMPS.get(device, "")) == "normal") \
            if device in PUMPS else False
        if device in PUMPS and "blocked_outlet" in admitted and not opens(R, DISCHARGE_VALVE) and running:
            return "blocked_outlet"
    return None


def set_aside(R, device, contingency, why):
    """Whether an instrumented function may be credited with preventing this cause."""
    for _, row in R.sis_register.iterrows():
        if PREVENTED.get(row["contingency_prevented"]) != (device, why):
            continue
        rated = int(str(row["sil"]).split()[-1]) >= SIL_FLOOR
        tested = float(row["proof_test_interval_months"]) <= PROOF_CEILING
        apart = row["initiating_element"] != CONTROL_ELEMENT.get((device, why))
        powered = not (contingency == "power_failure" and supply(R, SAFETY) == "normal")
        return rated and tested and apart and powered
    return False


def discharge(R, device, why):
    """(kg/h, molar mass, k, Z, T) under this cause, or None where the cause cannot be realised."""
    p1 = R.relieving(device, why)
    item = R.reg.loc[device, "protected_item"]
    if why == "fire":
        held = R.vessel.loc[item, "liquid held"]
        relief_temp = R.sat_at(held, p1, "saturation_temp_C")
        if R.wetted(item) <= 0.0:
            return None
        w = 3600.0 * R.absorbed(item, relief_temp) / R.sat_at(held, p1, "latent_heat_kj_per_kg")
        return (w, R.sat_at(held, p1, "vapour_molar_mass"), R.sat_at(held, p1, "vapour_k"),
                R.sat_at(held, p1, "vapour_z"), relief_temp + 273.15)
    if why == "cooling_failure":
        held = R.vessel.loc[item, "liquid held"]
        steam = float(re.search(r"([\d.]+)", R.exch.loc[BOILS[device][0], "tube_side"]).group(1)) + ATM
        gap = max(0.0, R.sat_at("steam", steam, "saturation_temp_C")
                  - R.sat_at(held, p1, "saturation_temp_C"))
        w = 3600.0 * R.coefficient_area(device) * gap / R.sat_at(held, p1, "latent_heat_kj_per_kg")
        return (w,) + state(R, device, p1)
    if why == "control_valve_failure":
        tag, upstream_device = ADMIT[device]
        if upstream_device is None:
            source = R.cap + ATM
        elif upstream_device in R.reg.index:
            source = float(R.reg.loc[upstream_device, "set_pressure_barg"]) + ATM
        else:
            source = float(R.other.loc[upstream_device, "set, barg"]) + ATM
        stream = VALVE_STREAM[tag]
        temp = R.mean("v401_temp_C") if stream == "feed_gas" else None
        molar, k, z, temp_k = R.vapour(stream, source, temp)
        spec = R.cv.loc[tag]
        w = R.flow(R.coefficient(tag) / 1.156, float(spec["xt"]), float(spec["fp"]), k,
                   source, p1, R.rho(source, temp_k, molar, z))
        return (w,) + state(R, device, p1)
    if why == "blocked_outlet":
        shutoff, b, suction, temp = R.curve(device)
        density = R.liquid_at("bottoms_product", temp, "density_kg_per_m3")
        head = (p1 - (suction + ATM)) * 1.0e5 / (density * 9.81)
        if head >= shutoff:
            return None
        return (math.sqrt((1.0 - head / shutoff) / b) * density, 86.0, 1.05, 1.0, temp + 273.15)
    raise ValueError(why)


def state(R, device, p1):
    fluid = R.reg.loc[device, "relieving_fluid"]
    if fluid == "feed_gas":
        return (R.feed_molar_mass(), R.gas_at(fluid, p1, "k"), R.gas_at(fluid, p1, "z"),
                R.mean(VESSEL_TEMP[device]) + 273.15)
    return R.vapour(fluid, p1)


# --------------------------------------------------------------------------- the table, and the study
def table(R):
    """One row for every (device, contingency) pair the standard could put in play."""
    rows = []
    for device in R.reg.index:
        for contingency in R.contingencies:
            why = cause(R, device, contingency)
            if why is None:
                continue
            if set_aside(R, device, contingency, why):
                rows.append(dict(device=device, contingency=contingency, cause=why, discharges=False,
                                 load=0.0, molar=0.0, k=0.0, z=0.0, temp=0.0))
                continue
            got = discharge(R, device, why)
            if got is None or got[0] <= 0.0:
                rows.append(dict(device=device, contingency=contingency, cause=why, discharges=False,
                                 load=0.0, molar=0.0, k=0.0, z=0.0, temp=0.0))
                continue
            rows.append(dict(device=device, contingency=contingency, cause=why, discharges=True,
                             load=got[0], molar=got[1], k=got[2], z=got[3], temp=got[4]))
    return pd.DataFrame(rows, columns=["device", "contingency", "cause", "discharges",
                                       "load", "molar", "k", "z", "temp"])


def mixture(part):
    """Molar mass from the moles, the rest mass-weighted."""
    total = part["load"].sum()
    moles = (part["load"] / part["molar"]).sum()
    return (total, total / moles, float((part["load"] * part["k"]).sum() / total),
            float((part["load"] * part["z"]).sum() / total),
            float((part["load"] * part["temp"]).sum() / total))


def inlet_pressure(R, part, tip_mm=None):
    """March out from the tip, one length at a time: (blinded end, pressure reached at each tie-in)."""
    reached = {}
    if not len(part):
        return 0.0, {}
    total, molar, k, z, temp = mixture(part)
    tip_bore = (float(re.search(r"([\d.]+)", R.tip["bore"]).group(1)) if tip_mm is None else tip_mm) / 1000.0
    density = R.rho(ATM, temp, molar, z)
    speed = total / 3600.0 / (density * math.pi / 4.0 * tip_bore ** 2)
    p = ATM + R.tip_coefficient() * density * speed ** 2 / 2.0 / 1.0e5

    bore = float(re.search(r"([\d.]+)", R.header["bore"]).group(1)) / 1000.0
    area = math.pi / 4.0 * bore ** 2
    end = float(re.search(r"([\d.]+)",
                          R.header["developed length, blinded end to the stack base"]).group(1))
    where = {device: R.tie_in(device) for device in R.tie.index}
    marks = np.unique(np.array([0.0, end] + list(where.values())))
    for low, high in zip(marks[:-1], marks[1:]):
        beyond = part[[where[d] >= high - 1.0e-9 for d in part["device"]]]
        if not len(beyond):
            continue
        carried, molar, k, z, temp = mixture(beyond)
        density = R.rho(p, temp, molar, z)
        speed = carried / 3600.0 / (density * area)
        resistance = DARCY * (high - low) / bore \
            + sum(KFIT[f] for f, x in R.fittings if low < x <= high)
        p += resistance * density * speed ** 2 / 2.0 / 1.0e5
        for device in part["device"]:
            if abs(where[device] - high) < 1.0e-9:
                reached[device] = p - ATM
    return p - ATM, {d: reached.get(d, p - ATM) for d in part["device"]}


def settle(R, contingency, tip_mm=None):
    """Sweep the contingency to settlement: (table of what discharges, blinded end, each tie-in).

    Section 4.1 ties the relieving pressure of a conventional device to the header, and section 6 ties the
    header to the rates, so the two are swept together from no built-up pressure until nothing moves.
    """
    R.standing = {}
    part, inlet, reached = None, 0.0, {}
    for _ in range(SWEEP_CAP):
        whole = table(R)
        part = whole[(whole["contingency"] == contingency) & whole["discharges"]]
        inlet, reached = inlet_pressure(R, part, tip_mm)
        moved = max([abs(reached.get(d, 0.0) - R.standing.get(d, 0.0))
                     for d in set(reached) | set(R.standing)] or [0.0])
        R.standing = dict(reached)
        if moved <= SETTLE:
            break
    R.standing = {}
    return part, inlet, reached


def re_rating(R):
    """Section 9: the smallest bore the vendor supplies that leaves no conventional device over the limit."""
    flat = " ".join(R.doc["flare_system"].split())
    bores = sorted(float(x) for x in
                   re.search(r"Tip bores the vendor supplies ([\d.,and ]+?) mm", flat)
                   .group(1).replace("and", " ").replace(",", " ").split())
    limit = float(re.search(r"more than ([\d.]+) per cent of",
                            " ".join(R.doc["standard"].split())).group(1)) / 100.0
    for bore in bores:
        worst, who, where = 0.0, "", ""
        for contingency in R.contingencies:
            part, inlet, reached = settle(R, contingency, bore)
            for device, standing in reached.items():
                if R.balanced(device):
                    continue
                share = standing / R.setting(device)
                if share > worst:
                    worst, who, where = share, device, contingency
        if worst <= limit:
            return bore, who, worst, where
    return None, "", 0.0, ""


def study(data, reports):
    R = Records(data, reports)
    rows = []
    for contingency in R.contingencies:
        part, inlet, reached = settle(R, contingency)
        rows.append((contingency, tuple(sorted(part["device"])), float(part["load"].sum()), inlet))
    return rows, re_rating(R)


def main():
    want_seeds = "--seeds" in sys.argv
    sealed, tru = common.truth()
    reports = common.crew_reports(sealed)
    rows, sizing = study(common.DATA, reports)
    n, notes = common.compare(rows, sealed, tru, sizing)

    print("A second study of the same records, written separately. Tolerance %.3f relative.\n" % sealed.TOL)
    print("| contingency | devices | load, kg/h | header inlet, barg | sealed load | sealed inlet |")
    print("|---|---|---|---|---|---|")
    worst_load = worst_back = 0.0
    for contingency, devices, total, back in rows:
        t = tru[contingency]
        rl = (total - t["load"]) / t["load"] if t["load"] else 0.0
        rb = (back - t["back"]) / t["back"] if t["back"] > 0.01 else 0.0
        worst_load, worst_back = max(worst_load, abs(rl)), max(worst_back, abs(rb))
        print("| %s | %s | %.1f | %.4f | %.1f (%+.3f%%) | %.4f (%+.3f%%) |"
              % (contingency, " ".join(devices) or "none", total, back,
                 t["load"], 100.0 * rl, t["back"], 100.0 * rb))
    print("\nre-rating: tip %s mm, %s binding at %.3f%%" % (sizing[0], sizing[1], 100.0 * sizing[2]))
    print("%d of %d parts agree; worst load %.4f and pressure %.4f against a band of %.4f"
          % (n, len(tru) + 1, worst_load, worst_back, sealed.TOL))

    if want_seeds:
        tmp = tempfile.mkdtemp(prefix="fl_ind_")
        os.environ["GEN_QUIET"] = "1"
        sys.path.insert(0, os.path.join(common.ROOT, "authoring", "provenance"))
        import gen
        try:
            worst = 7
            for seed in SEEDS:
                out = os.path.join(tmp, "data")
                shutil.rmtree(out, ignore_errors=True)
                os.makedirs(os.path.join(out, "docs"), exist_ok=True)
                gen.main(out, seed)
                rows_s, sizing_s = study(out, reports)
                k, _ = common.compare(rows_s, sealed, tru, sizing_s)
                worst = min(worst, k)
            print("worst agreement over %d laboratory seeds: %d of 7" % (len(SEEDS), worst))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    if n != len(tru):
        print("\nwhere they differ: %s" % common.worst(notes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
