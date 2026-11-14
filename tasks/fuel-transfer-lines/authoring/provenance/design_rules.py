"""design_rules.py: the rules the sites are built to, recomputed from the files as shipped.

    python3 authoring/provenance/design_rules.py > authoring/evidence/design_rules.txt

Everything is read from the packages, the sealed results, the crew's books and as_it_stands (what is true of
each pipe and on no record). The physics is the sealed definition's (oil_line.py, oil_pair.py). Each rule is
printed with `holds` or `BROKEN` and the figures that decide it.
"""
import csv
import json
import os
import sys

import numpy as np

sys.dont_write_bytecode = True
PROVENANCE = os.path.dirname(os.path.abspath(__file__))
BUNDLE = os.path.dirname(os.path.dirname(PROVENANCE))
sys.path.insert(0, PROVENANCE)
from oil_line import march, nu_m2s, walther  # noqa: E402
from oil_pair import roots  # noqa: E402

FACTS = os.path.join(PROVENANCE, "as_it_stands")
SIX_FILES = ("site.json", "oils.csv", "lines.csv", "surveys.csv", "work_log.csv", "records.csv")
MOST_PIPES, MOST_RECORDS = 60, 1500          # site_package.md
tally = {"rules": 0, "broken": 0}


def rule(text, holds):
    tally["rules"] += 1
    tally["broken"] += 0 if holds else 1
    print("%-7s %s" % ("holds" if holds else "BROKEN", text))


def where(name, role):
    return {"example": os.path.join(BUNDLE, "environment", "data", "examples", name),
            "pending": os.path.join(BUNDLE, "environment", "data", "pending", name),
            "run": os.path.join(BUNDLE, "tests", "sites", name)}[role]


def table(path):
    with open(path, newline="") as handle:
        return list(csv.DictReader(handle))


def oil_arrays(oils, names):
    rows = [oils[n] for n in names]
    A, B = walther(np.array([float(r["nu50_cSt"]) for r in rows]), np.array([float(r["nu100_cSt"]) for r in rows]))
    return dict(rho=np.array([float(r["density_kg_m3"]) for r in rows]), cp=np.array([float(r["cp_J_kgK"]) for r in rows]),
                k=np.array([float(r["k_W_mK"]) for r in rows]), A=A, B=B)


def coefficients(rows, bore, length, oil):
    """TS-2 5.2 by bisection on ln Uo, the sealed march; one entry a reading."""
    flow = np.array([float(r["flow_t_h"]) for r in rows]) / 3.6
    t_in, t_out, t_amb = (np.array([float(r[k]) for r in rows]) for k in ("t_in_C", "t_out_C", "t_amb_C"))
    lo, hi = np.full(len(rows), np.log(0.02)), np.full(len(rows), np.log(400.0))
    for _ in range(48):
        mid = 0.5 * (lo + hi)
        warm = march(flow, bore, length, np.exp(mid), t_in, t_amb, oil["rho"], oil["cp"], oil["k"], oil["A"], oil["B"], n=120)[1] > t_out
        lo, hi = np.where(warm, mid, lo), np.where(warm, hi, mid)
    return np.exp(0.5 * (lo + hi))


def main():
    with open(os.path.join(PROVENANCE, "manifest.json")) as handle:
        spec = json.load(handle)["sites"]
    facts = {}
    for name in spec:
        with open(os.path.join(FACTS, name + ".json")) as handle:
            facts[name] = json.load(handle)
    roles = {name: spec[name]["role"] for name in spec}
    names = sorted(spec)
    count = lambda role: sorted(n for n in names if roles[n] == role)
    print("design rules of fuel-transfer-lines, from the files as shipped")
    print()
    rule("9 sites: 2 examples with results (%s), 1 pending without (%s), 6 the program is run on (%s); no name twice"
         % (", ".join(count("example")), ", ".join(count("pending")), ", ".join(count("run"))),
         len(names) == 9 and len(count("example")) == 2 and len(count("pending")) == 1 and len(count("run")) == 6)
    beside = [n for n in names if roles[n] != "run"]
    seen = {}
    for n in beside:
        for f in SIX_FILES:
            with open(os.path.join(where(n, roles[n]), f), "rb") as handle:
                seen[handle.read()] = n
    shared = []
    for n in count("run"):
        for f in SIX_FILES[1:]:
            if f == "oils.csv":
                continue                                             # the same oils are on many sites by design
            with open(os.path.join(where(n, "run"), f), "rb") as handle:
                if handle.read() in seen:
                    shared.append("%s/%s" % (n, f))
    rule("no lines, surveys, work log or records file of a site the program is run on is a file of a site it is written beside",
         not shared)
    ok_files = all(sorted(os.listdir(where(n, "run"))) == sorted(SIX_FILES) for n in count("run"))
    rule("each of the six is the six files of a package and nothing else", ok_files)
    rule("the examples carry expected.csv, the pending site does not",
         all(os.path.exists(os.path.join(where(n, "example"), "expected.csv")) for n in count("example"))
         and not any(os.path.exists(os.path.join(where(n, "pending"), "expected.csv")) for n in count("pending")))

    sizes, stalls, laminar, first_unique, books_ok, allow_ok, recovered_ok = [], [], [], [], [], [], []
    drop_apart = {"narrowing": [], "sound pair": []}
    moved = {"declining": [], "no work": []}
    renewed = []
    history = []
    seen = []
    narrowing_now, declining_now = [], []
    places = {"narrowing": [], "declining": []}
    for n in names:
        role, f = roles[n], facts[n]
        pack = where(n, role)
        with open(os.path.join(pack, "site.json")) as handle:
            site = json.load(handle)
        lines = {r["line"]: r for r in table(os.path.join(pack, "lines.csv"))}
        oils = {r["oil"]: r for r in table(os.path.join(pack, "oils.csv"))}
        surveys, jobs, records = (table(os.path.join(pack, x)) for x in ("surveys.csv", "work_log.csv", "records.csv"))
        npipes = sum(int(l["pipes"]) for l in lines.values())
        sizes.append((len(lines), npipes, len(records)))
        kinds = {p: v["kind"] for p, v in f["pipes"].items()}
        line_of = lambda p: p.rsplit("-", 1)[0]
        # the allowance, and the pipes worked on since the last campaign
        dates = sorted({r["date"] for r in surveys})
        covering_after = sorted({j["pipe"] for j in jobs if "covering" in j["job"] and j["date"] > dates[-1]})
        recovered_ok.append(covering_after == sorted(p for p, k in kinds.items() if k == "recovered"))
        nx = sum(1 for k in kinds.values() if k == "narrowing")
        nz = sum(1 for k in kinds.values() if k == "declining")
        allow_ok.append(site["survey_allowance"] == len(covering_after) + nx + nz and (role != "example" or nx + nz == 0)
                        and (nx, nz) == (spec[n]["narrowing"], spec[n]["declining"]))
        for p, k in kinds.items():
            if k in places:
                places[k].append("%s %s" % (n, p))
        # the crew's book
        book_path = {"example": os.path.join(BUNDLE, "environment", "rig", "sealed", n + ".json"),
                     "pending": os.path.join(FACTS, n + "_book.json"), "run": os.path.join(BUNDLE, "tests", "crew", "books", n + ".json")}[role]
        with open(book_path) as handle:
            book = json.load(handle)
        books_ok.append(book["allowance"] == site["survey_allowance"] and sorted(book["readings"]) == sorted(kinds))
        # every reading says what the covering is: the outlet temperature for the coefficient 1.1 times higher
        # rather than 1.1 times lower, at the pipe's true bore and coefficient
        cases = [(r["pipe"], dates.index(r["date"]), float(r["flow_t_h"]), float(r["t_in_C"]), float(r["t_amb_C"])) for r in surveys]
        cases += [(p, 3, float(v[1]), float(v[2]), float(v[4])) for p, v in book["readings"].items()]
        o = oil_arrays(oils, [lines[line_of(c[0])]["oil"] for c in cases])
        args = [np.array([c[2] for c in cases]) / 3.6, np.array([f["pipes"][c[0]]["bore_mm"][c[1]] / 1e3 for c in cases]),
                np.array([float(lines[line_of(c[0])]["length_m"]) for c in cases])]
        u = np.array([f["pipes"][c[0]]["uo"][c[1]] for c in cases])
        t_in, t_amb = np.array([c[3] for c in cases]), np.array([c[4] for c in cases])
        hot = march(args[0], args[1], args[2], u / 1.1, t_in, t_amb, o["rho"], o["cp"], o["k"], o["A"], o["B"], n=120)[1]
        cold = march(args[0], args[1], args[2], u * 1.1, t_in, t_amb, o["rho"], o["cp"], o["k"], o["A"], o["B"], n=120)[1]
        seen.append(float(np.min(hot - cold)))
        # coefficients on file with the register's bore
        oil = oil_arrays(oils, [lines[line_of(r["pipe"])]["oil"] for r in surveys])
        bore = np.array([float(lines[line_of(r["pipe"])]["bore_mm"]) / 1e3 for r in surveys])
        length = np.array([float(lines[line_of(r["pipe"])]["length_m"]) for r in surveys])
        uo = dict(zip([(r["pipe"], r["date"]) for r in surveys], coefficients(surveys, bore, length, oil)))
        at = {(r["pipe"], r["date"]): r for r in surveys}
        for p, k in kinds.items():
            worked = any(j["pipe"] == p and "covering" in j["job"] and dates[-2] < j["date"] <= dates[-1] for j in jobs)
            step = abs(np.log(uo[(p, dates[-1])] / uo[(p, dates[-2])]))
            if k == "declining":
                moved["declining"].append(step)
                declining_now.append(f["pipes"][p]["uo"][3] / f["pipes"][p]["uo"][2])
            elif not worked and kinds[p] != "narrowing":
                moved["no work"].append(step)
            if k == "recovered":
                renewed.append(f["pipes"][p]["uo"][3] / f["pipes"][p]["uo"][2])
            if k == "narrowing":
                narrowing_now.append(1.0 - f["pipes"][p]["bore_mm"][3] / float(lines[line_of(p)]["bore_mm"]))
        # a pair's two pressure drops at the flows read, with the register's bore
        for ln, l in lines.items():
            if l["pipes"] != "2":
                continue
            o = oil_arrays(oils, [l["oil"]])
            apart = []
            for d in dates:
                pd = []
                for p in (ln + "-A", ln + "-B"):
                    r = at[(p, d)]
                    pd.append(march(np.array([float(r["flow_t_h"]) / 3.6]), float(l["bore_mm"]) / 1e3, float(l["length_m"]), uo[(p, d)],
                                    float(r["t_in_C"]), float(r["t_amb_C"]), o["rho"], o["cp"], o["k"], o["A"], o["B"], n=120)[0][0])
                apart.append(abs(np.log(pd[0] / pd[1])))
            key = "narrowing" if "narrowing" in (kinds[ln + "-A"], kinds[ln + "-B"]) else "sound pair"
            drop_apart[key].append(min(apart) if key == "narrowing" else max(apart))
        # the scope of TS-2: laminar in every pipe at every survey and every record
        worst = 0.0
        for r in surveys:
            p = r["pipe"]; l = lines[line_of(p)]; o = oils[l["oil"]]
            A, B = walther(float(o["nu50_cSt"]), float(o["nu100_cSt"]))
            w = dates.index(r["date"])
            d = f["pipes"][p]["bore_mm"][w] / 1e3
            worst = max(worst, 4 * float(r["flow_t_h"]) / 3.6 / (np.pi * d * float(o["density_kg_m3"]) * nu_m2s(A, B, float(r["t_in_C"]))))
        for r in records:
            l = lines[r["line"]]; o = oils[l["oil"]]
            A, B = walther(float(o["nu50_cSt"]), float(o["nu100_cSt"]))
            h = int(r["hour"])
            shares = [f["share_of_a"][r["line"]][h], 1 - f["share_of_a"][r["line"]][h]] if l["pipes"] == "2" else [1.0]
            for side, s in zip("AB", shares):
                d = f["pipes"][r["line"] + "-" + side]["bore_mm"][3] / 1e3
                worst = max(worst, 4 * s * float(r["flow_t_h"]) / 3.6 / (np.pi * d * float(o["density_kg_m3"]) * nu_m2s(A, B, float(r["t_in_C"]))))
        laminar.append(worst)
        # every pair stalls somewhere, and every pair's run opens where one division only satisfies 4.1
        pairs = [ln for ln, l in lines.items() if l["pipes"] == "2"]
        stalls.append((sum(1 for ln in pairs if min(min(s, 1 - s) for s in f["share_of_a"][ln]) < 0.3), len(pairs)))
        # where the record is history: more than one division, and the one the pair has is a collapsed one
        pr = [r for r in records if lines[r["line"]]["pipes"] == "2"]
        o = oil_arrays(oils, [lines[r["line"]]["oil"] for r in pr])
        par = dict(o, L=np.array([float(lines[r["line"]]["length_m"]) for r in pr]), Tin=np.array([float(r["t_in_C"]) for r in pr]),
                   Ta=np.array([float(r["t_amb_C"]) for r in pr]),
                   Da=np.array([f["pipes"][r["line"] + "-A"]["bore_mm"][3] / 1e3 for r in pr]), Db=np.array([f["pipes"][r["line"] + "-B"]["bore_mm"][3] / 1e3 for r in pr]),
                   Ua=np.array([f["pipes"][r["line"] + "-A"]["uo"][3] for r in pr]), Ub=np.array([f["pipes"][r["line"] + "-B"]["uo"][3] for r in pr]))
        case, share = roots(np.array([float(r["flow_t_h"]) / 3.6 for r in pr]), par, n=96)[:2]
        many = held = 0
        for q, r in enumerate(pr):
            found = share[case == q]
            if len(found) > 1:
                many += 1
                carried = f["share_of_a"][r["line"]][int(r["hour"])]
                if min(carried, 1 - carried) < 0.3 and np.any((found > 0.3) & (found < 0.7)):
                    held += 1
        history.append((n, many, held))
        firsts = [next(r for r in records if r["line"] == ln and r["hour"] == "0") for ln in pairs]
        o = oil_arrays(oils, [lines[ln]["oil"] for ln in pairs])
        par = dict(o, L=np.array([float(lines[ln]["length_m"]) for ln in pairs]), Tin=np.array([float(r["t_in_C"]) for r in firsts]),
                   Ta=np.array([float(r["t_amb_C"]) for r in firsts]),
                   Da=np.array([f["pipes"][ln + "-A"]["bore_mm"][3] / 1e3 for ln in pairs]), Db=np.array([f["pipes"][ln + "-B"]["bore_mm"][3] / 1e3 for ln in pairs]),
                   Ua=np.array([f["pipes"][ln + "-A"]["uo"][3] for ln in pairs]), Ub=np.array([f["pipes"][ln + "-B"]["uo"][3] for ln in pairs]))
        found = roots(np.array([float(r["flow_t_h"]) / 3.6 for r in firsts]), par, n=120)[0]
        first_unique.append(all(int(np.sum(found == q)) == 1 for q in range(len(pairs))))

    rule("a package holds 30 lines, %d to %d pipes and %d to %d records; site_package.md gives at most %d pipes and %d records"
         % (min(s[1] for s in sizes), max(s[1] for s in sizes), min(s[2] for s in sizes), max(s[2] for s in sizes), MOST_PIPES, MOST_RECORDS),
         all(s[0] == 30 and s[1] <= MOST_PIPES and s[2] <= MOST_RECORDS for s in sizes))
    rule("every survey on file, every pipe as the crew reads it now and every record is laminar in every pipe (TS-2 section 1): the largest Reynolds number is %.0f"
         % max(laminar), max(laminar) <= 2000)
    rule("the pipes whose covering was renewed or repaired after the last campaign, read from the work log, are the site's recovered pipes",
         all(recovered_ok))
    rule("a renewed or repaired covering has %.2f to %.2f times the coefficient of its last survey" % (min(renewed), max(renewed)),
         max(renewed) < 0.8)
    rule("the allowance is the recovered pipes, one more for a narrowing pipe and one more for a declining covering; the examples have neither",
         all(allow_ok))
    rule("every reading on file and every reading the crew gives moves its pipe's outlet temperature by %.3f K or more for a coefficient 1.1 times higher rather than 1.1 times lower (sites.py SEEN_K: 0.15), against a reading accuracy of 0.02 K"
         % min(seen), min(seen) >= 0.15)
    rule("the crew's book for every site holds the package's allowance and a reading for every pipe", all(books_ok))
    rule("at a sound pair the two pressure drops at the flows read, with the register's bore, are within %.3f in ln in every campaign (%d pairs)"
         % (max(drop_apart["sound pair"]), len(drop_apart["sound pair"])), max(drop_apart["sound pair"]) < 0.03)
    rule("at a pair with a narrowing pipe they are %.3f to %.3f apart in ln in every campaign"
         % (min(drop_apart["narrowing"]), max(drop_apart["narrowing"])), min(drop_apart["narrowing"]) > 0.1)
    rule("a narrowing pipe has lost %.1f to %.1f per cent of its bore as it stands now" % (100 * min(narrowing_now), 100 * max(narrowing_now)),
         min(narrowing_now) > 0.1)
    rule("with no covering job between the last two campaigns, a pipe's coefficient on file moves by at most %.3f in ln (%d pipes, narrowing ones apart)"
         % (max(moved["no work"]), len(moved["no work"])), max(moved["no work"]) < 0.03)
    rule("a declining covering's coefficient moves by %.3f to %.3f in ln between the last two campaigns, and stands %.2f to %.2f times its last survey now"
         % (min(moved["declining"]), max(moved["declining"]), min(declining_now), max(declining_now)), min(moved["declining"]) > 0.1)
    rule("the narrowing pipe is not one place: %s" % "; ".join(places["narrowing"]), len(set(p.split()[1] for p in places["narrowing"])) == len(places["narrowing"]))
    rule("the declining covering is not one place: %s" % "; ".join(places["declining"]), len(set(p.split()[1] for p in places["declining"])) == len(places["declining"]))
    rule("%d of %d pairs have a pipe carrying less than 0.3 of the oil at some record, and every site has %d or more such pairs"
         % (sum(a for a, _ in stalls), sum(b for _, b in stalls), min(a for a, _ in stalls)), min(a for a, _ in stalls) >= 15)
    rule("at %d to %d records a site a pair has more than one division that satisfies TS-2 4.1; at %d to %d of them the pair is held on a collapsed division while one between 0.3 and 0.7 also exists"
         % (min(h[1] for h in history), max(h[1] for h in history), min(h[2] for h in history), max(h[2] for h in history)),
         min(h[2] for h in history) > 0)
    rule("every pair's run of records opens at a flow at which one division only satisfies TS-2 4.1 (4.3)", all(first_unique))
    print()
    print("%d of %d rules hold" % (tally["rules"] - tally["broken"], tally["rules"]))
    return 1 if tally["broken"] else 0


if __name__ == "__main__":
    sys.exit(main())
