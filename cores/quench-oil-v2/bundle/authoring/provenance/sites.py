"""The nine sites: their quench tanks, oil systems, analyses and test bars on file, loads, results and laboratory figures.

    python3 sites.py OUT [SITE ...]        (all nine when no site is named)

Everything is written under OUT at the path it has in the bundle, so regenerate.py can compare it with the
shipped files byte for byte:

    environment/data/examples/SITE/    a package and its results (expected.csv)          two sites
    environment/data/pending/SITE/     a package without results                         one site
    environment/rig/sealed/SITE.json   what the laboratory answers for the two examples, where the program is written
    authoring/provenance/pending_lab/SITE.json   what it would answer for the pending site (installed nowhere)
    tests/sites/SITE/                  a package the submitted program is run on         six sites
    tests/sealed/truth/SITE.csv        its results
    tests/lab/sealed/SITE.json         what the laboratory answers for those six

A site is drawn from its seed. Its results, and its test bars, are quench.py's for the oil each tank really held
(HT-5 section 5) and the agitation it really had (section 4).

What is built in on purpose, and where (SITES below is the whole of it):

  * Every listed oil system is one charge of oil. The laboratory analysed the charges in four six-monthly
    rounds up to September 2025; most systems were renewed in January 2026; `kept` lists the central systems
    that were not.
  * `changing` names a kept system whose charge stopped ageing and started changing after the last round
    (water getting in): by the date the laboratory draws its samples its cooling rates are 12 to 20 per cent
    above its latest analysis. Nothing in the analyses on file shows it. Its tanks' test bars do: run through
    HT-5 with the oil on file, they come out progressively too slow, month by month. By section 5 its figures
    at a load need an analysis on the date the samples are drawn, which the oil log gives no reason to order.
  * `stopped` names a tank with its own oil whose propeller agitator, which the register records, has not run
    over the year of loads. By section 4 its coefficient is the oil's alone. Nothing but its test bars shows it:
    run through HT-5 with its oil and the register's agitation they come out far too fast, and with still oil
    they fit.
  * The laboratory's allowance is the number of charges that need an analysis: every renewed charge, and the
    changing one. A stopped agitator needs none.
  * In the two example sites neither is the case. The pending site has both. Of the six sites the submitted
    program is run on, three have both, two only a stopped agitator and one only a changing charge. Every site
    with a changing charge has a second kept system, so an analysis spent on a kept system chosen at random is
    right one time in two.
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

# name: (seed, role, central systems, tanks with their own oil, the central systems kept at the changeover,
#        the kept system whose charge is changing or None, the own-oil tank whose agitator stopped or None)
# Systems and own-oil tanks are counted from 0.
SITES = {
    "north_works": (11, "example", 3, 1, (2,), None, None),
    "east_works": (12, "example", 4, 2, (3,), None, None),
    "west_quarry": (51, "pending", 4, 2, (2, 3), 3, 1),
    "quay_site": (37, "hidden", 5, 2, (3, 4), 4, 0),
    "ridge_plant": (50, "hidden", 4, 2, (0, 3), 0, 1),
    "canal_works": (23, "hidden", 5, 2, (4,), None, 1),
    "upper_mill": (44, "hidden", 5, 3, (1, 4), 1, 2),
    "south_yard": (25, "hidden", 4, 2, (2, 3), 2, None),
    "tank_farm": (52, "hidden", 4, 3, (2, 3), None, 0),
}

# oil type: catalogue CR_max K/s, T_CRmax C, CR_300 K/s
NOMINAL = {"F": (95.0, 600.0, 9.0), "M": (80.0, 580.0, 7.0), "S": (65.0, 560.0, 5.5)}
PROPELLER = 1.35                   # HT-5 section 4: the agitation factor of a running propeller agitator
DIAMETERS = (20, 25, 30, 40, 50, 60, 80, 100)
TEST_BARS = (20, 25, 30)           # the shop's test pieces, C45 with a thermocouple at the centre
ROUNDS = ["2024-03-11", "2024-09-09", "2025-03-10", "2025-09-08"]     # the sample rounds on file
CHANGE = "2026-01-19"                                                  # the changeover
DRAWN = "2026-10-05"                                                   # the laboratory's samples are drawn
FIRST, LAST = "2025-10-06", "2026-09-25"                               # the span of the loads and test bars
AGEING = 0.001                     # a charge in service: its cooling rates rise this much a sample round
LOADS_PER_TANK = 150
PACKAGE = ("site.json", "tanks.csv", "oil_systems.csv", "oil_log.csv", "oil_samples.csv", "test_bars.csv",
           "loads.csv")
RESULT_HEADER = ["load"] + list(quench.RESULTS)
FORMATS = ("%.3f", "%.4f", "%.2f", "%.2f", "%.2f")


def days(text):
    return datetime.date.fromisoformat(text).toordinal()


def day(rng, a, b):
    A, B = datetime.date.fromisoformat(a), datetime.date.fromisoformat(b)
    while True:
        out = (A + datetime.timedelta(days=rng.randrange(1, (B - A).days))).isoformat()
        if out != CHANGE:
            return out


def scaled(nominal, f):
    """A charge as delivered: the type's catalogue figures moved by the factor f on its cooling rates."""
    return (round(nominal[0] * f, 1), round(nominal[1] + 60.0 * (f - 1)), round(nominal[2] * f, 2))


def on_file(site, tank):
    """The charge's latest analysis on file: the mean of that date's samples."""
    charges, samples = site["charges"], site["samples"]
    mine = {t for t in charges if charges[t]["system"] == charges[tank]["system"]}
    last = max(s[0] for s in samples if s[1] in mine)
    vals = [(float(s[2]), float(s[3]), float(s[4])) for s in samples if s[0] == last and s[1] in mine]
    return tuple(sum(v[i] for v in vals) / len(vals) for i in range(3))


def describe(name):
    """The site as it is: systems, tanks and their agitators, analyses on file, laboratory figures, loads."""
    seed, role, n_central, n_single, kept, changing, stopped = SITES[name]
    rng = random.Random(seed)
    systems, tanks = [], []
    number = 100 + 10 * rng.randrange(1, 9)
    for s in range(n_central):
        kind = rng.choice(["M", "M", "F", "S"])
        own = []
        for _ in range(rng.choice([2, 3])):
            number += rng.randrange(1, 6)
            own.append("QT-%d" % number)
        systems.append(dict(system="QS-%d" % (s + 1), kind="central", type=kind, renewed=s not in kept,
                            changing=s == changing, tanks=own, stopped=False))
    for s in range(n_single):
        number += rng.randrange(1, 6)
        tank = "QT-%d" % number
        systems.append(dict(system="OWN-" + tank, kind="single", type=rng.choice(["M", "F"]), renewed=True,
                            changing=False, tanks=[tank], stopped=s == stopped))
    charges, samples = {}, []
    for sy in systems:
        base = rng.uniform(0.94, 1.06)
        old = [scaled(NOMINAL[sy["type"]], base * (1 + AGEING * r)) for r in range(len(ROUNDS))]
        if sy["changing"]:      # water getting in since the last round
            now = scaled(NOMINAL[sy["type"]], base * (1 + AGEING * (len(ROUNDS) - 1)) * (1 + rng.uniform(0.12, 0.2)))
        else:                   # ageing: the cooling rates a little higher, T_CRmax where it was
            u = rng.uniform(0.0, AGEING)
            now = (round(old[-1][0] * (1 + u), 1), old[-1][1], round(old[-1][2] * (1 + u), 2))
        new = scaled(NOMINAL[sy["type"]], rng.uniform(0.9, 0.97) if rng.random() < 0.5 else rng.uniform(1.04, 1.12)) \
            if sy["renewed"] else None
        for tank in sy["tanks"]:
            charges[tank] = dict(old=old, new=new, now=new or now, system=sy["system"])
            stir = "propeller" if sy["stopped"] else rng.choice(["propeller", "propeller", "none"])
            tanks.append(dict(tank=tank, oil_system=sy["system"], volume=rng.choice([4, 6, 8, 12]), agitation=stir,
                              runs=PROPELLER if stir == "propeller" and not sy["stopped"] else 1.0))
        # each round: two samples at two different tanks where the system has two or more
        members = sy["tanks"]
        for r, date in enumerate(ROUNDS):
            picks = [members[r % len(members)], members[(r + 1) % len(members)]] if len(members) >= 2 else [members[0]]
            for tank in picks:
                v = old[r]
                samples.append((date, tank, "%.1f" % (v[0] + rng.choice([-0.1, 0.0, 0.1])), "%d" % v[1], "%.2f" % v[2]))
    samples.sort()
    budget = sum(1 for sy in systems if sy["renewed"]) + sum(1 for sy in systems if sy["changing"])
    site = dict(name=name, role=role, systems=systems, tanks=tanks, charges=charges, samples=samples, budget=budget)
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
    bars = []
    start = datetime.date.fromisoformat(FIRST)
    for t in tanks:
        for month in range(12):
            first = datetime.date(start.year + (start.month + month - 1) // 12, (start.month + month - 1) % 12 + 1, 1)
            date = (first + datetime.timedelta(days=rng.randrange(2, 27))).isoformat()
            if date == CHANGE:
                date = (first + datetime.timedelta(days=1)).isoformat()
            bars.append(dict(date=date, tank=t["tank"], steel="C45", diameter_mm=rng.choice(TEST_BARS),
                             furnace_C=rng.randrange(840, 861, 5), bath_C=rng.randrange(50, 81, 5),
                             error=rng.uniform(-0.004, 0.004)))
    bars.sort(key=lambda row: (row["date"], row["tank"]))
    site["bars"] = bars
    return site


def oil_of(site, row):
    """The oil a load or test bar was really quenched in, by HT-5 section 5."""
    charge = site["charges"][row["tank"]]
    if charge["new"] is not None:
        return charge["new"] if row["date"] > CHANGE else on_file(site, row["tank"])
    last, now = on_file(site, row["tank"]), site["lab"][row["tank"]]
    share = (days(row["date"]) - days(ROUNDS[-1])) / (days(DRAWN) - days(ROUNDS[-1]))
    return tuple(a + share * (b - a) for a, b in zip(last, now))


def cooled(site, rows):
    """quench.solve for rows of loads or test bars, each with its real oil and agitation; {name: array}."""
    runs = {t["tank"]: t["runs"] for t in site["tanks"]}
    oils = np.array([oil_of(site, row) for row in rows])
    out = {name: np.empty(len(rows)) for name in quench.RESULTS}
    for steel in sorted(quench.STEELS):
        mine = [i for i, row in enumerate(rows) if row["steel"] == steel]
        if not mine:
            continue
        found = quench.solve(steel, [rows[i]["diameter_mm"] for i in mine], [rows[i]["furnace_C"] for i in mine],
                             [rows[i]["bath_C"] for i in mine], oils[mine, 0], oils[mine, 1], oils[mine, 2],
                             [runs[rows[i]["tank"]] for i in mine])
        for name in quench.RESULTS:
            out[name][mine] = found[name]
    return out


def table(path, header, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as handle:
        out = csv.writer(handle)
        out.writerow(header)
        out.writerows(rows)


def build(out, name):
    site = describe(name)
    role = site["role"]
    package = os.path.join(out, {"example": "environment/data/examples", "pending": "environment/data/pending",
                                 "hidden": "tests/sites"}[role], name)
    os.makedirs(package, exist_ok=True)
    with open(os.path.join(package, "site.json"), "w") as handle:
        json.dump(dict(site=name, lab_samples=site["budget"], samples_drawn=DRAWN), handle, indent=1)
    table(os.path.join(package, "tanks.csv"), ["tank", "oil_system", "volume_m3", "agitation"],
          [[t["tank"], t["oil_system"], t["volume"], t["agitation"]] for t in site["tanks"]])
    table(os.path.join(package, "oil_systems.csv"), ["oil_system", "kind", "oil_type"],
          [[sy["system"], sy["kind"], "Type " + sy["type"]] for sy in site["systems"]])
    table(os.path.join(package, "oil_log.csv"), ["date", "oil_system", "work", "remarks"],
          [[CHANGE, sy["system"], "CHARGE_RENEWED", "drained, cleaned and refilled, new supplier"]
           for sy in site["systems"] if sy["renewed"]])
    table(os.path.join(package, "oil_samples.csv"), ["date", "sampled_at", "cr_max_K_s", "t_crmax_C", "cr_300_K_s"],
          site["samples"])
    bars = cooled(site, site["bars"])["t85_core_s"]
    table(os.path.join(package, "test_bars.csv"), ["date", "tank", "steel", "diameter_mm", "furnace_C", "bath_C",
                                                   "t85_core_s"],
          [[b["date"], b["tank"], b["steel"], b["diameter_mm"], b["furnace_C"], b["bath_C"],
            "%.2f" % (t85 * (1.0 + b["error"]))] for b, t85 in zip(site["bars"], bars)])
    table(os.path.join(package, "loads.csv"), list(site["loads"][0]), [list(row.values()) for row in site["loads"]])
    book = os.path.join(out, {"example": "environment/rig/sealed", "pending": "authoring/provenance/pending_lab",
                              "hidden": "tests/lab/sealed"}[role], name + ".json")
    os.makedirs(os.path.dirname(book), exist_ok=True)
    with open(book, "w") as handle:
        json.dump(dict(budget=site["budget"], analyses=site["lab"]), handle)
    if role != "pending":
        found = cooled(site, site["loads"])
        results = [[row["load"]] + [form % found[name][i] for name, form in zip(quench.RESULTS, FORMATS)]
                   for i, row in enumerate(site["loads"])]
        where = os.path.join(package, "expected.csv") if role == "example" else \
            os.path.join(out, "tests/sealed/truth", name + ".csv")
        table(where, RESULT_HEADER, results)
    print("%-12s %-8s %2d tanks %5d loads %4d test bars  allowance %d, systems the log shows renewed %d" % (
        name, role, len(site["tanks"]), len(site["loads"]), len(site["bars"]), site["budget"],
        sum(1 for sy in site["systems"] if sy["renewed"])), flush=True)


if __name__ == "__main__":
    for site_name in (sys.argv[2:] or list(SITES)):
        build(sys.argv[1], site_name)
