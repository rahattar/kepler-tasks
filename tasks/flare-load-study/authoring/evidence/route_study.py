#!/usr/bin/env python3
"""Defective routes through the study: each takes one wrong turn and is graded against the sealed answer.

Every route must fail on the shipped records. The last column counts the laboratory seeds on which the route
still gets all six contingencies right; a route that passes on many seeds is held up by scatter rather than by
the design.

    python3 route_study.py [--seeds]
"""
import os
import shutil
import sys
import tempfile

import common
import solve

SEEDS = list(range(7301, 7321))

ROUTES = [
    ("the register's set pressure, not the setting the valve carries", dict(setp="register")),
    ("the air compressor taken on the essential supply", dict(air="essential")),
    ("the safety system taken onto the normal supply with it", dict(sis="normal")),
    ("every control valve taken to close on a loss of air", dict(failpos="closed")),
    ("the pump's rated flow taken as its blocked outlet rate", dict(screen="rated")),
    ("no credit for instrumented protection", dict(credit="none")),
    ("credit taken without testing any condition", dict(credit="all")),
    ("credit taken without the SIL floor", dict(credit="sil")),
    ("credit taken without the proof test interval", dict(credit="proof")),
    ("the data sheet coefficient for every control valve", dict(cv="sheet")),
    ("a linear characteristic for every control valve", dict(cv="linear")),
    ("the largest logged flow taken as the relieving rate", dict(cv="maxflow")),
    ("the feed meter read as indicated", dict(meter="raw")),
    ("the whole valve trend fitted, across the work on the trim", dict(pool="trend")),
    ("the whole operating record averaged, across the work on the exchanger", dict(pool="record")),
    ("both records read whole", dict(pool="both")),
    ("the reboiler coefficient-area from the data sheet duty", dict(ua="design")),
    ("the data sheet duty taken as the relieving duty", dict(ua="duty")),
    ("the duty divided by the overhead's latent heat", dict(latent="overhead")),
    ("the pump's data sheet curve", dict(pump="sheet")),
    ("the last pump test on record, made before the element was renewed", dict(pump="record")),
    ("the tip coefficient the 2019 study worked to", dict(tip="old")),
    ("the booking spent on a test that reaches no row", dict(tip="old", pump="record")),
    ("elevation changes since the data book left out", dict(raised="ignore")),
    ("wetted area not cut at 7.6 m above grade", dict(firecut="none")),
    ("no drainage or firefighting credit", dict(firec="bare")),
    ("the whole shell taken as wetted", dict(level="full")),
    ("no insulation credit anywhere", dict(insul="none")),
    ("insulation credit without a certificate", dict(insul="always")),
    ("10 per cent accumulation for the fire case", dict(accum="flat")),
    ("the tie-in the isometrics show, the modification missed", dict(tiein="sheet")),
    ("the whole load along the whole header, in one length", dict(header="whole")),
    ("only the discharging tie-ins dividing the header", dict(header="flow")),
    ("the loss through the tip left out", dict(tip="skip")),
    ("the system never brought together, rates at no back pressure", dict(couple="none")),
    ("every device taken as conventional", dict(bonnet="all")),
    ("every device taken as balanced", dict(bonnet="none")),
    ("the tip sized without re-converging each candidate", dict(size="static")),
    ("the tip sized on the pressure at the blinded end", dict(size="inlet")),
    ("every density taken at atmospheric pressure", dict(rho="atm")),
]

STUDY_2019 = "the 2019 study's findings taken as the answer"


def study_sheet(d):
    """The 2019 study's findings read off as the answer."""
    rows = []
    for r in common.solve._md_table(d["flare_load_study_2019"], "| contingency | devices discharging |"):
        rows.append((r["contingency"].strip("` "),
                     tuple(sorted(r["devices discharging"].split())),
                     float(r["load, kg/h"]), float(r["header inlet, barg"])))
    return rows


def main():
    want_seeds = "--seeds" in sys.argv
    sealed, tru = common.truth()
    reports = common.crew_reports(sealed)
    d = solve.load(common.DATA)

    per_row = {c: 0 for c in tru}
    per_row["re-rating"] = 0
    results = []
    for name, sw in ROUTES + [(STUDY_2019, None)]:
        if sw is None:
            rows, sizing = study_sheet(d), None
        else:
            rows, sizing = common.run(d, reports, **sw)
        n, notes = common.compare(rows, sealed, tru, sizing)
        for c in notes:
            if notes[c]:
                per_row[c] += 1
        results.append((name, n, notes))

    counts = {}
    if want_seeds:
        tmp = tempfile.mkdtemp(prefix="fl_seed_")
        os.environ["GEN_QUIET"] = "1"
        import gen
        try:
            for seed in SEEDS:
                out = os.path.join(tmp, "data")
                shutil.rmtree(out, ignore_errors=True)
                os.makedirs(os.path.join(out, "docs"), exist_ok=True)
                gen.main(out, seed)
                ds = solve.load(out)
                for name, sw in ROUTES + [(STUDY_2019, None)]:
                    if sw is None:
                        rows, sizing = study_sheet(ds), None
                    else:
                        rows, sizing = common.run(ds, reports, **sw)
                    k, _ = common.compare(rows, sealed, tru, sizing)
                    counts[name] = counts.get(name, 0) + (1 if k == len(tru) + 1 else 0)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    print("Defective routes, graded against the sealed definition. Tolerance %.3f relative.\n" % sealed.TOL)
    print("| Route | Right of 7 | Worst part | Seeds with 7 |")
    print("|---|---|---|---|")
    for name, n, notes in results:
        seeds = "%d of %d" % (counts.get(name, 0), len(SEEDS)) if want_seeds else "-"
        print("| %s | %d | %s | %s |" % (name, n, common.worst(notes) or "-", seeds))
    print("\nRoutes failing each part:")
    for c in sorted(per_row):
        print("  %-24s %d" % (c, per_row[c]))
    thin = [c for c in per_row if per_row[c] < 3]
    full = [name for name, n, _ in results if n == len(tru) + 1]
    print("\nparts failed by fewer than 3 routes: %s" % (", ".join(sorted(thin)) if thin else "none"))
    print("routes that pass on the shipped records: %s" % (", ".join(full) if full else "none"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
