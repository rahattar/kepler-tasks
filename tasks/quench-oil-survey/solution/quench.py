#!/usr/bin/env python3
"""Quench results of a site's loads to HT-5.

    python3 quench.py PACKAGE_DIR OUT_CSV

The oil comes first. HT-5 section 5 takes a load's oil from the charge that was in its tank, and a charge is a
body of oil, not a line of the register: every tank fed from it gives the same cooling-curve analysis, within
what the laboratory repeats. So the tanks of each listed system are sorted into charges by the analyses on
file (charges_of). Charges that were renewed have no analysis yet, and the package's one laboratory order asks
for one sample from each of them. Every load then has its oil: before the renewal the charge's latest analysis
on file, after it the laboratory's figure.

Then the cooling. A site has about two thousand loads and no two need be alike: diameter, steel, furnace and
bath temperature and oil all enter, and the surface coefficient and the steel's properties change with
temperature, so there is nothing to tabulate. What makes it quick is that the loads are marched together.
Every bar is put on the same number of radial intervals and stepped in time in proportion to its own R^2, so
all bars of a steel are rows of one array: one tridiagonal elimination, written out along the radius, advances
them all, and a few hundred growing steps of the trapezoidal rule carry every centre from the furnace
temperature down to 150 C: short steps while any centre is above 500 C, long ones for the tail. The
properties and the surface coefficient are taken at the mid-step temperature by repeated passes.
"""
import csv
import json
import subprocess
import sys

import numpy as np

RHO = 7800.0
PROBE = 14200.0
STEELS = {
    "C45": (((20.0, 300.0, 600.0, 800.0, 900.0), (50.0, 44.0, 34.0, 26.0, 26.0)),
            ((20.0, 300.0, 600.0, 720.0, 800.0, 900.0), (470.0, 560.0, 750.0, 900.0, 650.0, 650.0))),
    "42CrMo4": (((20.0, 300.0, 600.0, 800.0, 900.0), (43.0, 40.0, 33.0, 27.0, 27.0)),
                ((20.0, 300.0, 600.0, 720.0, 800.0, 900.0), (460.0, 550.0, 720.0, 850.0, 640.0, 640.0))),
}
NODES = 32                 # radial intervals
# Time step as a share of R^2 / ALPHA: the first, its growth from step to step, the largest while any centre
# is still above 500 C, and the largest after that, when only the long tail to 150 C is left.
STEP, GROWTH, STEP_MAX, STEP_TAIL = 2.0e-4, 1.04, 2.0e-3, 2.0e-2
PASSES = 3                 # passes over a step, the coefficients taken at the mid-step temperature of the last
ALPHA = 6.0e-6
LEVELS = (800.0, 725.0, 675.0, 500.0, 150.0)


def surface_h(ts, cr_max, t_crmax, cr_300):
    """HT-5 section 4: the oil's heat transfer coefficient at surface temperature ts."""
    h_p = PROBE * cr_max / (t_crmax - 40.0)
    h_3 = PROBE * cr_300 / 260.0
    floor, blanket = 0.6 * h_3, 0.15 * h_p
    convection = floor + (h_3 - floor) * (ts - 100.0) / 200.0
    boiling = h_3 + (h_p - h_3) * (ts - 300.0) / (t_crmax - 300.0)
    collapse = h_p + (blanket - h_p) * (ts - t_crmax) / 120.0
    h = np.where(ts <= 300.0, np.maximum(convection, floor), np.where(ts <= t_crmax, boiling, collapse))
    return np.where(ts >= t_crmax + 120.0, blanket, h)


def cool(steel, radius, furnace, bath, cr_max, t_crmax, cr_300):
    """All loads of one steel at once. Arrays of equal length in; (t85, cr700, dT_max, ts at core 500, t150) out."""
    (kx, ky), (cx, cy) = STEELS[steel]
    count, n = len(radius), NODES
    dr = radius / n
    face = (np.arange(n) + 0.5)[None, :] * dr[:, None]
    volume = np.empty((count, n + 1))
    volume[:, 0] = face[:, 0] ** 2
    volume[:, 1:n] = face[:, 1:] ** 2 - face[:, :-1] ** 2
    volume[:, n] = radius ** 2 - face[:, -1] ** 2
    conduct = 2.0 * face / dr[:, None]
    wetted = 2.0 * radius
    scale = radius ** 2 / ALPHA
    T = np.repeat(furnace[:, None], n + 1, axis=1)
    clock = np.zeros(count)
    reached = {level: np.full(count, np.nan) for level in LEVELS}
    ts500 = np.full(count, np.nan)
    spread = np.zeros(count)
    sub = np.zeros((count, n + 1))
    sup = np.zeros((count, n + 1))
    step = 0
    share = STEP
    while np.isnan(reached[150.0]).any():
        dt = scale * share
        share = min(share * GROWTH, STEP_TAIL if not np.isnan(reached[500.0]).any() else STEP_MAX)
        w = 1.0 if step < 4 else 0.5                    # four backward Euler steps, then the trapezoidal rule
        mid = T
        for _ in range(PASSES):
            store = RHO * np.interp(mid, cx, cy) * volume / dt[:, None]
            link = np.interp(0.5 * (mid[:, 1:] + mid[:, :-1]), kx, ky) * conduct
            loss = surface_h(mid[:, n], cr_max, t_crmax, cr_300) * wetted
            sub[:, 1:] = -w * link
            sup[:, :n] = -w * link
            main = store - sub - sup
            main[:, n] += w * loss
            flow = link * (T[:, 1:] - T[:, :-1])
            right = store * T
            right[:, :n] += (1.0 - w) * flow
            right[:, 1:] -= (1.0 - w) * flow
            right[:, n] += loss * (bath - (1.0 - w) * T[:, n])
            for i in range(1, n + 1):                   # elimination along the radius, every bar at once
                m = sub[:, i] / main[:, i - 1]
                main[:, i] -= m * sup[:, i - 1]
                right[:, i] -= m * right[:, i - 1]
            new = np.empty_like(T)
            new[:, n] = right[:, n] / main[:, n]
            for i in range(n - 1, -1, -1):
                new[:, i] = (right[:, i] - sup[:, i] * new[:, i + 1]) / main[:, i]
            mid = w * new + (1.0 - w) * T
        before, after = T[:, 0], new[:, 0]
        for level in LEVELS:
            crossing = np.isnan(reached[level]) & (before > level) & (after <= level)
            if crossing.any():
                part = (before[crossing] - level) / (before[crossing] - after[crossing])
                reached[level][crossing] = clock[crossing] + part * dt[crossing]
                if level == 500.0:
                    ts500[crossing] = T[crossing, n] + part * (new[crossing, n] - T[crossing, n])
        spread = np.maximum(spread, new[:, 0] - new[:, n])
        clock += dt
        T = new
        step += 1
    return (reached[500.0] - reached[800.0], 50.0 / (reached[675.0] - reached[725.0]), spread, ts500, reached[150.0])


REPEATS = 0.005            # the laboratory repeats a cooling rate within this (site_package.md)
APART = 6 * REPEATS        # two analyses further apart than this are not of one charge


def day_number(text):
    year, month, day = (int(part) for part in text.split("-"))
    return year * 372 + month * 31 + day


def charges_of(tanks, samples):
    """{listed system: [[tanks on one charge], ...]}.

    Two tanks of a listed system hold different charges when the analyses drawn from them nearest in date
    stand further apart than APART in maximum cooling rate: one charge gives one analysis, within the
    laboratory's repeatability and the little it changes between two sample rounds. A tank with no analysis
    on file stays with the first charge of its system.
    """
    listed = {}
    for t in tanks:
        listed.setdefault(t["oil_system"], []).append(t["tank"])
    drawn = {}
    for s in samples:
        drawn.setdefault(s["sampled_at"], []).append((day_number(s["date"]), float(s["cr_max_K_s"])))

    def differ(one, other):
        pairs = [(abs(d1 - d2), v1, v2) for d1, v1 in drawn.get(one, []) for d2, v2 in drawn.get(other, [])]
        if not pairs:
            return False
        nearest = min(gap for gap, _, _ in pairs)
        return all(abs(v1 / v2 - 1.0) > APART for gap, v1, v2 in pairs if gap == nearest)

    charges = {}
    for system, members in listed.items():
        groups = []
        for tank in members:
            for group in groups:
                if not any(differ(tank, other) for other in group):
                    group.append(tank)
                    break
            else:
                groups.append([tank])
        charges[system] = groups
    return charges


def figures(row):
    return float(row["cr_max_K_s"]), float(row["t_crmax_C"]), float(row["cr_300_K_s"])


def main(package, out_csv):
    def table(name):
        with open(package + "/" + name, newline="") as handle:
            return list(csv.DictReader(handle))

    with open(package + "/site.json") as handle:
        site = json.load(handle)
    tanks, log, samples, loads = (table(name) for name in ("tanks.csv", "oil_log.csv", "oil_samples.csv", "loads.csv"))
    renewed = {}                                          # listed system -> date its oil was last renewed
    for job in log:
        if job["work"] == "CHARGE_RENEWED":
            renewed[job["oil_system"]] = max(renewed.get(job["oil_system"], ""), job["date"])
    charge_of = {}                                        # tank -> (listed system, charge number)
    for system, groups in charges_of(tanks, samples).items():
        for number, group in enumerate(groups):
            for tank in group:
                charge_of[tank] = (system, number)

    # The laboratory order: one sample from every charge that was renewed, at the first tank fed from it.
    first = {}
    for t in tanks:
        charge = charge_of[t["tank"]]
        if charge[0] in renewed:
            first.setdefault(charge, t["tank"])
    order = list(first.values())
    if len(order) > int(site["lab_samples"]):
        raise SystemExit("%d renewed charges and an allowance of %s samples" % (len(order), site["lab_samples"]))
    fresh = {}
    if order:
        lab = subprocess.run(["labsample", package] + order, capture_output=True, text=True)
        if lab.returncode != 0:
            raise SystemExit("the laboratory refused the order: " + lab.stdout.strip())
        for row in csv.DictReader(lab.stdout.splitlines()):
            fresh[charge_of[row["sampled_at"]]] = figures(row)

    # The oil on file for every charge: its latest analysis before any renewal, the mean of that date's samples.
    on_file = {}
    for charge in set(charge_of.values()):
        mine = [s for s in samples if charge_of[s["sampled_at"]] == charge
                and (charge[0] not in renewed or s["date"] < renewed[charge[0]])]
        if mine:
            latest = max(s["date"] for s in mine)
            read = [figures(s) for s in mine if s["date"] == latest]
            on_file[charge] = tuple(sum(values) / len(read) for values in zip(*read))

    oils = []
    for p in loads:
        charge = charge_of[p["tank"]]
        oil = fresh[charge] if (charge[0] in renewed and p["date"] > renewed[charge[0]]) else on_file[charge]
        oils.append(oil)
    oils = np.array(oils)
    result = [None] * len(loads)
    for steel in STEELS:
        mine = [i for i, p in enumerate(loads) if p["steel"] == steel]
        if not mine:
            continue
        found = cool(steel, np.array([float(loads[i]["diameter_mm"]) for i in mine]) / 2000.0,
                     np.array([float(loads[i]["furnace_C"]) for i in mine]),
                     np.array([float(loads[i]["bath_C"]) for i in mine]), oils[mine, 0], oils[mine, 1], oils[mine, 2])
        for k, i in enumerate(mine):
            result[i] = tuple(column[k] for column in found)

    with open(out_csv, "w", newline="") as handle:
        out = csv.writer(handle)
        out.writerow(["load", "t85_core_s", "cr700_core_K_s", "dT_max_K", "ts_core500_C", "t150_core_s"])
        for row, (t85, rate, spread, ts500, t150) in zip(loads, result):
            out.writerow([row["load"], "%.3f" % t85, "%.4f" % rate, "%.2f" % spread, "%.2f" % ts500, "%.2f" % t150])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
