"""The rules the nine sites were built to, recomputed from the generator's description and the shipped files.

    python3 design_rules.py > ../evidence/design_rules.txt

Nothing here cools a bar. sites.describe gives each site as it really is (which tanks hold which
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
import quench  # noqa: E402
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
    if min(values) == max(values):
        return form % min(values)
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

    sizes = {name: len(rows(role[name], name, "loads.csv")) for name in made}
    rule("loads in a package: %s beside the program, %s where it is run; the stated most is 3 000" % (
        span([sizes[n] for n in by_role["example"] + by_role["pending"]], "%d"),
        span([sizes[n] for n in by_role["hidden"]], "%d")), max(sizes.values()) <= 3000)

    print()
    print("site          role     systems renewed in the register   charges renewed   allowance   central system that is two charges")
    counts = {}
    for name, site in made.items():
        listed = sum(1 for sy in site["systems"] if sy["renewed"])
        real = sum(len(sy["groups"]) for sy in site["systems"] if sy["renewed"])
        with open(os.path.join(BUNDLE, WHERE[role[name]], name, "site.json")) as handle:
            allowance = json.load(handle)["lab_samples"]
        two = [sy for sy in site["systems"] if len(sy["groups"]) == 2]
        counts[name] = (listed, real, allowance, two)
        print("%-13s %-8s %19d %31d %11d   %s" % (name, role[name], listed, real, allowance,
              ", ".join("%s (Type %s): %s and %s" % (sy["system"], sy["type"], " ".join(sy["groups"][0]),
                                                      " ".join(sy["groups"][1])) for sy in two) or "none"))
    print()
    rule("at every site the allowance is the number of charges that were renewed",
         all(c[1] == c[2] for c in counts.values()))
    rule("at the two example sites every listed system is one charge, and the allowance is the register's count",
         all(not counts[n][3] and counts[n][0] == counts[n][2] for n in by_role["example"]))
    with_two = [n for n in by_role["hidden"] if counts[n][3]]
    rule("%d of the 6 sites the program is run on have one central system that is two charges, both renewed, "
         "and an allowance one above the register's count; the sixth (%s) has none" % (
             len(with_two), ", ".join(n for n in by_role["hidden"] if not counts[n][3])),
         len(with_two) == 5 and all(len(counts[n][3]) == 1 and counts[n][3][0]["renewed"]
                                    and counts[n][2] == counts[n][0] + 1 for n in with_two))
    pending = by_role["pending"][0]
    rule("the pending site, which the program's author can read, has such a system too: %s, allowance %d against "
         "%d systems renewed in the register" % (counts[pending][3][0]["system"], counts[pending][2], counts[pending][0]),
         len(counts[pending][3]) == 1 and counts[pending][3][0]["renewed"] and counts[pending][2] == counts[pending][0] + 1)
    rule("the system that is two charges is not one place: %s" % "; ".join(
        "%s %s of Type %s" % (n, counts[n][3][0]["system"], counts[n][3][0]["type"]) for n in [pending] + with_two),
        len({(counts[n][3][0]["system"], counts[n][3][0]["type"]) for n in with_two}) >= 4)

    # what the analyses on file show
    gaps, spreads, steps = [], [], []
    for name, site in made.items():
        samples = rows(role[name], name, "oil_samples.csv")
        charge = {t: (c["system"], c["group"]) for t, c in site["charges"].items()}
        by_round = {}
        for smp in samples:
            by_round.setdefault((smp["date"], charge[smp["sampled_at"]]), []).append(float(smp["cr_max_K_s"]))
        for values in by_round.values():
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
    rule("two samples of one charge in one sample round differ by at most %.2f per cent in maximum cooling rate "
         "(the laboratory repeats within 0.5; the figures are given to 0.1 K/s)" % max(spreads), max(spreads) < 0.5)
    rule("a charge's analysis moves by at most %.2f per cent from one sample round to the next" % max(steps),
         max(steps) < 1.2)
    rule("in a system that is two charges, the two differ by %s per cent in every one of the four sample rounds "
         "(%d rounds over %d systems)" % (span(gaps), len(gaps), len(gaps) // 4), min(gaps) > 8.0)
    rule("the smallest of those differences is %.0f times the largest difference between two samples of one charge"
         % (min(gaps) / max(spreads)), min(gaps) / max(spreads) > 8)

    # what the wrong oil is worth
    fresh, share, after, mixed = [], [], [], []
    for name in with_two + [pending]:
        site = made[name]
        sy = counts[name][3][0]
        with open(os.path.join(BUNDLE, BOOKS[role[name]], name + ".json")) as handle:
            book = json.load(handle)["analyses"]
        first, second = sy["groups"][0][0], sy["groups"][1][0]
        fresh.append(100.0 * abs(book[first][0] / book[second][0] - 1.0))
        ends = [site["charges"][g[0]]["old"][-1][0] for g in sy["groups"]]
        mixed.append(100.0 * (max(ends) / (sum(ends) / 2.0) - 1.0))
        if name in with_two:
            mine = [p for p in rows("hidden", name, "loads.csv") if p["tank"] == second]
            share.append(len(mine))
            after.append(sum(1 for p in mine if p["date"] > sites.CHANGE))
    rule("the two new charges of such a system differ by %s per cent in maximum cooling rate" % span(fresh),
         min(fresh) > 8.0)
    rule("taken as one system, its oil on file is the mean of two oils, %s per cent from either" % span(mixed),
         min(mixed) > 3.0)
    rule("the tank on the second charge has %s loads at a site, %s of them after the renewal"
         % (span(share, "%d"), span(after, "%d")), min(after) >= 60)

    # the size of the answers and how much they depend on the oil
    cols = quench.RESULTS
    lo = {c: 1e9 for c in cols}
    hi = {c: -1e9 for c in cols}
    for name in by_role["hidden"]:
        with open(os.path.join(BUNDLE, "tests/sealed/truth", name + ".csv"), newline="") as handle:
            for r in csv.DictReader(handle):
                for c in cols:
                    lo[c] = min(lo[c], float(r[c]))
                    hi[c] = max(hi[c], float(r[c]))
    rule("results at the six sites: centre from 800 to 500 C in %.1f to %.1f s, centre cooling rate through 700 C "
         "%.1f to %.1f K/s, largest centre to surface difference %.0f to %.0f K, surface at %.0f to %.0f C when the "
         "centre reaches 500 C, centre at 150 C after %.0f to %.0f s" % (
             lo["t85_core_s"], hi["t85_core_s"], lo["cr700_core_K_s"], hi["cr700_core_K_s"], lo["dT_max_K"],
             hi["dT_max_K"], lo["ts_core500_C"], hi["ts_core500_C"], lo["t150_core_s"], hi["t150_core_s"]),
         lo["t85_core_s"] > 0)
    peaks = []
    for name in made:
        with open(os.path.join(BUNDLE, BOOKS[role[name]], name + ".json")) as handle:
            for cr_max, t_crmax, cr_300 in json.load(handle)["analyses"].values():
                peaks.append(float(quench.film(t_crmax, cr_max, t_crmax, cr_300)))
    rule("the oils' peak heat transfer coefficient is %.0f to %.0f W/m2K" % (min(peaks), max(peaks)), min(peaks) > 1000)

    # scope and the laboratory's books
    inside = True
    seen = {"diameter_mm": [], "furnace_C": [], "bath_C": []}
    for name in made:
        for p in rows(role[name], name, "loads.csv"):
            inside &= (16 <= float(p["diameter_mm"]) <= 120 and 820 <= float(p["furnace_C"]) <= 900
                       and 40 <= float(p["bath_C"]) <= 90 and p["steel"] in quench.STEELS)
            for key in seen:
                seen[key].append(float(p[key]))
    rule("every load of every package is within the scope of HT-5 section 1: bars of %s mm, furnace at %s C, "
         "bath at %s C" % (span(seen["diameter_mm"], "%d"), span(seen["furnace_C"], "%d"), span(seen["bath_C"], "%d")),
         inside)
    complete = True
    for name, site in made.items():
        with open(os.path.join(BUNDLE, BOOKS[role[name]], name + ".json")) as handle:
            book = json.load(handle)
        complete &= set(book["analyses"]) == {t["tank"] for t in site["tanks"]} and book["budget"] == counts[name][2]
    rule("the laboratory's book for every site answers for every tank of the site and holds the package's allowance",
         complete)
    print()
    print("%d rules, %d not holding" % (rules, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
