"""design_rules.py: what the nine districts have to be, recomputed from the shipped files.

    python3 authoring/provenance/design_rules.py > authoring/evidence/design_rules.txt

Reads the packages as shipped, the crew's books, and authoring/provenance/as_it_is (every district as it is
and the facts of its record, written by districts.py and made again by regenerate.py). Runs no program. Each
line is one rule with the figures it was checked on; the last line counts the rules and those not holding.
(--small reads the seven small districts under authoring/evidence/small instead.)
"""
import csv
import hashlib
import json
import os
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SMALL = "--small" in sys.argv
sys.argv = [sys.argv[0]] + (["--small"] if SMALL else [])
sys.path.insert(0, HERE)
import districts as G  # noqa: E402

PACKAGE = ("district.json", "branches.csv", "surveys.csv", "work_log.csv", "regulators.csv", "doors.csv",
           "fans.csv", "fan_curves.csv", "log.csv", "points.csv")
MOST = {"branches": 1000, "log rows": 1500, "survey points": 4500}       # as district_package.md gives them
ALTERS = ("RESUPPORTED", "ENLARGED")
held = 0
count = 0


def rule(what, ok):
    global held, count
    count += 1
    held += bool(ok)
    print("%s  %s" % ("holds" if ok else "DOES NOT HOLD", what))


def rows(path):
    with open(path, newline="") as handle:
        return list(csv.DictReader(handle))


def span(values, form="%d"):
    values = list(values)
    return (form + " to " + form) % (min(values), max(values)) if min(values) != max(values) else form % values[0]


class District:
    def __init__(self, name, spec):
        self.name, self.spec, self.role = name, spec, spec["role"]
        self.package = G.place(spec["role"], name, "package")
        with open(G.place(spec["role"], name, "book")) as handle:
            self.book = json.load(handle)
        with open(os.path.join(G.KEPT, name + ".json")) as handle:
            self.as_it_is = json.load(handle)
        with open(os.path.join(G.KEPT, name + "_facts.json")) as handle:
            self.facts = json.load(handle)
        with open(os.path.join(self.package, "district.json")) as handle:
            self.head = json.load(handle)
        self.branches = rows(os.path.join(self.package, "branches.csv"))
        self.surveys = rows(os.path.join(self.package, "surveys.csv"))
        self.work = rows(os.path.join(self.package, "work_log.csv"))
        self.log = rows(os.path.join(self.package, "log.csv"))
        self.points = rows(os.path.join(self.package, "points.csv"))
        self.result = rows(G.place(spec["role"], name, "result"))

    def worked_on(self):
        """Airways re-supported or enlarged after their latest survey."""
        latest = {}
        for s in self.surveys:
            latest[s["branch"]] = max(latest.get(s["branch"], ""), s["date"])
        return sorted({w["branch"] for w in self.work if w["work"] in ALTERS and w["date"] > latest.get(w["branch"], "")})

    def balances(self):
        """For every stopping and every campaign: the airflow into the node at its intake end along the
        surveyed airways, less the airflow out of it along them. What is missing went through the stopping."""
        kind = {b["branch"]: b["kind"] for b in self.branches}
        into, out_of = {}, {}
        for b in self.branches:
            if b["kind"] == "airway":
                into.setdefault(b["to_node"], []).append(b["branch"])
                out_of.setdefault(b["from_node"], []).append(b["branch"])
        campaigns = {}
        for s in self.surveys:
            campaigns.setdefault(s["date"][:7], {})[s["branch"]] = float(s["q_m3_s"])
        found = {}
        for b in self.branches:
            if kind[b["branch"]] != "stopping":
                continue
            node = b["from_node"]
            for month, q in sorted(campaigns.items()):
                found.setdefault(b["branch"], []).append(sum(q[a] for a in into.get(node, [])) - sum(q[a] for a in out_of.get(node, [])))
        return found


def main():
    every = [District(name, spec) for name, spec in G.SITES.items()]
    examples = [d for d in every if d.role == "example"]
    pending = [d for d in every if d.role == "pending"]
    run = [d for d in every if d.role == "run"]
    beside = examples + pending
    want_run = 4 if SMALL else 6

    rule("%d districts: %d with results beside the program, %d without, %d the program is run on; no name twice" % (
        len(every), len(examples), len(pending), len(run)),
        len(examples) == 2 and len(pending) == 1 and len(run) == want_run and len({d.name for d in every}) == len(every))
    digests, plain = {}, {}
    for d in every:
        for name in PACKAGE:
            with open(os.path.join(d.package, name), "rb") as handle:
                found = hashlib.sha256(handle.read()).hexdigest()
            # fans.csv is two rows (fan, branch, model, blade setting) and points.csv the list of what is wanted
            (plain if name in ("fans.csv", "points.csv") else digests).setdefault(found, set()).add("run" if d.role == "run" else "beside")
    shared = sum(1 for where in digests.values() if len(where) == 2)
    same = sum(1 for where in plain.values() if len(where) == 2)
    rule("no file of a district's record in a package the program is run on is a file of a package it was written "
         "beside: 0 of the register, surveys, work log, regulators, doors, catalogue sheet and log are shared (%d); "
         "a fans.csv or a points.csv, which hold no record, can be the same file (%d are)" % (shared, same), shared == 0)
    rule("every package is the ten files of district_package.md; the two examples carry expected.csv besides, the pending package nothing",
         all(sorted(os.listdir(d.package)) == sorted(PACKAGE + (("expected.csv",) if d.role == "example" and not SMALL else ())) for d in every))
    if not SMALL:
        sizes = {"branches": [len(d.branches) for d in every], "log rows": [len(d.log) for d in every],
                 "survey points": [len(d.points) for d in every]}
        rule("a package holds %s branches, %s log rows and %s survey points; the stated most are %d, %d and %d" % (
            span(sizes["branches"]), span(sizes["log rows"]), span(sizes["survey points"]),
            MOST["branches"], MOST["log rows"], MOST["survey points"]), all(max(sizes[k]) <= MOST[k] for k in MOST))
    rule("the sealed result of every district has one row for every survey point, in the columns point,flow_m3_s",
         all({r["point"] for r in d.result} == {p["point"] for p in d.points} and len(d.result) == len(d.points)
             and list(d.result[0]) == ["point", "flow_m3_s"] for d in every))
    rule("the crew's book for every district holds the package's allowance and a reading for every branch",
         all(d.book["allowance"] == d.head["survey_allowance"] and set(d.book["readings"]) == {b["branch"] for b in d.branches}
             for d in every))

    # ---- the airways worked on
    worked = {d.name: d.worked_on() for d in every}
    rule("the airways re-supported or enlarged since their latest survey, read from the work log and the surveys, are the "
         "ones the district was built with: %s a district" % span(len(v) for v in worked.values()),
         all(worked[d.name] == sorted(d.as_it_is["altered"]) for d in every))
    ratios = []
    for d in every:
        latest = {}
        for s in d.surveys:
            if s["branch"] in worked[d.name] and s["date"] >= latest.get(s["branch"], ("", 0))[0]:
                latest[s["branch"]] = (s["date"], float(s["dp_Pa"]) / float(s["q_m3_s"]) ** 2)
        ratios += [latest[b][1] / d.as_it_is["R"][b] for b in worked[d.name]]
    rule("such an airway's latest survey on file gives %s times its resistance as it is" % span(ratios, "%.1f"), min(ratios) > 3.0)

    # ---- the allowance
    def conditions(d):
        return (1 if d.as_it_is["breach"] else 0) + (1 if d.as_it_is["close_at"] else 0)
    rule("at the two example districts the allowance is the number of airways worked on, no stopping is open and "
         "the records leave no closure open",
         all(d.head["survey_allowance"] == len(worked[d.name]) and conditions(d) == 0 for d in examples))
    rule("at every district the allowance is the number of airways worked on, and one more for an open stopping, "
         "and one more for a closure the records leave open",
         all(d.head["survey_allowance"] == len(worked[d.name]) + conditions(d) for d in every))

    # ---- the open stopping
    sound, opened = [], []
    for d in every:
        for stopping, misses in d.balances().items():
            (opened if stopping == d.as_it_is["breach"] else sound).append((d.name, stopping, misses))
    worst_sound = max(abs(m) for _, _, misses in sound for m in misses)
    least_open = min(abs(m) for _, _, misses in opened for m in misses)
    most_open = max(abs(m) for _, _, misses in opened for m in misses)
    rule("at a stopping as built, the surveyed airflows at its intake end balance within %.2f m3/s in every campaign "
         "(%d stoppings, %d balances): the leak of a stopping as built and the accuracy of two readings" % (
             worst_sound, len(sound), sum(len(m) for _, _, m in sound)), worst_sound < 2.0)
    rule("at an open stopping they miss by %.1f to %.1f m3/s in every one of the three campaigns (%d stoppings), "
         "%.0f times the largest miss at a stopping as built" % (least_open, most_open, len(opened), least_open / worst_sound),
         all(len(m) == 3 for _, _, m in opened) and least_open > 4.0 * worst_sound)
    booked = []
    for d in every:
        if d.as_it_is["breach"]:
            row = next(b for b in d.branches if b["branch"] == d.as_it_is["breach"])
            booked.append((float(row["resistance_Ns2_m8"]), d.as_it_is["R"][d.as_it_is["breach"]]))
    rule("an open stopping is booked at %s N s2/m8 and is at %s" % (span((b for b, _ in booked), "%.0f"), span((r for _, r in booked), "%.1f")),
         all(b > 100 * r for b, r in booked))
    has_breach = [d.name for d in run if d.as_it_is["breach"]]
    has_close = [d.name for d in run if d.as_it_is["close_at"]]
    neither = [d.name for d in run if not d.as_it_is["breach"] and not d.as_it_is["close_at"]]
    rule("of the districts the program is run on, %d have an open stopping (%s), %d a closure the records leave open (%s), "
         "and %d neither (%s)" % (len(has_breach), ", ".join(has_breach), len(has_close), ", ".join(has_close), len(neither), ", ".join(neither)),
         len(has_breach) >= 2 and len(has_close) >= 2 and len(neither) == 1)
    rule("the pending district, which the program's author can read, has both: %s open, and the closure of %s left open" % (
        pending[0].as_it_is["breach"], pending[0].as_it_is["close_at"]), conditions(pending[0]) == 2)
    rule("the open stopping is not one place: %s" % "; ".join("%s %s" % (d.name, d.as_it_is["breach"]) for d in every if d.as_it_is["breach"]),
         len({d.as_it_is["breach"] for d in every if d.as_it_is["breach"]}) >= (2 if SMALL else 4))

    # ---- the closure the records leave open
    closes = [d for d in every if d.as_it_is["close_at"]]
    gaps = [d.facts["edge_gap_per_cent"] for d in closes]
    rule("at such a closure the resistance at which the healthy state ceases, for the district as it is and for the "
         "district as its records have it, is %s per cent apart, and the return's first entry is built between the two" % span(gaps, "%.2f"),
         0.2 <= min(gaps) and max(gaps) < 1.0)
    turned = []
    for d in closes:
        a, b = d.facts["limbs"], d.facts["limbs_on_record"]
        first = min(i for i in range(len(a)) if a[i] != b[i])
        turned.append((d.name, len(a) - first, "stalls" if a[first] == "s" else "holds"))
    rule("from that closure on the district and its records are in different states for the last %s survey rounds: %s" % (
        span(n for _, n, _ in turned), "; ".join("%s %s where the records %s" % (n, w, "hold" if w == "stalls" else "stall") for n, _, w in turned)),
        all(d.facts["limbs"][:len(d.facts["limbs"]) - n] == d.facts["limbs_on_record"][:len(d.facts["limbs"]) - n]
            for d, (_, n, _) in zip(closes, turned)) and (SMALL or {way for _, _, way in turned} == {"stalls", "holds"}))
    rule("where the records leave no closure open, the district and its records are in the same state at every round",
         all(d.facts["limbs"] == d.facts["limbs_on_record"] for d in every if not d.as_it_is["close_at"]))

    # ---- stall
    rule("every district has a fan in stall at %s of its %s survey rounds, and both fans healthy at the rest" % (
        span(d.facts["rounds_stalled"] for d in every), span(d.facts["rounds"] for d in every)),
        all(0 < d.facts["rounds_stalled"] < d.facts["rounds"] for d in every))
    rule("the working district stands between the resistance at which a fan stalls and the one at which it recovers: "
         "%s and %s times its own" % (span((d.facts["band"][1] / d.facts["size"] ** 2 for d in every), "%.2f"),
                                      span((d.facts["band"][0] / d.facts["size"] ** 2 for d in every), "%.2f")),
         all(d.facts["band"][0] < d.facts["size"] ** 2 < d.facts["band"][1] for d in every))
    print("%d rules, %d not holding" % (count, count - held))
    return 0 if held == count else 1


if __name__ == "__main__":
    sys.exit(main())
