"""Writes the agent's documents and the sealed files from the sealed definition (tsim.py).

    python3 gen.py OUTDIR

OUTDIR/data      batches.csv, mill_certificates.csv, production_log.csv, supplier_tempering_curves.csv,
                 docs/procedure.md, docs/laboratory.md
OUTDIR/sealed    tsim.py and seed.json (the laboratory's scatter seed)
"""
import csv
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tsim as S  # noqa: E402

# the batch list was written before the production log's last change: B09's pinions are now from heat 41-7864
BATCH_LIST_HEAT = {"B09": "41-7731"}


def wtext(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


def wcsv(path, header, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        c = csv.writer(f, lineterminator="\n")
        c.writerow(header)
        c.writerows(rows)


PROC = """# Heat treatment procedure HT-4: hardening and tempering of alloy steel parts

1. Hardening: austenitise and quench in oil (all grades). The parts are then tempered as below without delay.
2. Tempering: the furnace setpoint is a whole degree C. The soak time at temperature is 1 h per 25 mm of ruling section,
   and at least 2 h, counted from when the load thermocouple reaches the setpoint. Grade G52 is double tempered: two
   identical tempers, with the parts cooled to room temperature between them. The lowest permitted tempering
   temperatures are 400 C for G41 and G43, 500 C for G32 and 540 C for G52.
3. Acceptance: the hardness at the location the drawing names (the surface, or half the radius of the ruling section)
   is within the drawing's range.

Grades: G41 (%(G41)s), G43 (%(G43)s), G32 (%(G32)s), G52 (%(G52)s).

Equivalent Jominy distance of oil-quenched rounds (mm), by ruling section diameter (mm):

| Diameter | Surface | Half-radius |
|---|---|---|
%(jt)s

Records: `mill_certificates.csv` (composition and Jominy hardness of each heat), `batches.csv` (the thirteen batches),
`production_log.csv`, and `supplier_tempering_curves.csv` (the steel supplier's typical tempering curves: one 2 h
temper of a 25 mm round, hardness at half-radius).
"""

LAB = """# Metallurgical laboratory

    temper <heat> <T> [<diameter_mm> <surface|half-radius>] [double]

hardens a test piece cut from the heat as production does (austenitise, oil quench), tempers it once for 2 h at T
(400 to 700 C), and reports the hardness (HRC, mean of five indentations) at the location given. With `double` the
test piece is tempered twice for 2 h at T, cooled to room temperature between the two tempers. Without a diameter the
test piece is a 25 mm round and the hardness is read at half-radius. A test piece of a larger diameter (up to 300 mm)
is cut from bar of that size. Run it from `/app`; each report is printed and saved under `/app/lab_reports`.

The laboratory furnace is booked for 11 tempers for all thirteen batches: a test tempered once uses one of them and a
test tempered twice uses two.
"""


def main(out):
    data = os.path.join(out, "data")
    certs = []
    for heat, (g, C, Mn, Si, Cr, Mo, V, Ni) in sorted(S.HEATS.items()):
        certs.append([heat, g, "%.2f" % C, "%.2f" % Mn, "%.2f" % Si, "%.2f" % Cr, "%.2f" % Mo, "%.2f" % V, "%.2f" % Ni]
                     + ["%.0f" % S.jominy(heat, J) for J in S.JDIST])
    wcsv(os.path.join(data, "mill_certificates.csv"), ["heat", "grade", "C", "Mn", "Si", "Cr", "Mo", "V", "Ni"]
         + ["jominy_HRC_at_%gmm" % J for J in S.JDIST], certs)
    rows = [[b, part, BATCH_LIST_HEAT.get(b, heat), "%.0f" % D, loc, "%.0f" % lo, "%.0f" % hi]
            for b, (part, heat, D, loc, (lo, hi)) in S.BATCHES.items()]
    wcsv(os.path.join(data, "batches.csv"), ["batch", "part", "heat", "ruling_section_diameter_mm", "hardness_location",
                                             "hardness_min_HRC", "hardness_max_HRC"], rows)
    Ts = list(range(400, 701, 25))
    wcsv(os.path.join(data, "supplier_tempering_curves.csv"), ["grade", "tempering_temperature_C", "hardness_HRC"],
         [[g, T, "%.1f" % S.supplier_curve(g, T)] for g in S.GRADES for T in Ts])
    wcsv(os.path.join(data, "production_log.csv"), ["date", "batch", "entry"], [
        ["2026-10-05", "B03", "Gear blanks forged and normalised; ruling section 200 mm after rough machining."],
        ["2026-10-12", "B09", "Pinion bar stock: heat 41-7731 used up; pinions cut from heat 41-7864 (same grade, "
                              "certificate on file)."],
        ["2026-10-14", "B07", "Die block rough-machined; ruling section 300 mm."],
        ["2026-10-16", "B06", "Die insert blanks upset-forged from heat 52-1312 bar; ruling section 200 mm."],
        ["2026-10-19", "", "All thirteen batches hardened (austenitised and oil quenched) per HT-4; awaiting tempering."],
    ])
    jt = "\n".join("| %d | %.1f | %.1f |" % (D, S.JTAB["surface"][i], S.JTAB["half-radius"][i])
                   for i, D in enumerate(S.JTAB_D))
    wtext(os.path.join(data, "docs", "procedure.md"), PROC % dict(jt=jt, **{g: S.GRADES[g]["desc"] for g in S.GRADES}))
    wtext(os.path.join(data, "docs", "laboratory.md"), LAB)
    sealed = os.path.join(out, "sealed")
    os.makedirs(sealed, exist_ok=True)
    shutil.copyfile(os.path.join(HERE, "tsim.py"), os.path.join(sealed, "tsim.py"))
    shutil.copyfile(os.path.join(HERE, "seed.json"), os.path.join(sealed, "seed.json"))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "out")
