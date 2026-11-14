#!/usr/bin/env python3
"""The second ropes.py made fast: python3 ropes.py WORKS_DIR OUT_CSV

It is plain_ropes.py with one function changed, `laid`, and so shares no code with solution/ropes.py or with the
sealed definition; it settles a rope as plain_ropes.py does and counts the bendings in another way again.

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

Counting the bendings. Not movement by movement. In a stretch of the log a station is bent over a sheave by
the movements whose lower height is below the height at which the sheave meets it, less those whose upper height
is below it too. The endurance of RS-4 section 4 is N = 10^c S^q with c and q set by the station's diameter, so
a station needs the sum of S^-q over those movements. The movements are sorted once by lower and once by upper
height, running sums of S^-q are kept for five values of q across the range the stations need, each station
reads its two running sums by bisection, and the five are joined to the station's own q by Lagrange's formula.
The whole of a works takes a second or two.
"""
import bisect
import csv
import math
import os
import sys

import numpy as np

G = 9.80665
TABLE = {"8x36": (-1.214, 0.887, 7.432, -2.103), "6x36": (-1.371, 0.934, 7.518, -2.146)}


def read(path):
    with open(path, newline="") as handle:
        return list(csv.DictReader(handle))


NODES = 5


def laid(crane, moves, first_day, last_day, places, diameters):
    """The damage RS-4 lays, in the movements from first_day up to last_day, on elements at `places`."""
    days = crane["days"]
    a, z = bisect.bisect_left(days, first_day), bisect.bisect_left(days, last_day)
    total = np.zeros(len(places))
    if z <= a:
        return list(total)
    low, high, ln_tension = moves[1][a:z], moves[2][a:z], moves[3][a:z]
    by_low, by_high = np.argsort(low), np.argsort(high)
    low_sorted, high_sorted = low[by_low], high[by_high]
    b0, b1, b2, b3 = crane["b"]
    x = np.asarray(places, float)
    d = np.asarray(diameters, float)
    for D in sorted(set(s[2] for s in crane["sheaves"])):
        ratio = np.log10(D / d)
        q = b1 + b3 * ratio                                    # N = 10^c S^q
        c = b0 + b2 * ratio - 2.0 * q * np.log10(d)
        middle, half = 0.5 * (q.max() + q.min()), max(0.5 * (q.max() - q.min()), 1e-6)
        nodes = middle + half * np.cos(np.pi * (2 * np.arange(NODES) + 1) / (2 * NODES))
        below_low, below_high = [], []
        for node in nodes:
            term = np.exp(-node * ln_tension)
            below_low.append(np.concatenate(([0.0], np.cumsum(term[by_low]))))
            below_high.append(np.concatenate(([0.0], np.cumsum(term[by_high]))))
        lagrange = np.ones((NODES, x.size))
        for j in range(NODES):
            for m in range(NODES):
                if m != j:
                    lagrange[j] *= (q - nodes[m]) / (nodes[j] - nodes[m])
        for parts, offset, D_this, weight in crane["sheaves"]:
            if D_this != D:
                continue
            height = crane["H"] - (crane["L"] - offset - x) / parts
            i_low = np.searchsorted(low_sorted, height, side="left")      # movements with low < height
            i_high = np.searchsorted(high_sorted, height, side="left")    # of those, the ones with high < height too
            summed = np.zeros(x.size)
            for j in range(NODES):
                summed += lagrange[j] * (below_low[j][i_low] - below_high[j][i_high])
            total += weight * 10.0 ** (-c) * summed
    return list(total)


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
    import pandas
    book = pandas.read_csv(os.path.join(works_dir, "movements.csv"), dtype={"crane": str})
    for name, part in book.groupby("crane", sort=False):
        c = facts[name]
        part = part.sort_values("day", kind="stable")
        a, b = part["from_height_m"].to_numpy(float), part["to_height_m"].to_numpy(float)
        tension = (part["hook_load_t"].to_numpy(float) + float(c["block_mass_t"])) * 1000.0 * G / (int(c["falls"]) * float(c["reeving_efficiency"]))
        logs[name] = (part["day"].to_numpy(float), np.minimum(a, b), np.maximum(a, b), np.log(tension))
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
        log = logs.get(name, (np.zeros(0), np.zeros(0), np.zeros(0), np.zeros(0)))
        crane["days"] = list(log[0])
        damage = one_rope(crane, log, days, sheets, stations)
        lines += ["%s-%03d,%.6f" % (name, i + 1, value) for i, value in enumerate(damage)]
    with open(out_csv, "w") as handle:
        handle.write("row,damage\n" + "\n".join(lines) + "\n")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
