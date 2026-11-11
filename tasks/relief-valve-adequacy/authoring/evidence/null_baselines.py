#!/usr/bin/env python3
"""Answers made without doing the assessment, to show what a sheet is worth without the work.

Each valve is graded on its own, so a null answer can be right on individual valves by luck; the table lists
every such free pass. The gate is all nine, so none of these is accepted.

    python3 null_baselines.py
"""
import sys

import common
import solve

NULLS = []


def constant_case(case):
    def build(d, tru):
        a = common.Agent(d)
        rows = []
        for vid in a.valves:
            setp, orif = a.as_built(vid)
            area = a.case_area(vid, case) if case in a.reg[vid]["contingencies"].split() else None
            if area is None:
                area = solve.ORIFICE[orif]
            rows.append((vid, case, area, "adequate" if solve.ORIFICE[orif] >= area else "inadequate"))
        return rows
    return build


def installed_area(d, tru):
    """Every valve called adequate, with the orifice it carries quoted as the requirement."""
    a = common.Agent(d)
    rows = []
    for vid in a.valves:
        setp, orif = a.as_built(vid)
        rows.append((vid, a.reg[vid]["contingencies"].split()[0], solve.ORIFICE[orif], "adequate"))
    return rows


def register_only(d, tru):
    """The register and the data sheets taken as the whole truth: no record read, no quantity identified."""
    return common.run(d, cv="sheet", meter="raw", ua="design", orifice="register", setp="register",
                      raised="ignore", pump="sheet", insul="none", kv="one", credit="none")


def study(d, tru):
    rows = []
    for r in solve._md_table(d["relief_study_2019"], "| valve | governing contingency |"):
        rows.append((r["valve"], r["governing contingency"].strip("`"),
                     float(r["required area, mm2"]), r["finding"]))
    return sorted(rows)


NULLS = [
    ("fire taken as governing everywhere", constant_case("fire")),
    ("blocked outlet taken as governing everywhere", constant_case("blocked_outlet")),
    ("the orifice fitted quoted as the requirement, every valve adequate", installed_area),
    ("the register and data sheets taken as the whole truth", register_only),
    ("the 2019 study copied out", study),
]


def main():
    mod, tru = common.truth()
    d = solve.load(common.DATA)
    print("Answers made without the assessment. Area tolerance %.3f relative; the gate is all nine.\n" % mod.TOL)
    print("| Null answer | Right of 9 | Free passes |")
    print("|---|---|---|")
    for name, build in NULLS:
        rows = build(d, tru)
        n, notes = common.compare(rows, tru, mod.TOL)
        free = [v for v in sorted(notes) if not notes[v]]
        print("| %s | %d | %s |" % (name, n, ", ".join(free) if free else "none"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
