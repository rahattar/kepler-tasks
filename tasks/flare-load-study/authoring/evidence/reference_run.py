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
    sealed, tru = common.truth()
    reports = common.crew_reports(sealed)
    d = solve.load(common.DATA)
    m = solve.Study(d, reports)
    print("solution/solve.py on the shipped records (seed %s).\n"
          % open(os.path.join(common.ROOT, "authoring", "provenance", "seed.json")).read().strip())

    print("Quantities it identifies rather than reads:\n")
    print("| quantity | identified | as the records would be read without the work | difference |")
    print("|---|---|---|---|")
    for tag in sorted(t for t in m.cvd if t in solve.CVSTREAM):
        got = m.cv_rated(tag)
        sheet = solve._num(m.cvd[tag]["data_sheet_cv_rated"])
        if sheet:
            print("| %s coefficient at full travel | %.2f | %.2f (data sheet) | %+.1f%% |"
                  % (tag, got, sheet, 100.0 * (got / sheet - 1.0)))
    for vid in ("PSV-403", "PSV-406"):
        name, prefix = solve.REBOILER[vid]
        got = m.reb_ua(vid)
        ps = m.steam_supply_barg(vid) + solve.ATM
        design = solve._num(m.exch[name]["design_duty_kw"]) / (
            m.sat("steam", ps, "t") - m.mean("%s_bottoms_C" % prefix))
        print("| %s coefficient-area, kW/K | %.2f | %.2f (data sheet duty) | %+.1f%% |"
              % (name, got, design, 100.0 * (got / design - 1.0)))
    k = m.feed_factor()
    print("| feed flow against FE-4011's indication | x %.4f | x 1.0000 (as indicated) | %+.1f%% |"
          % (k, 100.0 * (k - 1.0)))
    shutoff, b, suction, temp = m.pump_curve("PSV-405")
    sheet = solve._num(next(r for r in d["pump_data"] if r["pump"] == "P-401")["data_sheet_shutoff_head_m"])
    print("| P-401 shutoff head, m | %.1f | %.1f (data sheet) | %+.1f%% |"
          % (shutoff, sheet, 100.0 * (shutoff / sheet - 1.0)))
    for vid in sorted(m.reg):
        now, reg = m.set_pressure(vid), solve._num(m.reg[vid]["set_pressure_barg"])
        if abs(now - reg) > 1.0e-9:
            print("| %s set pressure, barg | %.1f | %.1f (register) | %+.1f%% |"
                  % (vid, now, reg, 100.0 * (now / reg - 1.0)))
    for r in d["flare_tie_ins"]:
        now, sheet = m.tie_in(r["device"]), solve._num(r["tie_in_m_from_stack_base"])
        if abs(now - sheet) > 1.0e-9:
            print("| %s tie-in, m from the stack base | %.0f | %.0f (isometrics) | %+.0f m |"
                  % (r["device"], now, sheet, now - sheet))
    for item in ("T-401", "T-402", "V-401", "V-403"):
        print("| %s wetted area, m2 | %.2f | %.2f (data book elevation) | %+.1f%% |"
              % (item, m.wetted_area(item), common.Agent(d, reports, raised="ignore").wetted_area(item),
                 100.0 * (m.wetted_area(item) / common.Agent(d, reports, raised="ignore").wetted_area(item) - 1.0)))

    print("\nIts answer, against the sealed definition:\n")
    print("| contingency | devices | load, kg/h | header inlet, barg | sealed load | sealed inlet |")
    print("|---|---|---|---|---|---|")
    worst_load = worst_back = 0.0
    for c, devices, total, back in m.sheet():
        t = tru[c]
        rl = (total - t["load"]) / t["load"] if t["load"] else 0.0
        rb = (back - t["back"]) / t["back"] if t["back"] > 0.01 else 0.0
        worst_load, worst_back = max(worst_load, abs(rl)), max(worst_back, abs(rb))
        print("| %s | %s | %.1f | %.4f | %.1f (%+.3f%%) | %.4f (%+.3f%%) |"
              % (c, " ".join(devices) or "none", total, back, t["load"], 100.0 * rl, t["back"], 100.0 * rb))
    print("\nworst relative load %.4f and pressure %.4f against a band of %.4f"
          % (worst_load, worst_back, sealed.TOL))

    print("\nWhat each contingency reaches:\n")
    print("| contingency | air lost | pump runs | safety system holds | device | cause | rate, kg/h |")
    print("|---|---|---|---|---|---|---|")
    for c in m.contingencies:
        parts = m.discharging(c)
        first = True
        for vid in sorted(parts):
            print("| %s | %s | %s | %s | %s | %s | %.1f |" % (
                c if first else "", ("yes" if m.air_lost(c) else "no") if first else "",
                ("yes" if m.pump_runs(c) else "no") if first else "",
                ("yes" if m.sis_holds(c) else "no") if first else "",
                vid, m.cause_of(vid, c), parts[vid][0]))
            first = False
    return 0


if __name__ == "__main__":
    sys.exit(main())
