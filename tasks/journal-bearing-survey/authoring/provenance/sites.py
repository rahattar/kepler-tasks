"""The nine sites: their bearings, oil systems, analyses on file, operating points, results and laboratory figures.

    python3 sites.py OUT [SITE ...]        (all nine when no site is named)

Everything is written under OUT at the path it has in the bundle, so `diff -r` against the bundle shows whether
the shipped files are what this program makes:

    environment/data/examples/SITE/    a package and its results (expected.csv)          two sites
    environment/data/pending/SITE/     a package without results                         one site
    environment/rig/sealed/SITE.json   what the laboratory answers for those three
    tests/sites/SITE/                  a package the submitted program is run on         six sites
    tests/sealed/truth/SITE.csv        its results
    tests/lab/sealed/SITE.json         what the laboratory answers for those six

A site is drawn from its seed. The results are film.py's, for the oil the bearing really drew at each point.

What is built in on purpose, and where (SITES below is the whole of it):

  * In the two example sites every console is what the register says: one charge.
  * `split` names a console that the register lists as one system and that is two: its first two machines draw
    from one reservoir and its third from another. The two charges gave analyses 8.5 to 11 per cent apart on
    every sample date, where two samples of one charge agree within the laboratory's 0.5 per cent, and both
    were renewed at the changeover, so the site's laboratory allowance, which is the number of charges that
    were renewed, is one more than the number of systems the register shows renewed.
  * The pending site (a package without results) has such a console. So do five of the six sites the
    submitted program is run on, in consoles of a different number and grade at each; the sixth has none.
"""
import csv
import datetime
import json
import math
import os
import random
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import film  # noqa: E402

# name: (seed, role, the console that is two charges or None, consoles, self-contained machines)
# A seed was kept for a site with such a console when the console's two new charges stand at least 8 per cent
# apart in viscosity, as its two old ones do by construction (design_rules.py checks both).
SITES = {
    "north_works": (11, "example", None, 3, 1),
    "east_works": (12, "example", None, 4, 2),
    "west_quarry": (31, "pending", 1, 4, 1),
    "quay_site": (37, "hidden", 1, 5, 2),
    "ridge_plant": (22, "hidden", 2, 4, 2),
    "canal_works": (23, "hidden", 0, 5, 1),
    "upper_mill": (24, "hidden", 3, 5, 2),
    "south_yard": (25, "hidden", None, 4, 2),
    "tank_farm": (26, "hidden", 1, 4, 3),
}

NOMINAL = {32: (32.0, 5.4, 865.0), 46: (46.0, 6.8, 870.0), 68: (68.0, 8.7, 875.0)}
# model: (journal diameter mm, length mm, radial clearance um, oil flow L/min, speeds rpm, specific loads MPa)
MODELS = {
    "JB-90": (90.0, 72.0, 60, 3.0, (1480, 3560), (0.6, 2.2)),
    "JB-125": (125.0, 110.0, 85, 6.0, (1480, 2960), (0.6, 2.4)),
    "JB-160": (160.0, 130.0, 110, 9.0, (900, 1780), (0.5, 2.0)),
    "JB-200": (200.0, 180.0, 140, 14.0, (600, 1480), (0.6, 2.2)),
}
ROUNDS = ["2024-03-11", "2024-09-09", "2025-03-10", "2025-09-08"]     # the sample rounds on file
CHANGE = "2026-01-19"                                                  # the changeover
FIRST, LAST = "2025-10-06", "2026-09-25"                               # the span of the operating points
POINTS_PER_BEARING = 110
PACKAGE = ("site.json", "bearings.csv", "oil_systems.csv", "oil_log.csv", "oil_samples.csv", "points.csv")
RESULT_HEADER = ["point", "h_min_um", "attitude_deg", "power_kW", "t_eff_C", "p_max_MPa"]


def day(rng, a, b):
    A, B = datetime.date.fromisoformat(a), datetime.date.fromisoformat(b)
    return (A + datetime.timedelta(days=rng.randrange(1, (B - A).days))).isoformat()


def scaled(nominal, f):
    """A charge as delivered: the grade's nominal figures moved by the factor f on the viscosity at 40 C."""
    return (round(nominal[0] * f, 1), round(nominal[1] * (1 + 0.6 * (f - 1)), 2), round(nominal[2] + 30 * (f - 1)))


def describe(name):
    """The site as it is: systems with their true charges, bearings, analyses on file and laboratory figures."""
    seed, role, split, n_cons, n_self = SITES[name]
    rng = random.Random(seed)
    kinds = ["P", "K", "C", "B", "G", "M"]
    systems, bearings = [], []
    mno = 100 + 10 * rng.randrange(1, 9)
    for s in range(n_cons):
        sysname = "LO-%d" % (s + 1)
        grade = rng.choice([46, 46, 68, 32])
        nm = 3 if s == split else rng.choice([2, 3])
        ms = []
        for _ in range(nm):
            mno += rng.randrange(1, 6)
            ms.append("%s-%d" % (rng.choice(kinds), mno))
        groups = [ms[:2], ms[2:]] if s == split else [ms]       # the charges the listed system really holds
        renewed = not (s == n_cons - 1 and split != s)          # the last console kept its oil at the changeover
        systems.append(dict(system=sysname, kind="console", grade=grade, renewed=renewed, groups=groups))
    for _ in range(n_self):
        mno += rng.randrange(1, 6)
        m = "%s-%d" % (rng.choice(kinds), mno)
        systems.append(dict(system="SC-" + m, kind="self-contained", grade=rng.choice([46, 68]), renewed=True,
                            groups=[[m]]))
    charges, samples = {}, []
    for sy in systems:
        base = rng.uniform(0.94, 1.06)
        for g, ms in enumerate(sy["groups"]):
            off = 0.0 if g == 0 else rng.choice([-1, 1]) * rng.uniform(0.085, 0.11)
            # a charge thickens by 0.4 per cent from one sample round to the next
            old = [scaled(NOMINAL[sy["grade"]], (base + off) * (1 + 0.004 * r)) for r in range(len(ROUNDS))]
            new = scaled(NOMINAL[sy["grade"]],
                         (rng.uniform(0.9, 0.97) if rng.random() < 0.5 else rng.uniform(1.04, 1.12))
                         + (0.0 if g == 0 else -off)) if sy["renewed"] else None
            for m in ms:
                charges[m] = dict(old=old, new=new, system=sy["system"], group=g)
        machines = [m for ms in sy["groups"] for m in ms]
        for m in machines:
            model = rng.choice(list(MODELS))
            for pos in (["DE", "NDE"] if rng.random() < 0.6 else ["DE"]):
                bearings.append(dict(tag="%s-%s" % (m, pos), machine=m, oil_system=sy["system"], model=model))
        # each round: two samples at two different machines where the system has two, one from each charge
        # where it holds two; every machine is sampled over the rounds
        for r, date in enumerate(ROUNDS):
            if len(sy["groups"]) == 2:
                picks = [sy["groups"][0][r % 2], sy["groups"][1][0]]
            elif len(machines) >= 2:
                picks = [machines[r % len(machines)], machines[(r + 1) % len(machines)]]
            else:
                picks = [machines[0]]
            for m in picks:
                own = [b["tag"] for b in bearings if b["machine"] == m]
                v = charges[m]["old"][r]
                jit = rng.choice([-0.1, 0.0, 0.1])
                samples.append((date, own[r % len(own)], "%.1f" % (v[0] + jit), "%.2f" % v[1], "%d" % v[2]))
    samples.sort()
    budget = sum(len(sy["groups"]) for sy in systems if sy["renewed"])
    site = dict(name=name, role=role, rng=rng, systems=systems, bearings=bearings, charges=charges,
                samples=samples, budget=budget)
    # what the laboratory would report for the oil now at each bearing: the new charge where the oil was
    # renewed, and where it was not, what is on file for the charge
    site["lab"] = {}
    for b in bearings:
        now = charges[b["machine"]]["new"]
        if now is None:
            nu40, nu100, rho15 = on_file(site, b["machine"])
            now = (round(nu40, 1), round(nu100, 2), round(rho15))
        site["lab"][b["tag"]] = now
    return site


def on_file(site, machine):
    """LS-3 section 7 for a charge that was not renewed, or before it was: the charge's latest analysis, the
    mean of that date's samples."""
    charges, samples = site["charges"], site["samples"]
    mine = {m for m in charges if (charges[m]["system"], charges[m]["group"]) ==
            (charges[machine]["system"], charges[machine]["group"])}
    last = max(s[0] for s in samples if s[1].rsplit("-", 1)[0] in mine)
    vals = [(float(s[2]), float(s[3]), float(s[4])) for s in samples
            if s[0] == last and s[1].rsplit("-", 1)[0] in mine]
    return tuple(sum(v[i] for v in vals) / len(vals) for i in range(3))


def operate(site):
    """The operating points on record and their results to LS-3 for the oil each bearing really drew."""
    rng = site["rng"]
    rows, results = [], []
    for b in site["bearings"]:
        D, L, c, q, speeds, loads = MODELS[b["model"]]
        charge = site["charges"][b["machine"]]
        brgs = {"old": film.Bearing((D, L, c / 1000.0, (90.0, 270.0), on_file(site, b["machine"]), q))}
        if charge["new"] is not None:
            brgs["new"] = film.Bearing((D, L, c / 1000.0, (90.0, 270.0), charge["new"], q))
        n = tries = 0
        while n < POINTS_PER_BEARING and tries < 400:
            tries += 1
            date = day(rng, FIRST, CHANGE) if rng.random() < 0.35 else day(rng, CHANGE, LAST)
            brg = brgs["new" if (date > CHANGE and "new" in brgs) else "old"]
            rpm = round(rng.uniform(*speeds) / 10) * 10
            load = round(rng.uniform(*loads) * D * L / 100) * 100
            t = round(rng.uniform(38, 52), 1)
            w = rpm * 2 * math.pi / 60.0
            brg.lands = brg.grids[0]
            x, (eps, psi, T, power, pmax, Rec) = brg.solve_regime(w, load, math.pi, t, False, (0.0, 0.9, t + 8.0))
            # kept: converged, laminar with margin, and neither nearly centred nor nearly touching
            if not (abs(brg.residual(x, w, load, math.pi, t, False)[0]).max() < 1e-7 and Rec < 0.7 * brg.Ret
                    and 0.1 < eps < 0.93):
                continue
            n += 1
            point = "%s-%03d" % (b["tag"], n)
            rows.append(dict(point=point, tag=b["tag"], date=date, speed_rpm=rpm, load_N=load, load_angle_deg=0,
                             inlet_C=t))
            results.append([point, "%.3f" % (brg.c * (1 - eps) * 1e6), "%.2f" % math.degrees(psi - math.pi),
                            "%.4f" % (power / 1e3), "%.2f" % T, "%.4f" % (pmax / 1e6)])
    order = sorted(range(len(rows)), key=lambda i: (rows[i]["date"], rows[i]["point"]))
    return [rows[i] for i in order], [results[i] for i in order]


def table(path, header, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as handle:
        out = csv.writer(handle)
        out.writerow(header)
        out.writerows(rows)


def build(out, name):
    site = describe(name)
    points, results = operate(site)
    role = site["role"]
    package = os.path.join(out, {"example": "environment/data/examples", "pending": "environment/data/pending",
                                 "hidden": "tests/sites"}[role], name)
    os.makedirs(package, exist_ok=True)
    with open(os.path.join(package, "site.json"), "w") as handle:
        json.dump(dict(site=name, lab_samples=site["budget"]), handle, indent=1)
    table(os.path.join(package, "bearings.csv"),
          ["tag", "machine", "oil_system", "journal_diameter_mm", "length_mm", "radial_clearance_um",
           "groove_angles_deg", "oil_flow_L_min"],
          [[b["tag"], b["machine"], b["oil_system"]] + list(MODELS[b["model"]][:3]) + ["90;270", MODELS[b["model"]][3]]
           for b in site["bearings"]])
    table(os.path.join(package, "oil_systems.csv"), ["oil_system", "kind", "oil_grade"],
          [[sy["system"], sy["kind"], "ISO VG %d" % sy["grade"]] for sy in site["systems"]])
    table(os.path.join(package, "oil_log.csv"), ["date", "oil_system", "work", "remarks"],
          [[CHANGE, sy["system"], "CHARGE_RENEWED", "drained, flushed and refilled, new supplier"]
           for sy in site["systems"] if sy["renewed"]])
    table(os.path.join(package, "oil_samples.csv"), ["date", "sampled_at", "nu40_cSt", "nu100_cSt", "rho15_kg_m3"],
          site["samples"])
    table(os.path.join(package, "points.csv"), list(points[0]), [list(p.values()) for p in points])
    if role == "example":
        table(os.path.join(package, "expected.csv"), RESULT_HEADER, results)
    elif role == "hidden":
        table(os.path.join(out, "tests/sealed/truth", name + ".csv"), RESULT_HEADER, results)
    book = os.path.join(out, "tests/lab/sealed" if role == "hidden" else "environment/rig/sealed", name + ".json")
    os.makedirs(os.path.dirname(book), exist_ok=True)
    with open(book, "w") as handle:
        json.dump(dict(budget=site["budget"], analyses=site["lab"]), handle)
    print("%-12s %-8s %2d bearings %5d points  allowance %d, systems the register shows renewed %d" % (
        name, role, len(site["bearings"]), len(points), site["budget"],
        sum(1 for sy in site["systems"] if sy["renewed"])), flush=True)


if __name__ == "__main__":
    for site_name in (sys.argv[2:] or list(SITES)):
        build(sys.argv[1], site_name)
