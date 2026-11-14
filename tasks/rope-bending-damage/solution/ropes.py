#!/usr/bin/env python3
"""Bending damage along the hoist ropes of one works, to RS-4.

    python3 ropes.py WORKS_DIR OUT_CSV

RS-4 sums damage for a rope element, the piece of rope itself, and gives the result for the element that lies
at each station when the log ends. So before any bending is counted, two things are settled for each rope from
its surveys, because the movement log says nothing about either:

  where each element lay.  A rope's wear pattern stays with the rope. Each survey is laid against the one
      before it twice, as written and end for end. Where end for end fits better, the pattern has changed ends
      between the two.

  what changed ends.  Either the rope was turned end for end on the crane, or the surveyor started from the
      other end of it. Bendings fall where the reeving puts them whichever way the rope lies, so in every run
      of surveys between two such changes the diameter the rope lost is laid against the bendings the log
      gives for the same days, as written and end for end. A run whose loss follows the bendings end for end
      was written from the dead end, and its stations are read from that end. A change with the same reading
      on both sides is a turn of the rope: the elements are followed to where they lay before it. Its day is
      taken half way between the two surveys.

Then RS-4 as it stands: for each movement and each sheave or drum, the elements the point of touch passes,
each with the diameter it had at the last survey not later than the movement.

The counting is a sweep, not a test of every movement against every station. For one sheave the hook height at
which the sheave meets a station rises with the station's place along the rope, so a movement bends a run of
neighbouring stations, found by bisection at both of its ends. Each movement adds its share to a difference
array at the two ends of its run, and one running sum gives every station's total. The share is w / N, and
N = 10^c S^q (section 4) has c and q set by the diameter, which differs from station to station; S^-q is
written as S^-q0 exp(-(q - q0) ln S) about the mean q0 of the stations, and the second factor as a short power
series in ln S, which is exact to a part in a million for the spread of diameters a rope has. So every station
takes five running sums, whatever its diameter.
"""
import csv
import os
import sys

import numpy as np
import pandas as pd

G = 9.80665
CONSTRUCTIONS = {"8x36": (-1.214, 0.887, 7.432, -2.103), "6x36": (-1.371, 0.934, 7.518, -2.146)}
TERMS = 5              # terms of the power series in ln S


class Hoist:
    """One crane: its reeving, its log and what RS-4 makes of a set of movements."""

    def __init__(self, row, sheaves, log):
        self.L = float(row["rope_length_m"])
        self.H = float(row["upper_block_height_m"])
        self.b = CONSTRUCTIONS[row["rope_construction"]]
        self.sheaves = sheaves
        self.day = log["day"].to_numpy(float)
        start, end = log["from_height_m"].to_numpy(float), log["to_height_m"].to_numpy(float)
        self.low, self.high = np.minimum(start, end), np.maximum(start, end)
        tension = ((log["hook_load_t"].to_numpy(float) + float(row["block_mass_t"])) * 1e3 * G
                   / (int(row["falls"]) * float(row["reeving_efficiency"])))
        self.ln_tension = np.log(tension)

    def bendings(self, first_day, last_day, place, diameter):
        """Damage laid between two days on elements lying at `place`, of the given diameters."""
        total = np.zeros(place.size)
        a, z = np.searchsorted(self.day, [first_day, last_day], side="left")
        if z <= a:
            return total
        low, high, ln_s = self.low[a:z], self.high[a:z], self.ln_tension[a:z]
        centre = float(ln_s.mean())
        spread = ln_s - centre
        b0, b1, b2, b3 = self.b
        for parts, offset, D, weight in self.sheaves:
            meets = self.H - (self.L - offset - place) / parts          # hook height with the sheave on the element
            order = np.argsort(meets, kind="stable")
            along = meets[order]
            first = np.searchsorted(along, low, side="right")           # the first station with meets > low
            after = np.searchsorted(along, high, side="right")          # the first station with meets > high
            d = diameter[order]
            ratio = np.log10(D / d)
            q = b1 + b3 * ratio
            c = b0 + b2 * ratio - 2.0 * q * np.log10(d)
            q0 = float(q.mean())
            delta = q - q0
            share = np.exp(-q0 * ln_s)
            series = np.zeros(place.size)
            power = np.ones_like(spread)
            factor = np.ones(place.size)
            for k in range(TERMS):
                if k:
                    power = power * spread
                    factor = factor * (-delta) / k
                runs = np.bincount(first, share * power, place.size + 1) - np.bincount(after, share * power, place.size + 1)
                series += factor * np.cumsum(runs)[:place.size]
            total[order] += weight * 10.0 ** (-c) * np.exp(-delta * centre) * series
        return total


def settle(hoist, days, profile, x):
    """(for each survey whether its stations were counted from the dead end, for each gap between two surveys
    whether the rope was turned in it)."""
    K = len(days)
    changed = []
    for k in range(K - 1):
        as_written = np.sum((profile[k + 1] - profile[k]) ** 2)
        end_for_end = np.sum((profile[k + 1] - profile[k][::-1]) ** 2)
        changed.append(end_for_end < 0.5 * as_written)
    runs, start = [], 0
    for k in range(K - 1):
        if changed[k]:
            runs.append((start, k))
            start = k + 1
    runs.append((start, K - 1))
    from_dead_end = [False] * K
    if len(runs) > 1:
        nominal = np.full(x.size, float(np.median(profile[0])))
        last = False
        for first, final in runs:
            verdict = last
            if final > first:
                lost = profile[first] - profile[final]
                laid = hoist.bendings(days[first], days[final], x, nominal)
                if lost.std() > 0 and laid.std() > 0:
                    verdict = np.corrcoef(lost, laid[::-1])[0, 1] > np.corrcoef(lost, laid)[0, 1]
            for k in range(first, final + 1):
                from_dead_end[k] = verdict
            last = verdict
    turned = [changed[k] and from_dead_end[k] == from_dead_end[k + 1] for k in range(K - 1)]
    return from_dead_end, turned


def rope_damage(hoist, days, profile, x):
    K = len(days)
    from_dead_end, turned = settle(hoist, days, profile, x)
    other_way = [False] * K                 # the rope lay the other way round than at the end of the log
    for k in range(K - 2, -1, -1):
        other_way[k] = other_way[k + 1] != turned[k]
    damage = np.zeros(x.size)
    for k in range(K):
        until = days[k + 1] if k + 1 < K else np.inf
        spans = [(days[k], until, other_way[k])]
        if k + 1 < K and turned[k]:
            half = 0.5 * (days[k] + until)
            spans = [(days[k], half, other_way[k]), (half, until, other_way[k + 1])]
        # the diameter of each element at this survey: the row is reversed once for a rope lying the other way
        # round and once for a survey counted from the dead end
        diameter = profile[k][::-1] if other_way[k] != from_dead_end[k] else profile[k]
        for first_day, last_day, reversed_then in spans:
            damage += hoist.bendings(first_day, last_day, hoist.L - x if reversed_then else x, diameter)
    return damage


def main(works_dir, out_csv):
    cranes = pd.read_csv(os.path.join(works_dir, "cranes.csv"), dtype={"crane": str})
    sheaves = pd.read_csv(os.path.join(works_dir, "sheaves.csv"), dtype={"crane": str})
    moves = pd.read_csv(os.path.join(works_dir, "movements.csv"), dtype={"crane": str})
    surveys = pd.read_csv(os.path.join(works_dir, "surveys.csv"), dtype={"crane": str})
    rows = []
    for _, crane in cranes.iterrows():
        name = crane["crane"]
        reeving = [(int(s["parts"]), float(s["offset_m"]), float(s["diameter_mm"]), float(s["bend_weight"]))
                   for _, s in sheaves[sheaves["crane"] == name].iterrows()]
        log = moves[moves["crane"] == name].sort_values("day", kind="stable")
        mine = surveys[surveys["crane"] == name]
        days = sorted(mine["day"].unique())
        profile = [mine[mine["day"] == day].sort_values("station_m")["diameter_mm"].to_numpy(float) for day in days]
        x = np.sort(mine[mine["day"] == days[-1]]["station_m"].to_numpy(float))
        damage = rope_damage(Hoist(crane, reeving, log), days, profile, x)
        rows += [["%s-%03d" % (name, i + 1), "%.6f" % value] for i, value in enumerate(damage)]
    with open(out_csv, "w", newline="") as handle:
        out = csv.writer(handle)
        out.writerow(["row", "damage"])
        out.writerows(rows)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
