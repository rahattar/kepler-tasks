#!/usr/bin/env python3
"""The reference solution run on the shipped records, with the quantities it had to identify and the margin it
leaves against the sealed answer.

    python3 reference_run.py
"""
import os
import sys

import common
import solve


def main():
    mod, tru = common.truth()
    d = solve.load(common.DATA)
    m = solve.Model(d)
    print("solution/solve.py on the shipped records (seed %s).\n"
          % open(os.path.join(common.ROOT, "authoring", "provenance", "seed.json")).read().strip())

    print("Quantities it identifies rather than reads:\n")
    print("| quantity | identified | on the data sheet | difference |")
    print("|---|---|---|---|")
    for tag in sorted(m.cvd.index if hasattr(m.cvd, "index") else m.cvd):
        got = m.cv_rated(tag)
        sheet = solve._num(m.cvd[tag]["data_sheet_cv_rated"])
        print("| %s coefficient at full travel | %.2f | %.2f | %+.1f%% |"
              % (tag, got, sheet, 100.0 * (got / sheet - 1.0)))
    for vid in ("PSV-403", "PSV-406"):
        name = solve.REBOILER[vid][0]
        got = m.reb_ua(vid)
        ps = m.steam_supply_barg(vid) + solve.ATM
        design = solve._num(m.exch[name]["design_duty_kw"]) / (
            m.sat("steam", ps, "t") - m.mean("%s_bottoms_C" % solve.REBOILER[vid][2]))
        print("| %s coefficient-area, kW/K | %.2f | %.2f | %+.1f%% |"
              % (name, got, design, 100.0 * (got / design - 1.0)))
    k = m.feed_factor()
    print("| feed flow against FE-4011's indication | x %.4f | x 1.0000 | %+.1f%% |" % (k, 100.0 * (k - 1.0)))
    shutoff, b, suction = m.pump_curve("PSV-405")
    sheet = solve._num(next(r for r in d["pump_data"] if r["pump"] == "P-401")["data_sheet_shutoff_head_m"])
    print("| P-401 shutoff head, m | %.1f | %.1f | %+.1f%% |" % (shutoff, sheet, 100.0 * (shutoff / sheet - 1.0)))

    print("\nIts answer, against the sealed definition:\n")
    print("| valve | governing case | area, mm2 | finding | sealed area | difference |")
    print("|---|---|---|---|---|---|")
    worst = 0.0
    for vid, case, need, verd in m.sheet():
        t = tru[vid]
        rel = (need - t["area"]) / t["area"]
        worst = max(worst, abs(rel))
        print("| %s | %s | %.4f | %s | %.4f | %+.4f |" % (vid, case, need, verd, t["area"], rel))
    print("\nworst relative area %.4f against a band of %.4f" % (worst, mod.TOL))

    print("\nWhere each finding comes from:\n")
    print("| valve | required | installed | inlet loss | limit | finding |")
    print("|---|---|---|---|---|---|")
    for vid, case, need, verd in m.sheet():
        setp, orif = m.as_built(vid)
        drop = m.inlet_drop(vid, case)
        print("| %s | %.1f | %s %.0f | %s | %.3f bar | %s |" % (
            vid, need, orif, solve.ORIFICE[orif],
            ("%.3f bar" % drop) if drop > 0 else "liquid service",
            solve.INLET_LIMIT * setp, verd))
    return 0


if __name__ == "__main__":
    sys.exit(main())
