#!/usr/bin/env python3
"""Reference: the moves that leave every coupled train of Unit 3 aligned at its running condition, to AP-12.

It works from the records in /app/data and from the laser contractor's six reports, and from nothing else. The
order of work is the order of the problem:

  1. each train's cold position from its dial sheet, corrected for the sag of the bracket the fitter had;
  2. how far each machine's shaft moves from cold to running, for every machine the records can still speak
     for as the unit now runs;
  3. the machines the records cannot speak for, sorted into groups that one measurement can stand for, and
     the laser programme that measures one train of each, placed in one order;
  4. the measured groups carried to their other members, and the moves at the feet.

Run with no arguments inside the container. DATA_DIR, REPORT_DIR, OUTPUT and LASERVISIT move the paths and the
command for a run elsewhere.
"""
import csv
import os
import re
import subprocess
import sys

EXPANSION = 11.5e-6          # per K, AP-12 section 5
QUOTED_AT = 25.0             # C, the ambient the survey's support temperatures are referred to
COLUMNS = ("tag", "v_front_mm", "v_rear_mm", "h_front_mm", "h_rear_mm")
TABLES = ("train_register", "pump_data", "dial_sheets", "tool_crib_log", "sag_cards",
          "support_temperature_survey", "process_conditions", "gearbox_running_position", "hot_checks",
          "work_orders")
DOCUMENTS = ("alignment_procedure", "kit_leaflets", "laser_service", "revamp_closeout")
# work that ends a turbine's hot check: on its casing supports or on the piping connected to it (AP-12 s.5)
ENDS_A_HOT_CHECK = ("expansion joint", "spring support", "casing support", "piping", "nozzle", "exhaust line",
                    "inlet line")


def load(data_dir):
    records = {}
    for name in TABLES:
        with open(os.path.join(data_dir, name + ".csv"), newline="") as handle:
            records[name] = list(csv.DictReader(handle))
    for name in DOCUMENTS:
        with open(os.path.join(data_dir, "docs", name + ".md")) as handle:
            records[name] = handle.read()
    return records


def read_reports(report_dir, tags):
    reports = {}
    for tag in tags:
        with open(os.path.join(report_dir, tag + ".csv"), newline="") as handle:
            reports[tag] = {row["quantity"]: float(row["mm"]) for row in csv.DictReader(handle)}
    return reports


class Turnaround:
    """The unit as the records give it. `visited` holds the laser reports once there are any."""

    def __init__(self, records):
        self.rec = records
        self.register = {row["tag"]: row for row in records["train_register"]}
        self.sheets = {row["tag"]: row for row in records["dial_sheets"]}
        self.survey = {row["tag"]: row for row in records["support_temperature_survey"]}
        self.pumped_now = {row["tag"]: float(row["pumped_temperature_C"]) for row in records["process_conditions"]}
        self.construction = {row["model"]: (row["casing_support"], row["bearing_pedestal"])
                             for row in records["pump_data"]}
        self.gearbox = {row["model"]: (float(row["rise_mm"]), float(row["lateral_to_right_mm"]))
                        for row in records["gearbox_running_position"]}
        self.sag_card = {(row["kit"], int(row["bar_set"])): float(row["mandrel_bottom_reading_mm"])
                         for row in records["sag_cards"]}
        self.tolerance = float(re.search(r"within (\d+\.\d+) mm", records["alignment_procedure"]).group(1))
        self.budget = int(re.search(r"time for (\d+) trains", records["laser_service"]).group(1))
        limits = re.search(r"set 1 for spans up to (\d+) mm, set 2 above \d+ and up to (\d+) mm",
                           records["kit_leaflets"])
        self.set_limits = (float(limits.group(1)), float(limits.group(2)))
        self.visited = {}
        self.measured_ratio = {}
        self.tags = sorted(self.register)

    # ---- 1. the cold position ------------------------------------------------------------------------
    def kit(self, tag):
        sheet = self.sheets[tag]
        held = [row["kit"] for row in self.rec["tool_crib_log"]
                if row["issued_to"] == sheet["fitter"] and row["out"] <= sheet["date"] <= row["returned"]]
        if len(held) != 1:
            raise ValueError("%s: the crib log gives %d kits for %s on %s" % (tag, len(held), sheet["fitter"],
                                                                             sheet["date"]))
        return held[0]

    def bar_set(self, tag):
        span = float(self.sheets[tag]["span_mm"])
        return 1 if span <= self.set_limits[0] else 2 if span <= self.set_limits[1] else 3

    def mandrel(self, tag):
        return self.sag_card[(self.kit(tag), self.bar_set(tag))]

    def dial_position(self, tag):
        """(y, z) of the movable centreline against the stationary one at the stationary hub's plane, then at
        the movable hub's plane, from the sheet's rim readings with the sag taken out (AP-12 sections 2, 3)."""
        sheet, droop = self.sheets[tag], self.mandrel(tag)
        rim = {key: float(sheet[key]) - (droop if key.endswith("bottom") else droop / 2.0)
               for key in sheet if key.startswith(("SM_", "MS_")) and not key.endswith("top")}
        y_movable = -rim["SM_bottom"] / 2.0
        z_movable = (rim["SM_right"] - rim["SM_left"]) / 2.0
        y_stationary = rim["MS_bottom"] / 2.0
        z_stationary = (rim["MS_left"] - rim["MS_right"]) / 2.0
        return (y_stationary, z_stationary), (y_movable, z_movable)

    def cold_position(self, tag):
        if tag in self.visited:
            seen = self.visited[tag]
            return ((seen["y_stationary_plane"], seen["z_stationary_plane"]),
                    (seen["y_movable_plane"], seen["z_movable_plane"]))
        return self.dial_position(tag)

    # ---- 2. what the records say of each machine --------------------------------------------------------
    def stationary(self, tag):
        """('pump', model), ('gearbox', model) or ('fan', None)."""
        words = self.register[tag]["stationary_machine"].split()
        return (words[0], words[1] if len(words) > 1 else None)

    def changes(self, tag):
        """What the revamp did to this train's pump, from the work orders."""
        done = set()
        for order in self.rec["work_orders"]:
            if order["item"] == tag:
                if "lagged" in order["work"]:
                    done.add("lagged")
                if "blanked" in order["work"]:
                    done.add("blanked")
        return frozenset(done)

    def hot_check(self, tag):
        """The turbine's hot check figure, or None where later work has ended it."""
        for check in self.rec["hot_checks"]:
            if check["tag"] != tag:
                continue
            ended = any(order["item"] == tag and order["date"] > check["date"]
                        and any(word in order["work"].lower() for word in ENDS_A_HOT_CHECK)
                        for order in self.rec["work_orders"])
            return None if ended else (float(check["rise_mm"]), float(check["lateral_mm"]))
        return None

    def survey_excess(self, tag):
        """(support above 25 C, pumped above 25 C) at the 2019 survey."""
        row = self.survey[tag]
        return float(row["stationary_support_C"]) - QUOTED_AT, float(row["pumped_temperature_C"]) - QUOTED_AT

    def model_ratio(self, model):
        """How far a model's support followed the pumped temperature in 2019: one figure for the model, by
        least squares through the origin over every pump of it in the survey."""
        pairs = [self.survey_excess(tag) for tag in self.tags if self.stationary(tag) == ("pump", model)]
        return sum(s * p for s, p in pairs) / sum(p * p for s, p in pairs)

    def growth(self, height, support, ambient):
        return EXPANSION * float(height) * (support - ambient)

    # ---- 3. the machines the records cannot speak for, and the programme ---------------------------------
    def told_apart(self, one, other, members):
        """Whether two models' surveyed ratios differ by enough to move any of these pumps out of tolerance."""
        gap = abs(self.model_ratio(one) - self.model_ratio(other))
        return any(self.growth(self.register[tag]["stationary_shaft_height_mm"],
                               gap * (self.pumped_now[tag] - QUOTED_AT), 0.0) > self.tolerance
                   for tag in members)

    def groups(self):
        """The changed pumps, in groups one measurement can stand for: the same construction, the same work
        done, and models whose supports ran alike before it. Each group is a sorted list of tags."""
        by_work = {}
        for tag in self.tags:
            kind, model = self.stationary(tag)
            if kind == "pump" and self.changes(tag):
                by_work.setdefault((self.construction[model], self.changes(tag)), []).append(tag)
        out = []
        for members in by_work.values():
            models = sorted({self.stationary(tag)[1] for tag in members}, key=self.model_ratio)
            clusters = [[models[0]]]
            for model in models[1:]:
                if self.told_apart(clusters[-1][-1], model, members):
                    clusters.append([model])
                else:
                    clusters[-1].append(model)
            out += [sorted(tag for tag in members if self.stationary(tag)[1] in cluster) for cluster in clusters]
        return sorted(out)

    def turbines_to_measure(self):
        return [tag for tag in self.tags
                if self.register[tag]["movable_machine"] == "steam turbine" and self.hot_check(tag) is None]

    def programme(self):
        """The trains to name in the one order: every turbine without a standing hot check, and the first
        train of every group of changed pumps."""
        wanted = self.turbines_to_measure() + [group[0] for group in self.groups()]
        if len(wanted) > self.budget:
            raise ValueError("%d measurements are needed and the contractor has time for %d"
                             % (len(wanted), self.budget))
        spare = [tag for group in self.groups() for tag in group[1:]]
        return wanted + spare[:self.budget - len(wanted)]

    # ---- 4. with the reports in hand -----------------------------------------------------------------------
    def take(self, reports):
        self.visited = dict(reports)
        self.measured_ratio = {}
        for number, group in enumerate(self.groups()):
            for tag in group:
                if tag in self.visited:
                    ambient = float(self.sheets[tag]["ambient_C"])
                    height = float(self.register[tag]["stationary_shaft_height_mm"])
                    support = ambient + self.visited[tag]["stationary_rise"] / (EXPANSION * height)
                    self.measured_ratio[number] = (support - QUOTED_AT) / (self.pumped_now[tag] - QUOTED_AT)
                    break
        return self

    def pump_ratio(self, tag):
        for number, group in enumerate(self.groups()):
            if tag in group:
                if number not in self.measured_ratio:
                    raise ValueError("%s: its group was not measured" % tag)
                return self.measured_ratio[number]
        return self.model_ratio(self.stationary(tag)[1])

    def stationary_movement(self, tag):
        kind, model = self.stationary(tag)
        ambient = float(self.sheets[tag]["ambient_C"])
        height = self.register[tag]["stationary_shaft_height_mm"]
        if kind == "gearbox":
            return self.gearbox[model]
        if kind == "pump":
            support = QUOTED_AT + self.pump_ratio(tag) * (self.pumped_now[tag] - QUOTED_AT)
        else:
            support = float(self.survey[tag]["stationary_support_C"])
        return self.growth(height, support, ambient), 0.0

    def movable_movement(self, tag):
        if self.register[tag]["movable_machine"] == "steam turbine":
            figure = self.hot_check(tag)
            if figure is None:
                raise ValueError("%s: no hot check stands and the turbine was not measured" % tag)
            return figure
        ambient = float(self.sheets[tag]["ambient_C"])
        return self.growth(self.register[tag]["movable_shaft_height_mm"],
                           float(self.survey[tag]["movable_support_C"]), ambient), 0.0

    def movements(self, tag):
        """((rise, lateral) of the stationary machine, (rise, lateral) of the movable machine), cold to running."""
        if tag in self.visited:
            seen = self.visited[tag]
            return ((seen["stationary_rise"], seen["stationary_lateral"]),
                    (seen["movable_rise"], seen["movable_lateral"]))
        return self.stationary_movement(tag), self.movable_movement(tag)

    def moves(self, tag):
        """(shim front, shim rear, lateral front, lateral rear): the cold line through the two reading planes
        carried out to the feet, and set so that the running shafts are in line (AP-12 sections 4, 5)."""
        at_stationary, at_movable = self.cold_position(tag)
        stationary, movable = self.movements(tag)
        span = float(self.sheets[tag]["span_mm"])
        front = span + float(self.register[tag]["hub_plane_to_front_feet_mm"])
        rear = front + float(self.register[tag]["front_to_rear_feet_mm"])
        out = []
        for axis in (0, 1):
            relative_growth = movable[axis] - stationary[axis]
            for feet in (front, rear):
                cold = at_stationary[axis] + (at_movable[axis] - at_stationary[axis]) * feet / span
                out.append(-(cold + relative_growth))
        return tuple(out)

    def sheet(self):
        return {tag: self.moves(tag) for tag in self.tags}


def write_sheet(path, sheet):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as handle:
        handle.write(",".join(COLUMNS) + "\n")
        for tag in sorted(sheet):
            handle.write("%s,%s\n" % (tag, ",".join("%.3f" % move for move in sheet[tag])))


def main():
    data_dir = os.environ.get("DATA_DIR", "/app/data")
    report_dir = os.environ.get("REPORT_DIR", "/app/laser_reports")
    output = os.environ.get("OUTPUT", "/app/output/moves.csv")
    unit = Turnaround(load(data_dir))
    programme = unit.programme()
    if not all(os.path.exists(os.path.join(report_dir, tag + ".csv")) for tag in programme):
        subprocess.run([os.environ.get("LASERVISIT", "laservisit")] + programme, check=True)
    unit.take(read_reports(report_dir, programme))
    write_sheet(output, unit.sheet())
    print("laser programme: %s" % " ".join(programme))
    print("%d trains written to %s" % (len(unit.tags), output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
