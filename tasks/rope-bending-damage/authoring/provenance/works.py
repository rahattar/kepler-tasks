"""The generator: nine works, their cranes, movement logs and rope surveys, written as packages.

    python3 works.py                 writes every package and every sealed result into the bundle
    python3 works.py melt_hall ...   only the works named

`WORKS` is the table of what each works is: its role, how many cranes it has and what has happened to its ropes
that no record says.

  turned      ropes turned end for end at a time between two surveys;
  dead_end    ropes whose surveys, from one survey on, were taken from the dead end and written down as if from
              the drum anchorage; the rope itself was never touched;
  both        ropes surveyed from the dead end from one survey on and, at least four surveys later, turned end
              for end;
  eight       cranes reeved on eight falls;
  tall        cranes with the upper block above 29 m (every visible crane is below 28 m).

The two examples, the works whose results go out with the task, are sound. The pending works, which goes out
without results, has one rope of each of the first two kinds. Five of the six works the program is run on have
them in other numbers, at other surveys and on other cranes, one of them has a rope of the third kind, and one
is sound.

A package is written the way a works writes it: the log as the controller has it, each survey as the surveyor
wrote it down. The result of a package is the damage `rope.life` gives for the element at each station, counted
from the drum anchorage as the rope lies at the end of the log.
"""
import csv
import json
import os
import sys

import numpy as np

sys.dont_write_bytecode = True
import rope  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
BUNDLE = os.path.dirname(os.path.dirname(HERE))
DAYS = 300.0
SPACING = 1.0                    # metres between survey stations
SURVEYS = 20
PLACE = {"example": "environment/data/examples", "pending": "environment/data/pending", "hidden": "tests/works"}
SEALED = {"pending": "authoring/provenance/pending_results", "hidden": "tests/sealed/results"}

WORKS = [
    dict(works="forge_bay", role="example", seed=51, tag="FB", cranes=5, turned=0, dead_end=0, both=0, eight=1, tall=0),
    dict(works="plate_shop", role="example", seed=52, tag="PS", cranes=5, turned=0, dead_end=0, both=0, eight=1, tall=0),
    dict(works="melt_hall", role="pending", seed=53, tag="MH", cranes=5, turned=1, dead_end=1, both=0, eight=1, tall=0),
    dict(works="roll_store", role="hidden", seed=61, tag="RS", cranes=6, turned=1, dead_end=1, both=0, eight=2, tall=2),
    dict(works="press_line", role="hidden", seed=62, tag="PL", cranes=6, turned=1, dead_end=1, both=0, eight=2, tall=1),
    dict(works="coil_yard", role="hidden", seed=63, tag="CY", cranes=6, turned=0, dead_end=0, both=0, eight=1, tall=2),
    dict(works="ladle_aisle", role="hidden", seed=64, tag="LA", cranes=6, turned=1, dead_end=2, both=0, eight=3, tall=2),
    dict(works="die_store", role="hidden", seed=65, tag="DS", cranes=6, turned=0, dead_end=1, both=1, eight=1, tall=1),
    dict(works="scrap_bay", role="hidden", seed=66, tag="SB", cranes=6, turned=2, dead_end=1, both=0, eight=2, tall=3),
]
BAND = 0.08                      # the accuracy asked of a result, as a share of the rope's greatest damage


def millimetres(value):
    """An offset as taped to the millimetre. Hook heights are logged to the centimetre; an offset that is not on
    that grid means no movement ends with a sheave exactly on a station."""
    k = int(round(value * 1000))
    return (k + 3 if k % 10 == 0 else k) / 1000.0


def make_crane(rng, name, eight, tall):
    falls = 8 if eight else int(rng.choice([2, 4, 4, 6]))
    H = float(round(rng.uniform(29.3, 42.7) if tall else rng.uniform(11.4, 27.6), 1))
    d = float(rng.choice([16.0, 18.0, 20.0, 22.0, 24.0, 26.0]))
    construction = str(rng.choice(sorted(rope.ROPE)))
    rated = float(round(0.118 * d * d * falls * rng.uniform(0.82, 1.07) / rope.G, 1))     # t, about a fifth of the rope's strength
    block = float(round(rated * rng.uniform(0.035, 0.06), 2))
    D_sheave = float(round(d * rng.uniform(24.3, 29.6), 0))
    D_drum = float(round(d * rng.uniform(22.2, 26.8), 0))
    first = float(round(rng.uniform(1.13, 1.87), 2))
    step = float(round(rng.uniform(0.93, 1.38), 2))
    sheaves = [dict(name="S%d" % p, parts=p, offset=millimetres(first + step * (p - 1)), D=D_sheave, weight=1.0)
               for p in range(1, falls)]
    sheaves.append(dict(name="drum", parts=falls, offset=millimetres(first + step * (falls - 1) + rng.uniform(3.7, 8.9)),
                        D=D_drum, weight=0.5))
    need = sheaves[-1]["offset"] + falls * (H - 0.4) + rng.uniform(9.0, 17.0)
    L = float(2 * SPACING * np.ceil(need / (2 * SPACING)))
    return dict(crane=name, falls=falls, H=H, d=d, construction=construction, rated=rated, block=block,
                eff=float(round(rng.uniform(0.93, 0.975), 3)), sheaves=sheaves, L=L, spacing=SPACING)


def make_log(rng, crane, busy):
    """A crane's movements over the log: lifts between a pick-up height, the top of the lift and a few set-down
    heights, with the short moves of placing the hook and the load. Rows: day, from, to, hook load (t)."""
    H = crane["H"]
    pick = rng.uniform(0.6, 1.6)
    travel = H * rng.uniform(0.58, 0.83) - 1.0
    sets = np.sort(rng.uniform(0.8, max(2.0, 0.45 * H), 3))
    rate = busy * rng.uniform(42, 62)                               # lifts a day
    t, h, rows = 0.0, travel, []

    def move(to, load):
        nonlocal h, t
        to = float(np.clip(to, 0.45, H - 2.05))
        if abs(to - h) > 0.03:
            rows.append((t, h, to, load))
            h = to
            t += 0.0003

    while True:
        t += 0.0006 + rng.exponential(1.0 / rate)
        if t >= DAYS:
            break
        heavy = rng.random() < 0.85
        load = crane["rated"] * (rng.uniform(0.16, 0.62) if heavy else rng.uniform(0.03, 0.16))
        move(pick + abs(rng.normal(0, 0.12)), 0.0)
        for _ in range(rng.poisson(1.0)):
            move(h + rng.choice([-1, 1]) * rng.uniform(0.04, 0.35), 0.0)
        move(travel + rng.normal(0, 0.35) if rng.random() < 0.9 else rng.uniform(travel, H - 2.1), load)
        move(float(rng.choice(sets)) + abs(rng.normal(0, 0.2)), load)
        for _ in range(rng.poisson(1.4)):
            move(h + rng.choice([-1, 1]) * rng.uniform(0.04, 0.35), load)
        move(travel + rng.normal(0, 0.3), 0.0)
    log = np.array(rows)
    log[:, 0] = np.round(log[:, 0], 4)                              # as the controller writes them
    log[:, 1:] = np.round(log[:, 1:], 2)
    return log


def draw(spec, seed_shift=0, busy=1.0):
    """Everything about a works that the packages are written from: (survey days, cranes). Each crane carries
    its log, the damage of its elements, the diameters every survey read, and what was done to its rope."""
    rng = np.random.default_rng(spec["seed"] + 1000 * seed_shift)
    n = spec["cranes"]
    on_eight = set(int(i) for i in rng.permutation(n)[:spec["eight"]])
    is_tall = set(int(i) for i in rng.permutation(n)[:spec["tall"]])
    order = [int(i) for i in rng.permutation(n)]
    kind = {}
    for what in ("turned", "dead_end", "both"):
        for _ in range(spec[what]):
            kind[order.pop(0)] = what
    survey_days = [0.0] + [float(v) for v in np.round(np.cumsum(rng.uniform(12.7, 17.9, SURVEYS - 1)), 2)]
    survey_days = [s for s in survey_days if s < DAYS - 5]
    cranes = []
    for i in range(n):
        what = kind.get(i, "sound")
        for _ in range(400):
            crane = make_crane(rng, "%s-%d" % (spec["tag"], i + 1), i in on_eight, i in is_tall)
            log = make_log(rng, crane, busy)
            turn_day, first_reversed = None, None
            if what == "turned":
                k = int(rng.integers(7, 13))
                turn_day = float(round(rng.uniform(survey_days[k] + 2.3, survey_days[k + 1] - 2.3), 2))
            elif what == "dead_end":
                first_reversed = int(rng.integers(8, 14))
            elif what == "both":
                first_reversed = int(rng.integers(5, 8))
                k = first_reversed + int(rng.integers(3, 6))
                turn_day = float(round(rng.uniform(survey_days[k] + 2.3, survey_days[k + 1] - 2.3), 2))
            wear_seed = int(rng.integers(1, 2 ** 31))
            damage, readings = rope.life(crane, log, survey_days, DAYS, turn_day, wear_seed)
            top = damage.max()
            matters = True
            if turn_day is not None:
                # the turn has to matter: read as if the rope had never been turned, several stations are well out
                unturned, _ = rope.life(crane, log, survey_days, DAYS, None, wear_seed)
                matters = matters and (np.abs(unturned - damage) > 2.5 * BAND * top).sum() >= 8
            if first_reversed is not None:
                # the end a survey starts from has to matter: the rope must not be alike from both ends
                matters = matters and (np.abs(damage - damage[::-1]) > 2.5 * BAND * top).sum() >= 12
            # and it has to be plain in the surveys: the survey after it fits the one before at least five times
            # better end for end than as written
            trial = dict(crane, readings=readings, turn_day=turn_day, first_reversed=first_reversed)
            for gap in ([k] if turn_day is not None else []) + ([first_reversed - 1] if first_reversed is not None else []):
                earlier = as_written(trial, gap, survey_days[gap])
                later = as_written(trial, gap + 1, survey_days[gap + 1])
                matters = matters and np.sum((later - earlier[::-1]) ** 2) < 0.2 * np.sum((later - earlier) ** 2)
            if matters and 0.08 * busy <= top <= 0.7 * busy:
                break
        else:
            raise SystemExit("no crane found for %s, crane %d" % (spec["works"], i + 1))
        crane.update(log=log, damage=damage, readings=readings, what=what, turn_day=turn_day,
                     dead_end_from=None if first_reversed is None else survey_days[first_reversed],
                     first_reversed=first_reversed)
        cranes.append(crane)
    return survey_days, cranes


def as_written(crane, k, survey_day):
    """The diameters of survey k in the order the surveyor wrote them down."""
    row = crane["readings"][k]
    if crane["turn_day"] is not None and survey_day < crane["turn_day"]:
        row = row[::-1]                     # the rope lay the other way round
    if crane["first_reversed"] is not None and k >= crane["first_reversed"]:
        row = row[::-1]                     # the surveyor started from the dead end
    return row


def build(spec, root=BUNDLE, seed_shift=0, busy=1.0, place=None, sealed=None):
    """Writes one works' package under root, and its results where its role keeps them."""
    survey_days, cranes = draw(spec, seed_shift, busy)
    folder = os.path.join(root, place or PLACE[spec["role"]], spec["works"])
    os.makedirs(folder, exist_ok=True)

    def table(name, header, rows, where=folder):
        with open(os.path.join(where, name), "w", newline="") as handle:
            out = csv.writer(handle, lineterminator="\n")
            out.writerow(header)
            out.writerows(rows)

    table("cranes.csv", ["crane", "falls", "upper_block_height_m", "block_mass_t", "reeving_efficiency",
                         "rope_construction", "rope_length_m"],
          [[c["crane"], c["falls"], c["H"], c["block"], c["eff"], c["construction"], "%.0f" % c["L"]] for c in cranes])
    table("sheaves.csv", ["crane", "sheave", "parts", "offset_m", "diameter_mm", "bend_weight"],
          [[c["crane"], s["name"], s["parts"], "%.3f" % s["offset"], "%.0f" % s["D"], s["weight"]]
           for c in cranes for s in c["sheaves"]])
    table("movements.csv", ["crane", "day", "from_height_m", "to_height_m", "hook_load_t"],
          [[c["crane"], "%.4f" % r[0], "%.2f" % r[1], "%.2f" % r[2], "%.2f" % r[3]] for c in cranes for r in c["log"]])
    stations = {c["crane"]: c["spacing"] * (0.5 + np.arange(c["damage"].size)) for c in cranes}
    table("surveys.csv", ["crane", "day", "station_m", "diameter_mm"],
          [[c["crane"], "%.2f" % day, "%.2f" % x, "%.2f" % d]
           for c in cranes for k, day in enumerate(survey_days)
           for x, d in zip(stations[c["crane"]], as_written(c, k, day))])
    results = [["%s-%03d" % (c["crane"], i + 1), "%.5f" % v] for c in cranes for i, v in enumerate(c["damage"])]
    if spec["role"] == "example":
        table("expected.csv", ["row", "damage"], results)
    else:
        where = os.path.join(root, sealed or SEALED[spec["role"]])
        os.makedirs(where, exist_ok=True)
        table(spec["works"] + ".csv", ["row", "damage"], results, where)
    return dict(works=spec["works"], role=spec["role"], survey_days=survey_days, rows=len(results),
                movements=int(sum(len(c["log"]) for c in cranes)),
                cranes=[dict(crane=c["crane"], falls=c["falls"], upper_block_height_m=c["H"], rope_length_m=c["L"],
                             rope_diameter_mm=c["d"], construction=c["construction"], stations=int(c["damage"].size),
                             movements=int(len(c["log"])), greatest_damage=round(float(c["damage"].max()), 4),
                             rope=c["what"], turn_day=c["turn_day"], surveyed_from_dead_end_since_day=c["dead_end_from"])
                       for c in cranes])


def spec_of(name):
    return next(w for w in WORKS if w["works"] == name)


if __name__ == "__main__":
    for which in (sys.argv[1:] or [w["works"] for w in WORKS]):
        made = build(spec_of(which))
        print(json.dumps({k: v for k, v in made.items() if k != "cranes"}))
        for c in made["cranes"]:
            print("   ", json.dumps(c))
