"""Writes the agent's documents and the sealed files for crack-growth-life from the sealed definition fcgsim.py.

    python3 gen.py OUTDIR

OUTDIR/data    the agent's documents (installed read-only at /app/data)
OUTDIR/sealed  fcgsim.py and seed.json (the laboratory's scatter seed), for the laboratory and the verifier
Everything is deterministic: the documents carry the sealed definition's components, loading and records, and each
example's re-inspected depth is the sealed growth law integrated over its recorded operating days.
"""
import csv
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fcgsim as F  # noqa: E402

SEED = 9704  # the laboratory's scatter seed, chosen by seed_screen.py
OUT = None
FAB_TEXT = {"AW": "as welded", "PWHT": "PWHT 580 C, 2 h, furnace", "VSR": "as welded; vibratory stress relief (VSR) 2017"}
LOG_EXTRA = {"C12": ("2022-05-16", "Walkway bracket torn off by a grab strike. New bracket fitted and fillet welded on site "
                                   "(E7018, 100 C preheat); MPI clear."),
             "C16": ("2023-08-29", "Cable tray cleat added for the new conveyor power cable, fillet welded on site "
                                   "(E7018, 100 C preheat); MPI clear.")}
MEMBER = {"B1": "unloader 1 boom", "T1": "unloader 1 tower", "B2": "unloader 2 boom", "T2": "unloader 2 tower"}
DETAIL = {"stiffener": "transverse stiffener", "lug": "lifting lug", "diaphragm": "diaphragm plate",
          "bracket": "walkway bracket", "cleat": "cable tray cleat"}


def w(path, rows, header):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        wr = csv.writer(f, lineterminator="\n"); wr.writerow(header); wr.writerows(rows)


def fl(x):
    return ("%.1f" % x).rstrip("0").rstrip(".")


def main(outdir):
    global OUT
    OUT = os.path.join(outdir, "data")
    sealed = os.path.join(outdir, "sealed")
    os.makedirs(sealed, exist_ok=True)
    shutil.copyfile(os.path.join(HERE, "fcgsim.py"), os.path.join(sealed, "fcgsim.py"))
    with open(os.path.join(sealed, "seed.json"), "w") as f:
        json.dump({"seed": SEED}, f)
        f.write("\n")
    os.makedirs(os.path.join(OUT, "docs"), exist_ok=True)
    comps = [F.comp(t, future=False) for t in F.COMPS]
    ex = [F.comp(t, future=False) for t in F.EXAMPLES]
    w(os.path.join(OUT, "component_register.csv"),
      [[c["id"], MEMBER[c["loc"]], c["position"], DETAIL[c["detail"]], fl(c["T"]), fl(c["tatt"]), fl(c["leg"]), c["heat"],
        FAB_TEXT[c["fab"]], fl(c["smin"])] for c in comps],
      ["component", "member", "position", "attachment", "flange_thickness_mm", "attachment_thickness_mm",
       "fillet_weld_leg_mm", "flange_plate_heat", "member_fabrication", "dead_load_stress_MPa"])
    w(os.path.join(OUT, "material_certificates.csv"),
      [[h, v[0], "%.0f" % v[1], "%.0f" % v[2]] for h, v in F.HEATS.items()],
      ["heat", "grade", "yield_strength_MPa", "fracture_toughness_Kmat_MPa_sqrt_m"])
    w(os.path.join(OUT, "inspection_2026.csv"),
      [[c["id"], "TOFD", "weld toe, in the flange", fl(c["a0"]), "2026-03-%02d" % (2 + i // 4)] for i, c in enumerate(comps)],
      ["component", "method", "crack_location", "crack_depth_mm", "date"])
    rows = []
    for c in comps:
        for f, n in zip(F.FRAC, F.counts(c)):
            rows.append([c["id"], fl(c["dsmax"] * f), "%d" % n])
    w(os.path.join(OUT, "strain_survey_rainflow.csv"), rows, ["component", "stress_range_MPa", "cycles"])
    byid = {c["id"]: c for c in comps}
    def where(cid):
        c = byid[cid]
        return "%s, %s" % (MEMBER[c["loc"]], c["position"])
    log = [["2017-06-12", where("C06"), "Lug weld toe dressed and re-welded after a coating crack (no crack found under it); "
                                         "vibratory stress relief (VSR) applied after welding."],
           ["2017-06-14", where("C10"), "Bracket weld re-made after a coating crack (no crack found under it); vibratory stress "
                                         "relief (VSR) applied after welding."],
           ["2019-09-03", "unloader 1 tower", "Ladder brackets re-coated."],
           ["2024-02-12", "unloader 1 boom, frame 12, top flange", "Crack E01 found at a transverse stiffener; assessed and left in service (record E01)."],
           ["2024-12-09", "unloader 1 boom, frame 12, top flange", "E01 ground out and re-welded (record E01)."],
           ["2025-01-20", "unloader 1 tower, leg D, outer flange", "Crack E02 found at a lifting lug; assessed and left in service (record E02)."],
           ["2025-06-23", "unloader 1 tower, leg D, outer flange", "E02 ground out and re-welded (record E02)."],
           ["2025-09-08", "both unloaders", "Strain-gauge survey started on both unloaders; rainflow counted on site (strain_survey_rainflow.csv)."],
           ["2025-09-22", "unloader 1", "Slew drive gearbox failed; unloader 1 out of service."],
           ["2025-09-29", "unloader 1", "Slew drive gearbox replaced; unloader 1 back in service."],
           ["2025-10-12", "both unloaders", "Strain-gauge survey ended."],
           ["2026-01-20", "unloader 2", "Grab G-3 (12.0 t empty, 24.0 t rated payload) replaced by G-5 (15.0 t empty, 30.0 t rated "
                                        "payload). Unloader 1 keeps its G-3 grab. The strain survey was taken with G-3 on both unloaders."],
           ["2026-03-02", "both unloaders", "Inspection campaign (TOFD): 16 weld-toe cracks recorded (inspection_2026.csv)."]]
    for cid, (d, txt) in LOG_EXTRA.items():
        log.append([d, where(cid), txt])
    log.sort(key=lambda r: r[0])
    w(os.path.join(OUT, "maintenance_log.csv"), log, ["date", "location", "entry"])
    os.makedirs(os.path.join(OUT, "examples"), exist_ok=True)
    dates = {"E01": ("2024-02-12", "2024-12-09"), "E02": ("2025-01-20", "2025-06-23")}
    for c in ex:
        days = F.EXAMPLE_DAYS[c["id"]]
        N = days * F.counts(c).sum() / F.SURVEY_DAYS
        a2 = F.grow(c, N)
        lines = [["component", c["id"]], ["member", MEMBER[c["loc"]]], ["position", c["position"]],
                 ["attachment", DETAIL[c["detail"]]],
                 ["flange_thickness_mm", fl(c["T"])], ["attachment_thickness_mm", fl(c["tatt"])],
                 ["fillet_weld_leg_mm", fl(c["leg"])], ["flange_plate_heat", c["heat"]],
                 ["member_fabrication", FAB_TEXT[c["fab"]]], ["dead_load_stress_MPa", fl(c["smin"])],
                 ["crack_depth_found_mm", fl(c["a0"])], ["depth_found_by", "TOFD"], ["date_found", dates[c["id"]][0]],
                 ["date_repaired", dates[c["id"]][1]], ["repair", "ground out and re-welded (procedure FA-3)"],
                 ["excavation_depth_mm", "%.1f" % (a2 + F.REPAIR_MARGIN_MM)],
                 ["operating_days_found_to_repair", "%d" % days],
                 ["survey", "2023 strain-gauge survey at this attachment, %d days of normal operation" % F.SURVEY_DAYS],
                 ["survey_days", "%d" % F.SURVEY_DAYS]]
        for f, n in zip(F.FRAC, F.counts(c)):
            lines.append(["survey_range_%s_MPa_cycles" % fl(c["dsmax"] * f), "%d" % n])
        w(os.path.join(OUT, "examples", "%s_record.csv" % c["id"]), lines, ["item", "value"])
    open(os.path.join(OUT, "docs", "procedure.md"), "w").write(PROCEDURE)
    open(os.path.join(OUT, "docs", "laboratory.md"), "w").write(LAB)
    w(os.path.join(OUT, "fcg_handbook.csv"), [
        ["BS 7910 simplified crack growth law, mean + 2 SD, steels in air",
         "da/dN = 5.21e-13 dK^3 (mm/cycle, dK in N/mm^1.5), that is 1.65e-11 dK^3 (m/cycle, dK in MPa sqrt(m))"],
        ["BS 7910 recommended threshold, steels in air",
         "dK0 = 170 - 214 R N/mm^1.5 (5.38 - 6.77 R MPa sqrt(m)) for 0 <= R < 0.5; 63 N/mm^1.5 (2.0 MPa sqrt(m)) for R >= 0.5"],
        ["Single-edge crack in a plate under tension (Tada)",
         "K = S Y sqrt(pi a), Y = 1.12 - 0.231 (a/W) + 10.55 (a/W)^2 - 21.72 (a/W)^3 + 30.39 (a/W)^4, a/W <= 0.6"],
    ], ["item", "value"])


PROCEDURE = """# Fatigue crack assessment, procedure FA-3

Scope: fatigue cracks found at the toes of the fillet welds that join attachments to the chord flanges of the
booms and towers of the berth's two grab ship unloaders, left in service under monitoring until they are repaired.
Assessments follow BS 7910 (fatigue crack growth) except where this procedure says otherwise.

## Crack model

Each crack is a long crack running along the weld toe and growing through the flange thickness, under the
nominal stress in the flange measured by the strain-gauge survey. The crack depth a0 is the TOFD depth from the
inspection. The critical depth is reached when the maximum stress intensity factor under primary stress, from
the dead-load stress plus the largest stress range of the spectrum, equals the fracture toughness Kmat of the
flange plate's heat, or at half the flange thickness, whichever comes first.

## Loading

The stress ranges are the rainflow counts of the strain-gauge survey of 8 September to 12 October 2025, on top of the
dead-load stress in the component register: each cycle rises from the dead-load stress, and its stress ratio R also
counts the welding residual stress at the weld toe, at the level BS 7910 gives for the joint's condition. Each
unloader discharges onto the berth conveyor, which sets its throughput at 1,800 t/h whatever grab it carries. The
unloaders operate 300 days a year, and the survey is taken as representative of every operating day.

## Growth and life

The remaining life is the operating time for the crack to grow from a0 to the critical depth, integrated over
the spectrum, using the flange material's crack growth behaviour. The laboratory tests the flange plate material
(docs/laboratory.md). The re-inspection interval is set in months of operation, twelve to an operating year.

## Repairs

A crack is repaired by grinding it out and re-welding the groove. The groove is ground until magnetic particle
inspection shows no further indication and then 1 mm deeper, to take out the crack tip; its depth is recorded as the
excavation depth.
"""

LAB = """# Crack growth testing

The materials laboratory tests compact-tension (CT) specimens to ASTM E647, cut from retained flange plate of any of
the four heats (H1 to H4) and stress relieved before machining, in laboratory air at room temperature, at a load ratio
R = Kmin/Kmax of your choosing (0.05 to 0.90). Results are reported as crack growth rate da/dN (m/cycle) against the
stress intensity factor range dK (MPa sqrt(m)).

The laboratory keeps Kmax = dK / (1 - R) below 75 MPa sqrt(m), well under the specimens' toughness.

- `fcgr paris <R> [<heat>]`: a constant-amplitude test at R, ten points spaced evenly on a log scale from a top dK of
  45 MPa sqrt(m), or 75 (1 - R) where that is lower, down to a 3.75th of it: at R = 0.1 the test runs from 12 to
  45 MPa sqrt(m), at R = 0.8 from 4 to 15. Uses 1 test slot.
- `fcgr threshold <R> [<heat>]`: a K-decreasing test at R from dK of 14 MPa sqrt(m), or 75 (1 - R) where that is
  lower, down to the threshold, where the growth rate falls to 1e-10 m/cycle; the report also states that threshold.
  Uses 3 test slots.

The heat is H1, H2, H3 or H4; without one the specimen is from heat H1. Points where the crack grows slower than
1e-11 m/cycle are not reported.

The allowance for this assessment is 5 test slots in total; the laboratory refuses further tests once it is used.
Each report is also saved under /app/lab_reports.
"""

if __name__ == "__main__":
    main(os.path.abspath(sys.argv[1]))
