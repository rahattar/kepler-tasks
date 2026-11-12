"""What the studies in this directory share.

Every study works the same way: it produces a complete sheet of moves the way some engineer would, writes it to
a file in the submission's format, and hands that file to the verifier's own module, tests/grade_moves.py. No
study compares numbers itself.

`Variant` is the reference solution with switches. With no switch set it is the reference. Each switch is one
thing an engineer might do differently, sound or not; the studies say which is which and the grader decides.
"""
import contextlib
import json
import os
import shutil
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
PROV = os.path.join(ROOT, "authoring", "provenance")
DATA = os.path.join(ROOT, "environment", "data")
for _path in (PROV, os.path.join(ROOT, "solution"), os.path.join(ROOT, "tests")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import gen  # noqa: E402
import grade_moves  # noqa: E402
import solve  # noqa: E402
import unit3  # noqa: E402

SHIPPED = json.load(open(os.path.join(PROV, "seed.json")))["seed"]
LAB_SEEDS = list(range(5301, 5321))
QUOTED_AT = solve.QUOTED_AT


def records(seed=SHIPPED):
    """The agent's records: the shipped ones, or the ones the generator writes for another seed."""
    if seed == SHIPPED:
        return solve.load(DATA)
    box = tempfile.mkdtemp(prefix="sam_rec_")
    try:
        gen.main(box, seed)
        return solve.load(box)
    finally:
        shutil.rmtree(box, ignore_errors=True)


def reports(seed, tags):
    """What the contractor would write for these trains, to the three decimals its reports carry."""
    trains = unit3.build(seed)
    return {tag: {quantity: float("%.3f" % value) for quantity, value in unit3.laser_report(trains[tag])}
            for tag in tags}


@contextlib.contextmanager
def _sealed_for(seed):
    """The verifier's module, grading against the unit another seed makes. The shipped seed is its own."""
    if seed == SHIPPED:
        yield
        return
    keep = grade_moves.sealed_trains
    grade_moves.sealed_trains = lambda: unit3.build(seed)
    try:
        yield
    finally:
        grade_moves.sealed_trains = keep


def grade(sheet, seed=SHIPPED, text=None):
    """Write the sheet as a submission and give it to the verifier's module. Returns its Outcome."""
    box = tempfile.mkdtemp(prefix="sam_sheet_")
    path = os.path.join(box, "moves.csv")
    try:
        if text is None:
            solve.write_sheet(path, sheet)
        else:
            with open(path, "w", newline="") as handle:
                handle.write(text)
        with _sealed_for(seed):
            return grade_moves.assess(path)
    finally:
        shutil.rmtree(box, ignore_errors=True)


def missed(outcome):
    return sorted(tag for tag, row in outcome.detail.items() if not row["aligned"])


class Variant(solve.Turnaround):
    """The reference with switches. Unknown switches are refused, so a misspelt one cannot pass for sound."""

    SWITCHES = {
        "sag": ("card", "none", "added"),
        "kit": ("crib", "first"),
        "bar": ("leaflet", "two"),
        "planes": ("as_read", "swapped"),
        "height_sign": ("as_read", "flipped"),
        "side_sign": ("as_read", "flipped"),
        "sides": ("corrected", "uncorrected"),
        "feet": ("line", "hub", "no_span", "swapped"),
        "sense": ("correct", "reversed"),
        "thermal": ("relative", "none", "reversed"),
        "ambient": ("sheet", "quoted"),
        "heights": ("register", "swapped"),
        "pumps": ("ratio", "survey", "pumped"),
        "untouched": ("model", "own"),
        "gearbox": ("maker", "thermal", "no_lateral", "lateral_left"),
        "turbine": ("measured", "hot_check", "other", "thermal"),
        "lump": ("by_ratio", "by_label", "every_model"),
        "blanked": ("changed", "plain"),
        "lagged": ("changed", "unchanged"),
        "unmeasured": ("refuse", "rescale", "plain", "sibling", "delta", "factor"),
        "transfer": ("ratio", "temperature", "rise"),
        "visited_cold": ("laser", "dial"),
        "visited_motor": ("laser", "survey"),
        "pick": ("first", "last"),
    }

    def __init__(self, records_, plan=None, **switches):
        super().__init__(records_)
        for name, value in switches.items():
            if value not in self.SWITCHES.get(name, ()):
                raise ValueError("no switch %s=%s" % (name, value))
        self.sw = {name: switches.get(name, values[0]) for name, values in self.SWITCHES.items()}
        self.plan = plan

    # ---- the cold position
    def kit(self, tag):
        if self.sw["kit"] == "first":
            sheet = self.sheets[tag]
            return [row["kit"] for row in self.rec["tool_crib_log"] if row["issued_to"] == sheet["fitter"]][0]
        return super().kit(tag)

    def bar_set(self, tag):
        return 2 if self.sw["bar"] == "two" else super().bar_set(tag)

    def mandrel(self, tag):
        card = super().mandrel(tag)
        return {"card": card, "none": 0.0, "added": -card}[self.sw["sag"]]

    def dial_position(self, tag):
        if self.sw["sides"] == "uncorrected":
            sheet, droop = self.sheets[tag], self.mandrel(tag)
            y_m = -(float(sheet["SM_bottom"]) - droop) / 2.0
            z_m = (float(sheet["SM_right"]) - float(sheet["SM_left"])) / 2.0
            y_s = (float(sheet["MS_bottom"]) - droop) / 2.0
            z_s = (float(sheet["MS_left"]) - float(sheet["MS_right"])) / 2.0
            at_s, at_m = (y_s, z_s), (y_m, z_m)
        else:
            at_s, at_m = super().dial_position(tag)
        if self.sw["planes"] == "swapped":
            at_s, at_m = at_m, at_s
        if self.sw["height_sign"] == "flipped":
            at_s, at_m = (-at_s[0], at_s[1]), (-at_m[0], at_m[1])
        if self.sw["side_sign"] == "flipped":
            at_s, at_m = (at_s[0], -at_s[1]), (at_m[0], -at_m[1])
        return at_s, at_m

    def cold_position(self, tag):
        if self.sw["visited_cold"] == "dial":
            return self.dial_position(tag)
        return super().cold_position(tag)

    # ---- the records
    def changes(self, tag):
        done = set(super().changes(tag))
        if self.sw["blanked"] == "plain":
            done.discard("blanked")
        if self.sw["lagged"] == "unchanged":
            done.discard("lagged")
        return frozenset(done)

    def told_apart(self, one, other, members):
        return {"by_ratio": super().told_apart, "by_label": lambda *a: False,
                "every_model": lambda *a: True}[self.sw["lump"]](one, other, members)

    def programme(self):
        if self.plan is not None:
            return list(self.plan)
        if self.sw["pick"] == "last":
            return self.turbines_to_measure() + [group[-1] for group in self.groups()]
        return super().programme()

    def plain_ratio(self, tag):
        """The ratio of the plain-pedestal models with the same casing support."""
        support = self.construction[self.stationary(tag)[1]][0]
        models = [m for m, (casing, pedestal) in self.construction.items() if casing == support and pedestal == "plain"]
        pairs = [self.survey_excess(t) for t in self.tags if self.stationary(t)[0] == "pump"
                 and self.stationary(t)[1] in models and self.survey_excess(t)[1] > 100.0]
        return sum(s * p for s, p in pairs) / sum(p * p for s, p in pairs)

    def pump_ratio(self, tag):
        model = self.stationary(tag)[1]
        if self.sw["blanked"] == "plain" and "blanked" in solve.Turnaround.changes(self, tag):
            return self.plain_ratio(tag)
        groups = self.groups()
        for number, group in enumerate(groups):
            if tag not in group:
                continue
            if number in self.measured_ratio:
                return self.measured_ratio[number]
            how = self.sw["unmeasured"]
            if how == "rescale":
                return self.model_ratio(model)
            if how == "plain":
                return self.plain_ratio(tag)
            # the nearest measured group of the same construction and the same work
            label = (self.construction[model], self.changes(tag))
            near = [(abs(self.model_ratio(self.stationary(g[0])[1]) - self.model_ratio(model)), n)
                    for n, g in enumerate(groups) if n in self.measured_ratio
                    and (self.construction[self.stationary(g[0])[1]], self.changes(g[0])) == label]
            if how == "refuse" or not near:
                if how == "refuse":
                    raise ValueError("%s: its group was not measured" % tag)
                return self.model_ratio(model)
            n = min(near)[1]
            before = self.model_ratio(self.stationary(groups[n][0])[1])
            if how == "sibling":
                return self.measured_ratio[n]
            if how == "delta":
                return self.model_ratio(model) + (self.measured_ratio[n] - before)
            return self.model_ratio(model) * self.measured_ratio[n] / before
        if self.sw["untouched"] == "own":
            support, pumped = self.survey_excess(tag)
            return support / pumped
        return self.model_ratio(model)

    def _visited_member(self, tag):
        for group in self.groups():
            if tag in group:
                for other in group:
                    if other in self.visited:
                        return other
        return None

    # ---- the movements
    def stationary_movement(self, tag):
        kind, model = self.stationary(tag)
        ambient = QUOTED_AT if self.sw["ambient"] == "quoted" else float(self.sheets[tag]["ambient_C"])
        height = self.register[tag]["movable_shaft_height_mm" if self.sw["heights"] == "swapped"
                                    else "stationary_shaft_height_mm"]
        survey = float(self.survey[tag]["stationary_support_C"])
        if kind == "gearbox":
            if self.sw["gearbox"] == "thermal":
                return self.growth(height, survey, ambient), 0.0
            rise, right = self.gearbox[model]
            return {"maker": (rise, right), "no_lateral": (rise, 0.0), "lateral_left": (rise, -right)}[self.sw["gearbox"]]
        if kind == "fan":
            return self.growth(height, survey, ambient), 0.0
        if self.sw["pumps"] == "survey":
            return self.growth(height, survey, ambient), 0.0
        if self.sw["pumps"] == "pumped":
            return self.growth(height, self.pumped_now[tag], ambient), 0.0
        source = self._visited_member(tag)
        if source is not None and self.sw["transfer"] != "ratio":
            seen = self.visited[source]["stationary_rise"]
            if self.sw["transfer"] == "rise":
                return seen, 0.0
            support = float(self.sheets[source]["ambient_C"]) + seen / (
                solve.EXPANSION * float(self.register[source]["stationary_shaft_height_mm"]))
            return self.growth(height, support, ambient), 0.0
        support = QUOTED_AT + self.pump_ratio(tag) * (self.pumped_now[tag] - QUOTED_AT)
        return self.growth(height, support, ambient), 0.0

    def movable_movement(self, tag):
        ambient = QUOTED_AT if self.sw["ambient"] == "quoted" else float(self.sheets[tag]["ambient_C"])
        height = self.register[tag]["stationary_shaft_height_mm" if self.sw["heights"] == "swapped"
                                    else "movable_shaft_height_mm"]
        survey = float(self.survey[tag]["movable_support_C"])
        if self.register[tag]["movable_machine"] == "steam turbine":
            how = self.sw["turbine"]
            if how == "thermal":
                return self.growth(height, survey, ambient), 0.0
            if how == "other":
                seen = [t for t in self.visited if self.register[t]["movable_machine"] == "steam turbine"]
                if seen:
                    return self.visited[seen[0]]["movable_rise"], self.visited[seen[0]]["movable_lateral"]
            if how in ("hot_check", "other"):
                check = [c for c in self.rec["hot_checks"] if c["tag"] == tag][0]
                return float(check["rise_mm"]), float(check["lateral_mm"])
            return super().movable_movement(tag)
        return self.growth(height, survey, ambient), 0.0

    def movements(self, tag):
        if tag in self.visited:
            seen = self.visited[tag]
            stationary = (seen["stationary_rise"], seen["stationary_lateral"])
            movable = (seen["movable_rise"], seen["movable_lateral"])
            if self.sw["visited_motor"] == "survey" and self.register[tag]["movable_machine"] != "steam turbine":
                movable = self.movable_movement(tag)
            return stationary, movable
        return self.stationary_movement(tag), self.movable_movement(tag)

    # ---- the feet
    def moves(self, tag):
        at_s, at_m = self.cold_position(tag)
        stationary, movable = self.movements(tag)
        span = float(self.sheets[tag]["span_mm"])
        to_front = float(self.register[tag]["hub_plane_to_front_feet_mm"])
        between = float(self.register[tag]["front_to_rear_feet_mm"])
        front = (0.0 if self.sw["feet"] == "no_span" else span) + to_front
        rear = front + between
        if self.sw["feet"] == "hub":
            front = rear = span
        if self.sw["feet"] == "swapped":
            front, rear = rear, front
        out = []
        for axis in (0, 1):
            relative = {"relative": movable[axis] - stationary[axis], "none": 0.0,
                        "reversed": stationary[axis] - movable[axis]}[self.sw["thermal"]]
            for feet in (front, rear):
                cold = at_s[axis] + (at_m[axis] - at_s[axis]) * feet / span
                move = -(cold + relative)
                out.append(-move if self.sw["sense"] == "reversed" else move)
        return tuple(out)


def run(seed=SHIPPED, plan=None, recs=None, **switches):
    """One engineer's whole job: the programme, the reports, the sheet. Returns (sheet, programme)."""
    study = Variant(recs if recs is not None else records(seed), plan=plan, **switches)
    programme = study.programme()
    study.take(reports(seed, programme))
    return study.sheet(), programme


# Sound variations: every one of these must leave all the trains aligned.
SOUND = [
    ("the reference", {}),
    ("each untouched pump on its own 2019 ratio, not its model's", dict(untouched="own")),
    ("the last train of each group visited, not the first", dict(pick="last")),
    ("visited trains kept on their dial sheets for the cold position", dict(visited_cold="dial")),
    ("visited motors taken from the survey, not the laser", dict(visited_motor="survey")),
    ("the side readings left uncorrected for sag (the two halves cancel)", dict(sides="uncorrected")),
    ("own ratios, last trains, dial positions and survey motors together",
     dict(untouched="own", pick="last", visited_cold="dial", visited_motor="survey")),
]

# Readings AP-12 does not sanction whose effect is inside the acceptance on the shipped records. They are
# reported, not counted as routes: the sheet they produce is a correct sheet.
ABSORBED = [
    ("the kit a fitter first drew taken for every one of his sheets", dict(kit="first")),
    ("25 C taken as the ambient of every sheet", dict(ambient="quoted")),
]

K = "K-201A"
LISTED = ["TP-301A", "TP-301B", "P-301A", "P-320A", "P-340A", K]
# Defective routes: (what the engineer did, switches, the programme named or None for the reference's own).
DEFECTIVE = [
    ("no sag correction", dict(sag="none"), None),
    ("the sag correction applied with the wrong sign", dict(sag="added"), None),
    ("bar set 2 taken at every span", dict(bar="two"), None),
    ("the two reading planes taken the wrong way round", dict(planes="swapped"), None),
    ("the bottom readings taken with the wrong sign", dict(height_sign="flipped"), None),
    ("right and left taken the wrong way round", dict(side_sign="flipped"), None),
    ("the offset at the movable hub taken as the move at both pairs of feet", dict(feet="hub"), None),
    ("the feet placed from the stationary plane without the span", dict(feet="no_span"), None),
    ("front and rear feet interchanged", dict(feet="swapped"), None),
    ("every move made in the opposite sense", dict(sense="reversed"), None),
    ("aligned cold to zero, no running position", dict(thermal="none"), None),
    ("the running position applied the wrong way round", dict(thermal="reversed"), None),
    ("the two machines' shaft heights interchanged", dict(heights="swapped"), None),
    ("the 2019 survey taken as it stands for every pump", dict(pumps="survey"), None),
    ("the pumped temperature taken as the support temperature", dict(pumps="pumped"), None),
    ("the gearbox taken by the thermal formula from the survey", dict(gearbox="thermal"), None),
    ("the gearbox's lateral shift left out", dict(gearbox="no_lateral"), None),
    ("the gearbox's lateral shift taken to the left", dict(gearbox="lateral_left"), None),
    ("the 2023 hot checks used for both turbines", dict(turbine="hot_check"),
     ["P-301A", "P-320A", "P-322", "P-340A", K, "K-201B"]),
    ("one turbine measured and its figure used for the other", dict(turbine="other"),
     ["TP-301A", "P-301A", "P-320A", "P-322", "P-340A", K]),
    ("the turbines taken by the thermal formula from the survey", dict(turbine="thermal"),
     ["P-301A", "P-320A", "P-322", "P-340A", K, "K-201B"]),
    ("one visit for each class as listed, HSC-250 measured, the spare on a compressor",
     dict(lump="by_label"), LISTED),
    ("one visit for each class as listed, HSC-400 measured, the spare on a compressor",
     dict(lump="by_label"), ["TP-301A", "TP-301B", "P-301A", "P-322", "P-340A", K]),
    ("one visit for each class as listed, the spare on the pump with the grout repair",
     dict(lump="by_label"), ["TP-301A", "TP-301B", "P-310A", "P-325B", "P-342", "P-331"]),
    ("both lagged models measured and the two HSC models taken as one",
     dict(lump="by_label"), ["TP-301A", "TP-301B", "P-301A", "P-310B", "P-325A", "P-345A"]),
    ("drained jackets taken as plain pedestals, no blanked pump measured",
     dict(blanked="plain"), ["TP-301A", "TP-301B", "P-301A", "P-304", "P-310A", "K-201B"]),
    ("the lagged pumps left on their 2019 ratio, the spare on a compressor",
     dict(lagged="unchanged"), ["TP-301A", "TP-301B", "P-320A", "P-322", "P-340A", K]),
    ("HSC-250 left unmeasured and given HSC-400's change in ratio", dict(unmeasured="delta"),
     ["TP-301A", "TP-301B", "P-301A", "P-322", "P-340A", K]),
    ("HSC-250 left unmeasured and given HSC-400's ratio scaled by their 2019 ratios", dict(unmeasured="factor"),
     ["TP-301A", "TP-301B", "P-301A", "P-322", "P-340A", K]),
    ("every changed pump left on its 2019 ratio at today's temperature, the visits spent elsewhere",
     dict(unmeasured="rescale"), ["TP-301A", "TP-301B", K, "K-201B", "K-201C", "P-331"]),
    ("a measured support temperature carried to the group as a temperature", dict(transfer="temperature"), None),
    ("a measured rise carried to the group in millimetres", dict(transfer="rise"), None),
    ("no visit ordered: hot checks, and every pump on its 2019 ratio at today's temperature",
     dict(unmeasured="rescale", turbine="hot_check"), []),
]
