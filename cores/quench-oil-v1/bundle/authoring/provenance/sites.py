"""The nine sites: their quench tanks, oil systems, analyses on file, loads, results and laboratory figures.

    python3 sites.py OUT [SITE ...]        (all nine when no site is named)

Everything is written under OUT at the path it has in the bundle, so regenerate.py can compare it with the
shipped files byte for byte:

    environment/data/examples/SITE/    a package and its results (expected.csv)          two sites
    environment/data/pending/SITE/     a package without results                         one site
    environment/rig/sealed/SITE.json   what the laboratory answers for the two examples, where the program is written
    authoring/provenance/pending_lab/SITE.json   what it would answer for the pending site (not installed)
    tests/sites/SITE/                  a package the submitted program is run on         six sites
    tests/sealed/truth/SITE.csv        its results
    tests/lab/sealed/SITE.json         what the laboratory answers for those six

A site is drawn from its seed. The results are quench.py's, for the oil each tank really held.

What is built in on purpose, and where (SITES below is the whole of it):

  * In the two example sites every central system is what the register says, one charge of oil, and every
    charge ages as HT-5 allows. Their laboratory allowance is the number of systems the oil log shows renewed.
  * `split` names a central system that the register lists as one and that is two: its first two tanks are
    fed from one reservoir and its third from another. The two charges gave cooling rates 8.5 to 11 per cent
    apart on every sample date, where two samples of one charge agree within the laboratory's 0.5 per cent,
    and both were renewed at the changeover. That is one charge more to sample than the register shows.
  * `kept` lists the central systems that were not renewed. Their charges age by 0.1 per cent a sample round,
    inside the 0.5 per cent the package format states. `changing` names one of them whose charge is not
    ageing but changing (water getting in): its cooling rates rise 4 to 5.5 per cent a round over the four
    rounds on file, and faster after the last one, so its figures at a load cannot be had from the analyses on
    file. That is one more charge to sample, which the oil log gives no reason to.
  * The laboratory's allowance is the number of charges that need a sample: every renewed charge, and the
    changing one.
  * The pending site (a package without results, which the agent's laboratory does not answer for) has both.
    Of the six sites the submitted program is run on, four have both, one has only the divided system and
    one only the changing charge. Every site with a changing charge has a second kept system, so a sample
    spent on a kept system chosen at random is right one time in two.
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

# name: (seed, role, the central system that is two charges or None, central systems, tanks with their own oil,
#        the central systems kept at the changeover, the kept system whose charge is changing or None)
# Systems are counted from 0. A seed was kept when a divided system's two new charges stand at least 8 per cent
# apart in maximum cooling rate, as its two old ones do by construction (design_rules.py checks it).
SITES = {
    "north_works": (11, "example", None, 3, 1, (2,), None),
    "east_works": (12, "example", None, 4, 2, (3,), None),
    "west_quarry": (51, "pending", 1, 4, 1, (2, 3), 3),
    "quay_site": (37, "hidden", 1, 5, 2, (3, 4), 4),
    "ridge_plant": (50, "hidden", 2, 4, 2, (0, 3), 0),
    "canal_works": (23, "hidden", 0, 5, 1, (4,), None),
    "upper_mill": (44, "hidden", 3, 5, 2, (1, 4), 1),
    "south_yard": (25, "hidden", None, 4, 2, (2, 3), 2),
    "tank_farm": (52, "hidden", 1, 4, 3, (2, 3), 3),
}

# oil type: catalogue CR_max K/s, T_CRmax C, CR_300 K/s
NOMINAL = {"F": (95.0, 600.0, 9.0), "M": (80.0, 580.0, 7.0), "S": (65.0, 560.0, 5.5)}
DIAMETERS = (20, 25, 30, 40, 50, 60, 80, 100)
ROUNDS = ["2024-03-11", "2024-09-09", "2025-03-10", "2025-09-08"]     # the sample rounds on file
CHANGE = "2026-01-19"                                                  # the changeover
DRAWN = "2026-10-05"                                                   # the laboratory's samples are drawn
AGEING = 0.001                     # a charge in service: its cooling rates rise this much a sample round
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
    seed, role, split, n_central, n_single, kept, changing = SITES[name]
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
        systems.append(dict(system="QS-%d" % (s + 1), kind="central", type=kind, renewed=s not in kept,
                            groups=groups, changing=s == changing))
    for _ in range(n_single):
        number += rng.randrange(1, 6)
        tank = "QT-%d" % number
        systems.append(dict(system="OWN-" + tank, kind="single", type=rng.choice(["M", "F"]), renewed=True,
                            groups=[[tank]], changing=False))
    charges, samples = {}, []
    for sy in systems:
        base = rng.uniform(0.94, 1.06)
        for g, members in enumerate(sy["groups"]):
            off = 0.0 if g == 0 else rng.choice([-1, 1]) * rng.uniform(0.085, 0.11)
            if sy["changing"]:
                # water getting in: the cooling rates climb round by round, and faster after the last round
                rise = rng.uniform(0.04, 0.055)
                old = [scaled(NOMINAL[sy["type"]], base * (1 + rise * r)) for r in range(len(ROUNDS))]
                now = scaled(NOMINAL[sy["type"]], base * (1 + rise * (len(ROUNDS) - 1 + rng.uniform(3.5, 4.5))))
            else:
                old = [scaled(NOMINAL[sy["type"]], (base + off) * (1 + AGEING * r)) for r in range(len(ROUNDS))]
                now = scaled(NOMINAL[sy["type"]], (base + off) * (1 + AGEING * (len(ROUNDS) - 1))
                             * (1 + rng.uniform(0.0, AGEING)))
            new = scaled(NOMINAL[sy["type"]],
                         (rng.uniform(0.9, 0.97) if rng.random() < 0.5 else rng.uniform(1.04, 1.12))
                         + (0.0 if g == 0 else -off)) if sy["renewed"] else None
            for tank in members:
                charges[tank] = dict(old=old, new=new, now=new or now, system=sy["system"], group=g)
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
    budget = sum(len(sy["groups"]) for sy in systems if sy["renewed"]) + sum(1 for sy in systems if sy["changing"])
    site = dict(name=name, role=role, systems=systems, tanks=tanks, charges=charges, samples=samples, budget=budget)
    # what the laboratory reports for the oil in each tank on the date its samples are drawn
    site["lab"] = {t["tank"]: charges[t["tank"]]["now"] for t in tanks}
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


def days(text):
    return datetime.date.fromisoformat(text).toordinal()


def oil_of(site, load):
    """The oil the load was really quenched in, by HT-5 section 5."""
    charge = site["charges"][load["tank"]]
    if charge["new"] is not None:
        return charge["new"] if load["date"] > CHANGE else on_file(site, load["tank"])
    # a charge that was not renewed: linear in time from its latest analysis on file to the laboratory's
    last, now = on_file(site, load["tank"]), site["lab"][load["tank"]]
    share = (days(load["date"]) - days(ROUNDS[-1])) / (days(DRAWN) - days(ROUNDS[-1]))
    return tuple(a + share * (b - a) for a, b in zip(last, now))


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
        json.dump(dict(site=name, lab_samples=site["budget"], samples_drawn=DRAWN), handle, indent=1)
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
    book = os.path.join(out, {"example": "environment/rig/sealed", "pending": "authoring/provenance/pending_lab",
                              "hidden": "tests/lab/sealed"}[role], name + ".json")
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
