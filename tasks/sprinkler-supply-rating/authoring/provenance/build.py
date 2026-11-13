"""Writes the agent's data (environment/data) and the verifier's sealed rating (tests/sealed) from the sealed
definition in supply_site.py. Run from anywhere: python3 build.py
"""
import csv
import datetime as dt
import json
import os
import shutil

import docs_fp
import ssphys as P
import supply_site as S

HERE = os.path.dirname(os.path.abspath(__file__))
TASK = os.path.normpath(os.path.join(HERE, "..", ".."))
DATA = os.path.join(TASK, "environment", "data")
SEALED = os.path.join(TASK, "tests", "sealed")


def write_csv(path, header, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def register_rows(risers):
    rows = []
    for r in risers:
        hyd = S.WALL_HYDRANT.get(r["id"])
        rows.append([r["id"], r["building"], r["material"], r["size"], r["length_ft"], r["laid"], r["check"] or "",
                     hyd[0] if hyd else "", "%.0f" % hyd[1] if hyd else "",
                     "lock" if r["id"] in S.UNSUPERVISED else "switch", r["drain"][0][0], r["gauges"][-1][0],
                     "%.1f" % r["gauge_ft"], r["q_d"], r["placard_psi"]])
    return rows


REGISTER_HEADER = ["riser", "building", "lead_in_material", "lead_in_size_in", "lead_in_equiv_length_ft", "laid",
                   "lead_in_check", "wall_hydrant", "wall_hydrant_at_equiv_ft", "valve_supervision", "main_drain",
                   "supply_gauge_serial", "supply_gauge_height_ft", "placard_flow_gpm", "placard_pressure_psi"]


def drain_rows(log, only=None):
    return [[x["riser"], x["time"].strftime("%Y-%m-%d"), x["time"].strftime("%H:%M"), x["gauge_serial"],
             "%.1f" % x["static_psi"], "%.1f" % x["residual_psi"]] for x in log if only is None or x["riser"] in only]


def pressure_rows(main, first, last):
    rows = []
    for i in range(main.n):
        t = main.time(i)
        if first <= t.date() <= last:
            rows.append([t.strftime("%Y-%m-%d %H:%M"), "%.2f" % main.record[i]])
    return rows


def maintenance_rows():
    rows = [(S.OVERHAUL.date(), "connection", "Backflow preventer overhauled: both checks stripped, springs and "
             "seats renewed, isolating valves operated. Returned to service the same afternoon.")]
    for r in S.RISERS:
        if "swab" in r:
            rows.append((r["swab"][0].date(), r["id"], "Lead-in swabbed and flushed from the yard main to the "
                         "riser. Riser shut for the work."))
        for when, _cv in r.get("valve", []):
            if "swab" not in r:
                rows.append((when.date(), r["id"], "Control valve gland repacked; valve exercised."))
        for i, (serial, until) in enumerate(r["gauges"][:-1]):
            rows.append((until.date(), r["id"], "Supply gauge %s found with a cracked lens and replaced by %s."
                         % (serial, r["gauges"][i + 1][0])))
        for i, (pattern, until) in enumerate(r["drain"][:-1]):
            rows.append((until.date(), r["id"], "Main drain valve seized; replaced, %s pattern fitted."
                         % r["drain"][i + 1][0]))
    rows += list(S.NO_EFFECT)
    rows.sort(key=lambda x: x[0])
    return [[d.strftime("%Y-%m-%d"), item, work] for d, item, work in rows]


def main():
    if os.path.isdir(DATA):
        shutil.rmtree(DATA)
    os.makedirs(os.path.join(DATA, "docs"))
    sim = S.simulate()
    grid = sim["main"]
    write_csv(os.path.join(DATA, "riser_register.csv"), REGISTER_HEADER, register_rows(S.RISERS))
    write_csv(os.path.join(DATA, "main_drain_log.csv"),
              ["riser", "date", "time", "gauge_serial", "static_psi", "residual_psi"], drain_rows(sim["drain_log"]))
    write_csv(os.path.join(DATA, "utility_pressure.csv"), ["timestamp", "pressure_psi"],
              pressure_rows(grid, S.LOG_START, S.LOG_END))
    write_csv(os.path.join(DATA, "utility_flow_tests.csv"),
              ["date", "time", "residual_hydrant", "flow_hydrant", "outlets_flowing", "static_psi", "residual_psi",
               "pitot_psi"],
              [[u["time"].strftime("%Y-%m-%d"), u["time"].strftime("%H:%M"), u["residual_hydrant"],
                u["flow_hydrant"], u["outlets"], "%.1f" % u["static_psi"], "%.1f" % u["residual_psi"],
                "%.1f" % u["pitot_psi"]] for u in sim["utility_tests"]])
    write_csv(os.path.join(DATA, "yard_flow_tests.csv"),
              ["date", "time", "flow_hydrant", "outlets_flowing", "pitot_psi", "gauge_riser", "static_psi",
               "residual_psi"],
              [[y["time"].strftime("%Y-%m-%d"), y["time"].strftime("%H:%M"), y["flow_hydrant"], y["outlets"],
                "%.1f" % y["pitot_psi"], y["residual_riser"], "%.1f" % y["static_psi"], "%.1f" % y["residual_psi"]]
               for y in sim["yard_tests"]])
    write_csv(os.path.join(DATA, "maintenance_log.csv"), ["date", "item", "work"], maintenance_rows())
    serials = sorted({g for r in S.RISERS for g, _u in r["gauges"]})
    with open(os.path.join(DATA, "gauge_certificates.md"), "w") as f:
        f.write(docs_fp.certificates(serials, S.GAUGE_ZERO))
    for name, text in docs_fp.documents().items():
        with open(os.path.join(DATA, "docs", name), "w") as f:
            f.write(text)

    # the example riser: its year of rounds, made along with the other risers' rounds of that year
    ex_first, ex_last = dt.date(2022, 1, 1), dt.date(2022, 12, 31)
    ex = S.simulate(risers=[S.EXAMPLE] + S.RISERS, tag="example", first=ex_first, last=ex_last, main=grid)
    exd = os.path.join(DATA, "example")
    write_csv(os.path.join(exd, "riser_register.csv"), REGISTER_HEADER, register_rows([S.EXAMPLE]))
    write_csv(os.path.join(exd, "main_drain_log.csv"),
              ["riser", "date", "time", "gauge_serial", "static_psi", "residual_psi"],
              drain_rows(ex["drain_log"], only={"SR00"}))
    write_csv(os.path.join(exd, "utility_pressure.csv"), ["timestamp", "pressure_psi"],
              pressure_rows(grid, ex_first, ex_last))
    write_csv(os.path.join(exd, "maintenance_log.csv"), ["date", "item", "work"], [])
    with open(os.path.join(exd, "about_this_riser.md"), "w") as f:
        f.write(docs_fp.EXAMPLE_NOTE)
    with open(os.path.join(exd, "gauge_certificates.md"), "w") as f:
        f.write(docs_fp.certificates(["G-1399"], S.GAUGE_ZERO))

    # the contractor's program and what it runs on
    rig = os.path.join(TASK, "environment", "rig", "sealed")
    os.makedirs(rig, exist_ok=True)
    for name in ("ssphys.py", "supply_site.py"):
        shutil.copy(os.path.join(HERE, name), os.path.join(rig, name))
    with open(os.path.join(rig, "seed.json"), "w") as f:
        json.dump({"seed": S.SEED}, f)

    exp = S.expected(grid)
    os.makedirs(SEALED, exist_ok=True)
    with open(os.path.join(SEALED, "rating.json"), "w") as f:
        json.dump({rid: {"limit": e["limit"], "p_base_psi": round(e["p_base_psi"], 4),
                         "q_avail_gpm": round(e["q_avail_gpm"], 3)} for rid, e in exp.items()}, f, indent=1)
    for rid, e in exp.items():
        print(rid, e["limit"], "%.2f psi" % e["p_base_psi"], "%.0f gpm" % e["q_avail_gpm"])
    print("drain log rows:", len(sim["drain_log"]), " pressure rows:", len(pressure_rows(grid, S.LOG_START, S.LOG_END)))


if __name__ == "__main__":
    main()
