"""The nine sites: their quench tanks, oil systems, analyses on file, loads, results and laboratory figures.

    python3 sites.py OUT [SITE ...]        (all nine when no site is named)

Everything is written under OUT at the path it has in the bundle, so regenerate.py can compare it with the
shipped files byte for byte:

    environment/data/examples/SITE/    a package and its results (expected.csv)          two sites
    environment/data/pending/SITE/     a package without results                         one site
    environment/rig/sealed/SITE.json   what the laboratory answers for those three
    tests/sites/SITE/                  a package the submitted program is run on         six sites
    tests/sealed/truth/SITE.csv        its results
    tests/lab/sealed/SITE.json         what the laboratory answers for those six

A site is drawn from its seed. The results are quench.py's, for the oil each tank really held.

What is built in on purpose, and where (SITES below is the whole of it):

  * In the two example sites every central system is what the register says: one charge of oil.
  * `split` names a central system that the register lists as one and that is two: its first two tanks are
    fed from one reservoir and its third from another. The two charges gave cooling rates 8.5 to 11 per cent
    apart on every sample date, where two samples of one charge agree within the laboratory's 0.5 per cent,
    and both were renewed at the changeover, so the site's laboratory allowance, which is the number of
    charges that were renewed, is one more than the number of systems the register shows renewed.
  * The pending site (a package without results) has such a system. So do five of the six sites the
    submitted program is run on, in systems of a different number and oil type from site to site; the sixth
    has none.
"""
import csv
import datetime
import json
import os
import random
import sys

import numpy as np

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import quench  # noqa: E402

# name: (seed, role, the central system that is two charges or None, central systems, tanks with their own oil)
# A seed was kept for a site with such a system when the system's two new charges stand at least 8 per cent
# apart in maximum cooling rate, as its two old ones do by construction (design_rules.py checks both).
SITES = {
    "north_works": (11, "example", None, 3, 1),
    "east_works": (12, "example", None, 4, 2),
    "west_quarry": (31, "pending", 1, 4, 1),
    "quay_site": (37, "hidden", 1, 5, 2),
    "ridge_plant": (22, "hidden", 2, 4, 2),
    "canal_works": (23, "hidden", 0, 5, 1),
    "upper_mill": (44, "hidden", 3, 5, 2),
    "south_yard": (25, "hidden", None, 4, 2),
    "tank_farm": (41, "hidden", 1, 4, 3),
}

# oil type: catalogue CR_max K/s, T_CRmax C, CR_300 K/s
NOMINAL = {"F": (95.0, 600.0, 9.0), "M": (80.0, 580.0, 7.0), "S": (65.0, 560.0, 5.5)}
DIAMETERS = (20, 25, 30, 40, 50, 60, 80, 100)
ROUNDS = ["2024-03-11", "2024-09-09", "2025-03-10", "2025-09-08"]     # the sample rounds on file
CHANGE = "2026-01-19"                                                  # the changeover
FIRST, LAST = "2025-10-06", "2026-09-25"                               # the span of the loads
LOADS_PER_TANK = 150
PACKAGE = ("site.json", "tanks.csv", "oil_systems.csv", "oil_log.csv", "oil_samples.csv", "loads.csv")
RESULT_HEADER = ["load"] + list(quench.RESULTS)
FORMATS = ("%.3f", "%.4f", "%.2f", "%.2f", "%.2f")


def day(rng, a, b):
    A, B = datetime.date.fromisoformat(a), datetime.date.fromisoformat(b)
    return (A + datetime.timedelta(days=rng.randrange(1, (B - A).days))).isoformat()


def scaled(nominal, f):
    """A charge as delivered: the type's catalogue figures moved by the factor f on its cooling rates."""
    return (round(nominal[0] * f, 1), round(nominal[1] + 60.0 * (f - 1)), round(nominal[2] * f, 2))


def on_file(site, tank):
    """HT-5 section 5 for a charge that was not renewed, or before it was: the charge's latest analysis, the
    mean of that date's samples."""
    charges, samples = site["charges"], site["samples"]
    mine = {t for t in charges if (charges[t]["system"], charges[t]["group"]) ==
            (charges[tank]["system"], charges[tank]["group"])}
    last = max(s[0] for s in samples if s[1] in mine)
    vals = [(float(s[2]), float(s[3]), float(s[4])) for s in samples if s[0] == last and s[1] in mine]
    return tuple(sum(v[i] for v in vals) / len(vals) for i in range(3))


def describe(name):
    """The site as it is: systems with their true charges, tanks, analyses on file, loads, laboratory figures."""
    seed, role, split, n_central, n_single = SITES[name]
    rng = random.Random(seed)
    systems, tanks = [], []
    number = 100 + 10 * rng.randrange(1, 9)
    for s in range(n_central):
        kind = rng.choice(["M", "M", "F", "S"])
        count = 3 if s == split else rng.choice([2, 3])
        own = []
        for _ in range(count):
            number += rng.randrange(1, 6)
            own.append("QT-%d" % number)
        groups = [own[:2], own[2:]] if s == split else [own]     # the charges the listed system really holds
        renewed = not (s == n_central - 1 and split != s)        # the last central system kept its oil
        systems.append(dict(system="QS-%d" % (s + 1), kind="central", type=kind, renewed=renewed, groups=groups))
    for _ in range(n_single):
        number += rng.randrange(1, 6)
        tank = "QT-%d" % number
        systems.append(dict(system="OWN-" + tank, kind="single", type=rng.choice(["M", "F"]), renewed=True,
                            groups=[[tank]]))
    charges, samples = {}, []
    for sy in systems:
        base = rng.uniform(0.94, 1.06)
        for g, members in enumerate(sy["groups"]):
            off = 0.0 if g == 0 else rng.choice([-1, 1]) * rng.uniform(0.085, 0.11)
            # a charge quenches 0.4 per cent faster from one sample round to the next as it ages
            old = [scaled(NOMINAL[sy["type"]], (base + off) * (1 + 0.004 * r)) for r in range(len(ROUNDS))]
            new = scaled(NOMINAL[sy["type"]],
                         (rng.uniform(0.9, 0.97) if rng.random() < 0.5 else rng.uniform(1.04, 1.12))
                         + (0.0 if g == 0 else -off)) if sy["renewed"] else None
            for tank in members:
                charges[tank] = dict(old=old, new=new, system=sy["system"], group=g)
        members = [t for group in sy["groups"] for t in group]
        for tank in members:
            tanks.append(dict(tank=tank, oil_system=sy["system"], volume=rng.choice([4, 6, 8, 12])))
        # each round: two samples at two different tanks where the system has two, one from each charge where
        # it holds two; every tank is sampled over the rounds
        for r, date in enumerate(ROUNDS):
            if len(sy["groups"]) == 2:
                picks = [sy["groups"][0][r % 2], sy["groups"][1][0]]
            elif len(members) >= 2:
                picks = [members[r % len(members)], members[(r + 1) % len(members)]]
            else:
                picks = [members[0]]
            for tank in picks:
                v = charges[tank]["old"][r]
                jit = rng.choice([-0.1, 0.0, 0.1])
                samples.append((date, tank, "%.1f" % (v[0] + jit), "%d" % v[1], "%.2f" % v[2]))
    samples.sort()
    budget = sum(len(sy["groups"]) for sy in systems if sy["renewed"])
    site = dict(name=name, role=role, systems=systems, tanks=tanks, charges=charges, samples=samples, budget=budget)
    # what the laboratory would report for the oil now in each tank: the new charge where the oil was renewed,
    # and where it was not, what is on file for the charge
    site["lab"] = {}
    for t in tanks:
        now = charges[t["tank"]]["new"]
        if now is None:
            cr, tp, c3 = on_file(site, t["tank"])
            now = (round(cr, 1), round(tp), round(c3, 2))
        site["lab"][t["tank"]] = now
    loads = []
    for t in tanks:
        for n in range(1, LOADS_PER_TANK + 1):
            date = day(rng, FIRST, CHANGE) if rng.random() < 0.35 else day(rng, CHANGE, LAST)
            loads.append(dict(load="%s-%03d" % (t["tank"], n), tank=t["tank"], date=date,
                              steel=rng.choice(sorted(quench.STEELS)), diameter_mm=rng.choice(DIAMETERS),
                              furnace_C=rng.randrange(830, 881, 5), bath_C=rng.randrange(50, 81, 5)))
    loads.sort(key=lambda row: (row["date"], row["load"]))
    site["loads"] = loads
    return site


def oil_of(site, load):
    """The oil the load was really quenched in."""
    charge = site["charges"][load["tank"]]
    if charge["new"] is not None and load["date"] > CHANGE:
        return charge["new"]
    return on_file(site, load["tank"])


def results_of(site):
    """The results to HT-5 of every load, as rows of text in the order of the loads."""
    loads = site["loads"]
    oils = np.array([oil_of(site, load) for load in loads])
    table = [None] * len(loads)
    for steel in sorted(quench.STEELS):
        mine = [i for i, load in enumerate(loads) if load["steel"] == steel]
        found = quench.solve(steel, [loads[i]["diameter_mm"] for i in mine], [loads[i]["furnace_C"] for i in mine],
                             [loads[i]["bath_C"] for i in mine], oils[mine, 0], oils[mine, 1], oils[mine, 2])
        for k, i in enumerate(mine):
            table[i] = [loads[i]["load"]] + [form % found[name][k] for name, form in zip(quench.RESULTS, FORMATS)]
    return table


def table(path, header, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as handle:
        out = csv.writer(handle)
        out.writerow(header)
        out.writerows(rows)


def build(out, name, records_only=False):
    site = describe(name)
    role = site["role"]
    package = os.path.join(out, {"example": "environment/data/examples", "pending": "environment/data/pending",
                                 "hidden": "tests/sites"}[role], name)
    os.makedirs(package, exist_ok=True)
    with open(os.path.join(package, "site.json"), "w") as handle:
        json.dump(dict(site=name, lab_samples=site["budget"]), handle, indent=1)
    table(os.path.join(package, "tanks.csv"), ["tank", "oil_system", "volume_m3"],
          [[t["tank"], t["oil_system"], t["volume"]] for t in site["tanks"]])
    table(os.path.join(package, "oil_systems.csv"), ["oil_system", "kind", "oil_type"],
          [[sy["system"], sy["kind"], "Type " + sy["type"]] for sy in site["systems"]])
    table(os.path.join(package, "oil_log.csv"), ["date", "oil_system", "work", "remarks"],
          [[CHANGE, sy["system"], "CHARGE_RENEWED", "drained, cleaned and refilled, new supplier"]
           for sy in site["systems"] if sy["renewed"]])
    table(os.path.join(package, "oil_samples.csv"), ["date", "sampled_at", "cr_max_K_s", "t_crmax_C", "cr_300_K_s"],
          site["samples"])
    table(os.path.join(package, "loads.csv"), list(site["loads"][0]), [list(row.values()) for row in site["loads"]])
    book = os.path.join(out, "tests/lab/sealed" if role == "hidden" else "environment/rig/sealed", name + ".json")
    os.makedirs(os.path.dirname(book), exist_ok=True)
    with open(book, "w") as handle:
        json.dump(dict(budget=site["budget"], analyses=site["lab"]), handle)
    if role != "pending" and not records_only:
        results = results_of(site)
        if role == "example":
            table(os.path.join(package, "expected.csv"), RESULT_HEADER, results)
        else:
            table(os.path.join(out, "tests/sealed/truth", name + ".csv"), RESULT_HEADER, results)
    print("%-12s %-8s %2d tanks %5d loads  allowance %d, systems the register shows renewed %d" % (
        name, role, len(site["tanks"]), len(site["loads"]), site["budget"],
        sum(1 for sy in site["systems"] if sy["renewed"])), flush=True)


if __name__ == "__main__":
    for site_name in (sys.argv[2:] or list(SITES)):
        build(sys.argv[1], site_name)
