#!/usr/bin/env python3
"""A second ropes.py, written apart from the reference: python3 ropes.py WORKS_DIR OUT_CSV

It shares no code with solution/ropes.py or with the sealed definition, and it takes both of its steps another
way.

Settling a rope. For every gap between two surveys it reckons the bendings RS-4 lays on each place of the rope
in that gap (with the rope as new). Then:
  - a survey mirrors the one before when the absolute differences, station by station, are three times
    smaller end for end than as written;
  - which end the surveys of a stretch were counted from is read from the part of the wear that is not
    alike from both ends: over the gaps of the stretch, the loss of diameter is multiplied by the difference
    between the bendings at a place and at its mirror place, and summed. A positive sum says the wear sits
    where the bendings fall as the stations are written; a negative one, that the stations were counted from
    the other end;
  - a mirrored survey between two stretches counted from the same end is a rope turned end for end, put at
    the middle of the gap.

Counting the bendings. Plainly: movement by movement, sheave by sheave, station by station, the endurance
worked out afresh for each bending. This is the calculation exactly as RS-4 words it, and it is slow.
"""
import csv
import math
import os
import sys

G = 9.80665
TABLE = {"8x36": (-1.214, 0.887, 7.432, -2.103), "6x36": (-1.371, 0.934, 7.518, -2.146)}


def read(path):
    with open(path, newline="") as handle:
        return list(csv.DictReader(handle))


def laid(crane, moves, first_day, last_day, places, diameters):
    """The damage RS-4 lays, in the movements from first_day up to last_day, on elements at `places`."""
    b0, b1, b2, b3 = crane["b"]
    total = [0.0] * len(places)
    for day, low, high, tension in moves:
        if day < first_day or day >= last_day:
            continue
        for parts, offset, D, weight in crane["sheaves"]:
            for i, x in enumerate(places):
                height = crane["H"] - (crane["L"] - offset - x) / parts
                if low < height <= high:
                    d = diameters[i]
                    ratio = math.log10(D / d)
                    lgN = b0 + (b1 + b3 * ratio) * math.log10(tension / (d * d)) + b2 * ratio
                    total[i] += weight / 10.0 ** lgN
    return total


def settle(crane, moves, days, sheets, stations):
    """(counted_from_dead_end for each survey, turned for each gap)."""
    count = len(days)
    new = sorted(sheets[0])[len(stations) // 2]
    as_new = [new] * len(stations)
    mirrored = []
    for g in range(count - 1):
        straight = sum(abs(b - a) for a, b in zip(sheets[g], sheets[g + 1]))
        flipped = sum(abs(b - a) for a, b in zip(reversed(sheets[g]), sheets[g + 1]))
        mirrored.append(3.0 * flipped < straight)
    stretches, begin = [], 0
    for g in range(count - 1):
        if mirrored[g]:
            stretches.append((begin, g))
            begin = g + 1
    stretches.append((begin, count - 1))
    from_dead_end = [False] * count
    if len(stretches) > 1:
        previous = False
        for begin, end in stretches:
            reading = previous
            if end > begin:
                bent = laid(crane, moves, days[begin], days[end], stations, as_new)
                lost = [a - b for a, b in zip(sheets[begin], sheets[end])]
                lopsided = sum(l * (b - m) for l, b, m in zip(lost, bent, reversed(bent)))
                reading = lopsided < 0
            for k in range(begin, end + 1):
                from_dead_end[k] = reading
            previous = reading
    turned = [mirrored[g] and from_dead_end[g] == from_dead_end[g + 1] for g in range(count - 1)]
    return from_dead_end, turned


def one_rope(crane, moves, days, sheets, stations):
    count = len(days)
    from_dead_end, turned = settle(crane, moves, days, sheets, stations)
    lay = [0] * count                     # 1 where the rope lay the other way round than at the end
    for g in range(count - 2, -1, -1):
        lay[g] = lay[g + 1] ^ int(turned[g])
    damage = [0.0] * len(stations)
    mirror_places = [crane["L"] - x for x in stations]
    for k in range(count):
        end = days[k + 1] if k + 1 < count else float("inf")
        pieces = [(days[k], end, lay[k])]
        if k + 1 < count and turned[k]:
            middle = (days[k] + end) / 2.0
            pieces = [(days[k], middle, lay[k]), (middle, end, lay[k + 1])]
        sheet = list(reversed(sheets[k])) if lay[k] ^ int(from_dead_end[k]) else sheets[k]
        for first_day, last_day, other_way in pieces:
            part = laid(crane, moves, first_day, last_day, mirror_places if other_way else stations, sheet)
            damage = [a + b for a, b in zip(damage, part)]
    return damage


def main(works_dir, out_csv):
    sheaves, logs, surveys = {}, {}, {}
    for row in read(os.path.join(works_dir, "sheaves.csv")):
        sheaves.setdefault(row["crane"], []).append((int(row["parts"]), float(row["offset_m"]),
                                                     float(row["diameter_mm"]), float(row["bend_weight"])))
    cranes = read(os.path.join(works_dir, "cranes.csv"))
    facts = {c["crane"]: c for c in cranes}
    for row in read(os.path.join(works_dir, "movements.csv")):
        c = facts[row["crane"]]
        a, b = float(row["from_height_m"]), float(row["to_height_m"])
        tension = (float(row["hook_load_t"]) + float(c["block_mass_t"])) * 1000.0 * G / (int(c["falls"]) * float(c["reeving_efficiency"]))
        logs.setdefault(row["crane"], []).append((float(row["day"]), min(a, b), max(a, b), tension))
    for row in read(os.path.join(works_dir, "surveys.csv")):
        surveys.setdefault(row["crane"], {}).setdefault(float(row["day"]), []).append((float(row["station_m"]), float(row["diameter_mm"])))
    lines = []
    for c in cranes:
        name = c["crane"]
        crane = {"L": float(c["rope_length_m"]), "H": float(c["upper_block_height_m"]),
                 "b": TABLE[c["rope_construction"]], "sheaves": sheaves[name]}
        days = sorted(surveys[name])
        sheets = [[d for _, d in sorted(surveys[name][day])] for day in days]
        stations = [x for x, _ in sorted(surveys[name][days[-1]])]
        damage = one_rope(crane, logs.get(name, []), days, sheets, stations)
        lines += ["%s-%03d,%.6f" % (name, i + 1, value) for i, value in enumerate(damage)]
    with open(out_csv, "w") as handle:
        handle.write("row,damage\n" + "\n".join(lines) + "\n")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
