"""The rules the nine sites were built to, recomputed from the generator's description and the shipped files.

    python3 design_rules.py > ../evidence/design_rules.txt

Nothing here solves a film. sites.describe gives each site as it really is (which machines draw on which
charge); everything else is read from the packages and laboratory books as shipped.
"""
import csv
import hashlib
import json
import os
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
BUNDLE = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import film  # noqa: E402
import sites  # noqa: E402

WHERE = {"example": "environment/data/examples", "pending": "environment/data/pending", "hidden": "tests/sites"}
BOOKS = {"example": "environment/rig/sealed", "pending": "environment/rig/sealed", "hidden": "tests/lab/sealed"}
failed = 0
rules = 0


def rule(text, holds):
    global failed, rules
    rules += 1
    failed += not holds
    print("%s  %s" % ("holds " if holds else "FAILS ", text))


def rows(role, name, part):
    with open(os.path.join(BUNDLE, WHERE[role], name, part), newline="") as handle:
        return list(csv.DictReader(handle))


def span(values, form="%.1f"):
    return (form + " to " + form) % (min(values), max(values))


def main():
    made = {name: sites.describe(name) for name in sites.SITES}
    role = {name: site["role"] for name, site in made.items()}
    by_role = {r: [n for n in made if role[n] == r] for r in ("example", "pending", "hidden")}
    rule("%d sites: %d with results beside them, %d without, %d the program is run on; no name twice" % (
        len(made), len(by_role["example"]), len(by_role["pending"]), len(by_role["hidden"])),
        (len(by_role["example"]), len(by_role["pending"]), len(by_role["hidden"])) == (2, 1, 6))

    digest = {}
    for name in made:
        digest[name] = tuple(hashlib.sha256(open(os.path.join(BUNDLE, WHERE[role[name]], name, part), "rb").read()).hexdigest()
                             for part in sites.PACKAGE if part != "site.json")
    shared = sum(1 for h in by_role["hidden"] for v in by_role["example"] + by_role["pending"]
                 for a, b in zip(digest[h], digest[v]) if a == b)
    rule("no file of a package the program is run on is a file of a package it was written beside (%d shared)" % shared,
         shared == 0)

    sizes = {name: len(rows(role[name], name, "points.csv")) for name in made}
    rule("operating points in a package: %s beside the program, %s where it is run; the stated most is 3 000" % (
        span([sizes[n] for n in by_role["example"] + by_role["pending"]], "%d"),
        span([sizes[n] for n in by_role["hidden"]], "%d")), max(sizes.values()) <= 3000)

    print()
    print("site          role     systems renewed in the register   charges renewed   allowance   listed system that is two charges")
    counts = {}
    for name, site in made.items():
        listed = sum(1 for sy in site["systems"] if sy["renewed"])
        real = sum(len(sy["groups"]) for sy in site["systems"] if sy["renewed"])
        with open(os.path.join(BUNDLE, WHERE[role[name]], name, "site.json")) as handle:
            allowance = json.load(handle)["lab_samples"]
        two = [sy for sy in site["systems"] if len(sy["groups"]) == 2]
        counts[name] = (listed, real, allowance, two)
        print("%-13s %-8s %19d %31d %11d   %s" % (name, role[name], listed, real, allowance,
              ", ".join("%s (ISO VG %d): %s and %s" % (sy["system"], sy["grade"], " ".join(sy["groups"][0]),
                                                      " ".join(sy["groups"][1])) for sy in two) or "none"))
    print()
    rule("at every site the allowance is the number of charges that were renewed",
         all(c[1] == c[2] for c in counts.values()))
    rule("at the two example sites every listed system is one charge, and the allowance is the register's count",
         all(not counts[n][3] and counts[n][0] == counts[n][2] for n in by_role["example"]))
    with_two = [n for n in by_role["hidden"] if counts[n][3]]
    rule("%d of the 6 sites the program is run on have one listed console that is two charges, both renewed, "
         "and an allowance one above the register's count; the sixth (%s) has none" % (
             len(with_two), ", ".join(n for n in by_role["hidden"] if not counts[n][3])),
         len(with_two) == 5 and all(len(counts[n][3]) == 1 and counts[n][3][0]["renewed"]
                                    and counts[n][2] == counts[n][0] + 1 for n in with_two))
    pending = by_role["pending"][0]
    rule("the pending site, which the program's author can read, has such a console too: %s, allowance %d against "
         "%d systems renewed in the register" % (counts[pending][3][0]["system"], counts[pending][2], counts[pending][0]),
         len(counts[pending][3]) == 1 and counts[pending][3][0]["renewed"] and counts[pending][2] == counts[pending][0] + 1)
    where = {(sy["system"], sy["grade"], len(made[n]["systems"])) for n in with_two + [pending] for sy in counts[n][3]}
    rule("the console that is two charges is not one place: %s" % "; ".join(
        "%s %s of ISO VG %d" % (n, counts[n][3][0]["system"], counts[n][3][0]["grade"]) for n in [pending] + with_two),
        len({(counts[n][3][0]["system"], counts[n][3][0]["grade"]) for n in with_two}) >= 4)

    # what the analyses on file show
    gaps, spreads, steps = [], [], []
    for name, site in made.items():
        samples = rows(role[name], name, "oil_samples.csv")
        machine = {b["tag"]: b["machine"] for b in site["bearings"]}
        charge = {m: (c["system"], c["group"]) for m, c in site["charges"].items()}
        by_round = {}
        for s in samples:
            by_round.setdefault((s["date"], charge[machine[s["sampled_at"]]]), []).append(float(s["nu40_cSt"]))
        for (date, key), values in by_round.items():
            if len(values) > 1:
                spreads.append(100.0 * (max(values) / min(values) - 1.0))
        for sy in site["systems"]:
            if len(sy["groups"]) == 2:
                for date in sites.ROUNDS:
                    a = by_round[(date, (sy["system"], 0))]
                    b = by_round[(date, (sy["system"], 1))]
                    gaps.append(100.0 * abs(sum(a) / len(a) - sum(b) / len(b)) / min(sum(a) / len(a), sum(b) / len(b)))
        for key in {k[1] for k in by_round}:
            series = [sum(by_round[(d, key)]) / len(by_round[(d, key)]) for d in sites.ROUNDS if (d, key) in by_round]
            steps += [100.0 * abs(b / a - 1.0) for a, b in zip(series, series[1:])]
    rule("two samples of one charge in one sample round differ by at most %.2f per cent in viscosity at 40 C "
         "(the laboratory repeats within 0.5; the figures are given to 0.1 mm2/s)" % max(spreads), max(spreads) < 0.9)
    rule("a charge's analysis moves by at most %.2f per cent from one sample round to the next" % max(steps),
         max(steps) < 1.2)
    rule("in a console that is two charges, the two differ by %s per cent in every one of the four sample rounds "
         "(%d rounds over %d consoles)" % (span(gaps), len(gaps), len(gaps) // 4), min(gaps) > 8.0)
    rule("the smallest of those differences is %.0f times the largest difference between two samples of one charge"
         % (min(gaps) / max(spreads)), min(gaps) / max(spreads) > 8)

    # what the wrong oil is worth
    fresh, share, after = [], [], []
    for name in with_two + [pending]:
        site = made[name]
        sy = counts[name][3][0]
        with open(os.path.join(BUNDLE, BOOKS[role[name]], name + ".json")) as handle:
            book = json.load(handle)["analyses"]
        first = [b["tag"] for b in site["bearings"] if b["machine"] in sy["groups"][0]][0]
        second = [b["tag"] for b in site["bearings"] if b["machine"] in sy["groups"][1]]
        fresh.append(100.0 * abs(book[first][0] / book[second[0]][0] - 1.0))
        if name in with_two:
            points = rows("hidden", name, "points.csv")
            mine = [p for p in points if p["tag"] in second]
            share.append(len(mine))
            after.append(sum(1 for p in mine if p["date"] > sites.CHANGE))
    rule("the two new charges of such a console differ by %s per cent in viscosity at 40 C" % span(fresh),
         min(fresh) > 8.0)
    mixed = []
    for name in with_two + [pending]:
        sy = counts[name][3][0]
        ends = [made[name]["charges"][g[0]]["old"][-1][0] for g in sy["groups"]]
        mixed.append(100.0 * (max(ends) / (sum(ends) / 2.0) - 1.0))
    rule("taken as one system, its oil on file is the mean of two oils, %s per cent from either" % span(mixed),
         min(mixed) > 3.0)
    rule("the machine on the second charge has %s operating points at a site, %s of them after the renewal"
         % (span(share, "%d"), span(after, "%d")), min(after) >= 60)

    # the size of the answers and how steeply they depend on the oil
    cols = ("h_min_um", "attitude_deg", "power_kW", "p_max_MPa")
    lo = {c: 1e9 for c in cols}
    hi = {c: -1e9 for c in cols}
    rise = []
    for name in by_role["hidden"]:
        inlet = {p["point"]: float(p["inlet_C"]) for p in rows("hidden", name, "points.csv")}
        with open(os.path.join(BUNDLE, "tests/sealed/truth", name + ".csv"), newline="") as handle:
            for r in csv.DictReader(handle):
                for c in cols:
                    lo[c] = min(lo[c], float(r[c]))
                    hi[c] = max(hi[c], float(r[c]))
                rise.append(float(r["t_eff_C"]) - inlet[r["point"]])
    rule("results at the six sites: film thickness %.1f to %.1f um, attitude %.0f to %.0f degrees, power loss %.2f "
         "to %.2f kW, peak pressure %.1f to %.1f MPa, film %.1f to %.1f K above the inlet" % (
             lo["h_min_um"], hi["h_min_um"], lo["attitude_deg"], hi["attitude_deg"], lo["power_kW"], hi["power_kW"],
             lo["p_max_MPa"], hi["p_max_MPa"], min(rise), max(rise)), lo["h_min_um"] > 0 and min(rise) > 0)
    slope = []
    for name in made:
        with open(os.path.join(BUNDLE, BOOKS[role[name]], name + ".json")) as handle:
            for nu40, nu100, rho15 in json.load(handle)["analyses"].values():
                k = film.oil_constants(dict(nu40_cSt=nu40, nu100_cSt=nu100, rho15_kg_m3=rho15))
                for t in (45.0, 60.0, 75.0):
                    slope.append(100.0 * (1.0 - film.oil_at(k, t + 0.5)[0] / film.oil_at(k, t - 0.5)[0]))
    rule("the oils' viscosity falls by %.1f to %.1f per cent for each K between 45 and 75 C" % (min(slope), max(slope)),
         min(slope) > 1.5)

    # scope and the laboratory's books
    inside = True
    for name in made:
        for b in rows(role[name], name, "bearings.csv"):
            d, length = float(b["journal_diameter_mm"]), float(b["length_mm"])
            inside &= 40 <= d <= 600 and 0.3 <= length / d <= 1.2
        for p in rows(role[name], name, "points.csv"):
            b = next(x for x in made[name]["bearings"] if x["tag"] == p["tag"])
            d, length = sites.MODELS[b["model"]][:2]
            inside &= (float(p["speed_rpm"]) <= 12000 and 0.02 <= float(p["load_N"]) / (d * length) <= 7.0
                       and 10 <= float(p["inlet_C"]) <= 85 and abs(float(p["load_angle_deg"])) <= 60)
    rule("every bearing and operating point of every package is within the scope of LS-3 section 1", inside)
    complete = True
    for name, site in made.items():
        with open(os.path.join(BUNDLE, BOOKS[role[name]], name + ".json")) as handle:
            book = json.load(handle)
        complete &= set(book["analyses"]) == {b["tag"] for b in site["bearings"]} and book["budget"] == counts[name][2]
    rule("the laboratory's book for every site answers for every bearing of the site and holds the package's allowance",
         complete)
    print()
    print("%d rules, %d not holding" % (rules, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
