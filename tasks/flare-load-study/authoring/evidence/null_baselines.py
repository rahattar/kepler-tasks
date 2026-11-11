#!/usr/bin/env python3
"""Answers made without doing the study, to show what a sheet is worth without the work.

Each contingency is graded on its own, so a null answer can be right on one row by luck; the table lists every
such free pass. The gate is all six, so none of these is accepted.

    python3 null_baselines.py
"""
import sys

import common
import route_study
import solve


def everything(d, tru, reports):
    """Every device that admits any cause taken to discharge under every contingency."""
    a = common.Agent(d, reports)
    rows = []
    for c in a.contingencies:
        parts = {}
        for vid in sorted(a.reg):
            for cause in a.reg[vid]["causes_admitted"].split():
                got = a.rate(vid, cause)
                if got and got[0] > 0.0:
                    parts[vid] = got
                    break
        rows.append((c, tuple(sorted(parts)), sum(v[0] for v in parts.values()), a.header_pressure(parts)))
    return rows


def nothing(d, tru, reports):
    """No device discharges anywhere."""
    return [(c, (), 0.0, 0.0) for c in common.Agent(d, reports).contingencies]


def lowest_set(d, tru, reports):
    """Only the device with the lowest set pressure, on the grounds that it lifts first."""
    a = common.Agent(d, reports)
    vid = min(sorted(a.reg), key=lambda v: a.set_pressure(v))
    rows = []
    for c in a.contingencies:
        cause = a.reg[vid]["causes_admitted"].split()[0]
        got = a.rate(vid, cause)
        parts = {vid: got} if got and got[0] > 0.0 else {}
        rows.append((c, tuple(parts), sum(v[0] for v in parts.values()), a.header_pressure(parts)))
    return rows


def zones_only(d, tru, reports):
    """Every contingency answered with the first zone's fire case, the process cases never considered."""
    a = common.Agent(d, reports)
    zone = sorted(a.zones)[0]
    rows = []
    for c in a.contingencies:
        parts = {}
        for vid in sorted(a.reg):
            if a.reg[vid]["protected_item"] in a.zones[zone] and "fire" in a.reg[vid]["causes_admitted"]:
                got = a.rate(vid, "fire")
                if got and got[0] > 0.0:
                    parts[vid] = got
        rows.append((c, tuple(sorted(parts)), sum(v[0] for v in parts.values()), a.header_pressure(parts)))
    return rows


def sets_only(d, tru, reports):
    """The device sets worked out properly, the two numbers left at the 2019 study's."""
    old = {r[0]: r for r in route_study.study_sheet(d)}
    worked, _sizing = common.run(d, reports)
    out = []
    for c, devices, total, back in worked:
        was = old.get(c)
        out.append((c, devices, was[2] if was else 0.0, was[3] if was else 0.0))
    return out


def no_header(d, tru, reports):
    """The loads worked out properly and the header never computed."""
    rows, _sizing = common.run(d, reports)
    return [(c, devices, total, 0.0) for c, devices, total, _ in rows]


NULLS = [
    ("every device that admits a cause, under every contingency", everything),
    ("no device discharges anywhere", nothing),
    ("only the device with the lowest set pressure", lowest_set),
    ("the first zone's fire case, whatever the contingency", zones_only),
    ("the 2019 study's findings copied", lambda d, tru, reports: route_study.study_sheet(d)),
    ("the right device sets with the 2019 numbers", sets_only),
    ("the right loads with the header never computed", no_header),
]


def main():
    sealed, tru = common.truth()
    reports = common.crew_reports(sealed)
    d = solve.load(common.DATA)
    print("Answers made without doing the study. Tolerance %.3f relative.\n" % sealed.TOL)
    print("| Null answer | Right of 6 | Free passes |")
    print("|---|---|---|")
    worst = 0
    for name, build in NULLS:
        n, notes = common.compare(build(d, tru, reports), sealed, tru)
        free = [c for c in sorted(notes) if not notes[c]]
        worst = max(worst, n)
        print("| %s | %d | %s |" % (name, n, ", ".join(free) or "none"))
    print("\nbest null answer: %d of 6 contingencies, against a gate of all six and the re-rating" % worst)
    return 0


if __name__ == "__main__":
    sys.exit(main())
