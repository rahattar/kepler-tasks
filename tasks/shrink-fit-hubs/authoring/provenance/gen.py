"""Writes the agent's documents and the sealed files from sfsim.py.

    python3 authoring/provenance/gen.py OUTDIR

OUTDIR/data    the documents installed read-only at /app/data
OUTDIR/sealed  sfsim.py and seed.json for the laboratory and the verifier

The records are the plant's as they were before the latest changes: the register still shows J10's shaft solid, J07's
assembly sheet still says light machine oil, and the duty list predates J11's motor upgrade; the maintenance log
records all three.
"""
import csv
import json
import os
import shutil
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sfsim as S  # noqa: E402

GRADE = {"J01": "C45+N", "J02": "AlSi10Mg-T6", "J03": "CuSn12-C", "J04": "42CrMo4+QT", "J05": "EN-GJS-600-3",
         "J06": "42CrMo4+QT", "J07": "EN-GJS-400-15", "J08": "EN-GJS-400-15", "J09": "42CrMo4+QT", "J10": "S355J2",
         "J11": "C45+N", "J12": "S355J2"}
LIMIT_NOTE = {"J02": "T6 temper: do not exceed 190 C", "J03": "do not exceed 230 C",
              "J04": "induction-hardened teeth, tempered 300 C: do not exceed 270 C",
              "J06": "abradable seal coating on the shroud: do not exceed 270 C",
              "J09": "induction-hardened coupling teeth, tempered 320 C: do not exceed 280 C"}
SHEET_COND = {"dry": "degreased, dry", "oiled": "light machine oil", "paste": "MoS2 assembly paste"}
REG_DI = {"J10": 0.0}                         # the register still shows J10's shaft solid
SHEET = {"J07": "oiled"}                      # the assembly sheet predates the change to paste
DUTY_FACTOR = {"J11": 55.0 / 75.0}            # the torque survey predates the motor upgrade
MATNAME = {"steel": "steel", "GJS": "ductile iron", "CuSn12": "tin bronze CuSn12", "AlSi10Mg": "aluminium AlSi10Mg"}

STD = """# Plant standard ST-9: shrink-fitted hubs

Hubs are fitted to steel shafts by heating the hub in an oven and sliding it on; the joint carries the torque by
friction alone (no key).

1. Torque: at the least interference the tolerances allow, at rest and in steady running, the joint carries 1.5 times
   the peak torque without slipping.
2. Hub stress: at the greatest interference the tolerances allow, at rest and in steady running, the equivalent
   (von Mises) stress at the hub bore does not exceed the hub material's yield strength divided by 1.2.
3. Assembly: at the heating temperature the hub bore clears the shaft by at least 0.001 x the shaft diameter at the
   greatest interference, and the heating temperature does not exceed the hub's heating limit.

The interference that acts in the joint is the geometric interference less the smoothing of the surfaces on fitting,
0.8 x (Rz of the bore + Rz of the shaft).

The drawing specifies the mean diametral interference in whole micrometres. The shaft is ground to IT5 and the bore
to IT6 about it, so the interference lies within the mean -/+ (IT5 + IT6) / 2:

| Diameter (mm) | IT5 (um) | IT6 (um) |
|---|---|---|
%(it)s

Records: `joint_register.csv`, `hub_certificates.csv`, `assembly_sheets.csv` (surface finish and preparation),
`duty.csv` (peak torques), `thermography.csv` (hub and shaft temperatures in steady running), `materials.csv`,
`maintenance_log.csv`.
"""

LAB = """# Joint laboratory

    slip <material> <dry|oiled|paste> <pressure_MPa> [shrink]

makes a 40 mm specimen joint of a hub of the material on a steel shaft, with the surface preparation given, at an
interference that gives the contact pressure stated (10 to 200 MPa), and reports the coefficient of friction from the
torque at which it slips. The specimen is pressed together on a press; with `shrink` it is assembled by heating the
hub instead. Materials: steel, ductile-iron, bronze, aluminium.

    cte <material> <T>

reports the mean coefficient of expansion of the material from 20 C to T (100 to 400 C), from a dilatometer.

Run them from `/app`; each report is printed and saved under `/app/lab_reports`. The laboratory is booked for %(budget)d tests
in all.
"""


def wcsv(out, path, header, rows):
    p = os.path.join(out, path)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", newline="") as f:
        c = csv.writer(f, lineterminator="\n")
        c.writerow(header)
        c.writerows(rows)


def wtext(out, path, text):
    p = os.path.join(out, path)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        f.write(text)


def main(outdir):
    data = os.path.join(outdir, "data")
    J = S.JOINTS
    wcsv(data, "joint_register.csv", ["joint", "part", "shaft_diameter_mm", "shaft_bore_mm", "hub_outside_diameter_mm",
                                      "hub_length_mm", "hub_material", "speed_rpm"],
         [[k, j["desc"], "%g" % j["d"], "%g" % REG_DI.get(k, j["di"]), "%g" % j["D"], "%g" % j["L"], GRADE[k],
           "%g" % j["rpm"]] for k, j in J.items()])
    wcsv(data, "hub_certificates.csv", ["joint", "hub_material", "yield_strength_MPa", "heating_limit_C", "note"],
         [[k, GRADE[k], "%.0f" % j["Re"], "%.0f" % j["Tlim"], LIMIT_NOTE.get(k, "")] for k, j in J.items()])
    wcsv(data, "assembly_sheets.csv", ["joint", "bore_Rz_um", "shaft_Rz_um", "surface_preparation"],
         [[k, "%.1f" % j["Rz_h"], "%.1f" % j["Rz_s"], SHEET_COND[SHEET.get(k, j["cond"])]] for k, j in J.items()])
    wcsv(data, "duty.csv", ["joint", "peak_torque_Nm", "source"],
         [[k, "%.0f" % (j["Tpeak"] * DUTY_FACTOR.get(k, 1.0)), "torque survey 2024"] for k, j in J.items()])
    wcsv(data, "thermography.csv", ["joint", "hub_C", "shaft_C"], [[k, "%.0f" % j["Th"], "%.0f" % j["Ts"]] for k, j in J.items()])
    wcsv(data, "maintenance_log.csv", ["date", "joint", "entry"], [
        ["2024-11-04", "J04", "Gear hub reground on the bore face; Rz unchanged."],
        ["2025-03-18", "J11", "Drive motor upgraded from 55 kW to 75 kW at the same speed (peak torque in proportion)."],
        ["2025-08-12", "J10", "Pulley shaft replaced by a hollow shaft, bore 40 mm, for the encoder cable."],
        ["2026-02-09", "J07", "Engineering memo EM-112: crane wheels to be refitted with MoS2 assembly paste against fretting."],
        ["2026-09-30", "", "All twelve hubs removed for overhaul; shafts and bores to be re-machined to the new interferences."],
    ])
    wcsv(data, "materials.csv", ["material", "E_GPa", "poisson", "density_kg_m3", "expansion_20_100C_um_per_m_K"],
         [[MATNAME[m], "%.0f" % p["E"], "%.2f" % p["nu"], "%.0f" % p["rho"], "%.1f" % (S.cte(m, 100.0) * 1e6)]
          for m, p in S.MAT.items()])
    it = "\n".join("| up to %d | %d | %d |" % (b, S.IT5[i], S.IT6[i]) for i, b in enumerate(S.BANDS))
    wtext(data, "docs/standard.md", STD % {"it": it})
    wtext(data, "docs/laboratory.md", LAB % {"budget": S.BUDGET})
    sealed = os.path.join(outdir, "sealed")
    os.makedirs(sealed, exist_ok=True)
    shutil.copy(os.path.join(HERE, "sfsim.py"), sealed)
    shutil.copy(os.path.join(HERE, "seed.json"), sealed)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "out")
