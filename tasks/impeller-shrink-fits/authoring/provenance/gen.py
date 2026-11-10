"""Writes the agent's documents and the sealed files from isim.py.

    python3 authoring/provenance/gen.py OUTDIR

OUTDIR/data    the documents installed read-only at /app/data
OUTDIR/sealed  isim.py and seed.json for the laboratory and the verifier

The parts register predates the titanium 5th-stage impeller, and the OEM rotor data still give the original trip
setting; the maintenance log records both. The inspection report gives the seat diameters as measured on the rotor in
the overhaul bay.
"""
import csv
import json
import os
import shutil
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import isim as S  # noqa: E402

NAME = {"FV520B": "FV520B", "Ti64": "Ti-6Al-4V", "42CrMo4": "42CrMo4", "rotor": "26NiCrMoV14-5"}
REGISTER_MAT = {"S5": "FV520B"}                 # the register predates the titanium replacement
OEM_TRIP = 1.05                                  # the data sheet's trip setting, before the governor change
CERT_LIMIT = {"S2": 260}                         # the certificate predates the S2 spare's recoating (maintenance log)
NOTE = {"S2": "anti-fouling coating: do not exceed 260 C",
        "S6": "re-aged at 430 C after a blade-tip weld repair: do not exceed 375 C",
        "S5": "replacement impeller to OEM data sheet rev. B: do not exceed 285 C",
        "BD": "abradable labyrinth coating: do not exceed 220 C; mill test of the forging: mean expansion 20-250 C "
              "%.2f um/m K" % (S.cte("42CrMo4", 250.0) * 1e6),
        "TC": "induction-hardened thrust faces: do not exceed 190 C"}

STD = """# Plant standard RS-3: shrink-fitted rotor parts

Impellers, balance drums and thrust collars are fitted to the rotor by heating the part in an oven and sliding it onto
its seat; they are held by the fit alone. Dimensions are at 20 C.

The bore is finish-honed to Rz %(rz).1f um and to IT5 (for the seat's nominal diameter) about its specified diameter, so
the interference lies within the mean -/+ IT5 / 2. The interference that acts in the fit is the geometric interference less the smoothing of the
surfaces on fitting, 0.8 x (Rz of the bore + Rz of the seat).

1. Retention: at the least interference, at rest and at trip speed in running, the contact pressure at the seat is at
   least %(pmin).0f MPa, and an impeller's fit carries twice the stage's torque at MCS with the friction coefficient below.
2. Hub stress: at the greatest interference, at rest and at trip speed in running, the von Mises stress at the bore,
   including the hoop stress of rotation, does not exceed the part's yield strength divided by 1.2.
3. Assembly: at the oven temperature the bore clears the seat, as the rotor stands in the overhaul bay, by at least
   0.001 x the seat diameter, and the oven temperature does not exceed the part's heating limit.

In running means at the temperatures of the thermal survey (`thermal_survey.csv`).

Friction coefficient of a dry, degreased fit on rotor steel: FV520B %(mf).2f, 42CrMo4 %(mc).2f, Ti-6Al-4V %(mt).2f.

| Diameter (mm) | IT5 (um) |
|---|---|
%(it)s
"""

OEM = """# OEM rotor data, compressor C-201 (data sheet rev. B)

Maximum continuous speed (MCS): %(mcs).0f rpm. Overspeed trip: %(trip).0f %% of MCS.

Spin-test results for each impeller alone, at 20 C: the free growth of the bore diameter and the hoop stress at the
bore, at the spin-test speed. Stage power at MCS for the stage's impeller.

| Part | Spin-test speed (rpm) | Bore growth (um, on diameter) | Bore hoop stress (MPa) | Stage power at MCS (kW) |
|---|---|---|---|---|
%(rows)s

The balance drum and the thrust collar are plain rings and were not spin-tested.
"""

INSPECTION = """# Rotor C-201: seat inspection after regrind

Inspection of 2026-10-03, after the seats were reground (maintenance log of 2026-10-02). The rotor was on its stands in
the overhaul bay. Each seat was measured with a calibrated outside micrometer in two planes and two directions; the
mean is reported in `rotor_inspection.csv`, as read. The roughness Rz was measured with a stylus instrument.

| Instrument | Range (mm) | Seats | Calibration of 2026-09-14: error (indication less true value) |
|---|---|---|---|
| M-113 | 75-100 | TC | %(e113)+.3f mm |
| M-114 | 100-125 | S1-S6, BD | %(e114)+.3f mm |

Bay and rotor temperature during the inspection: %(t).1f C. Roundness and taper of every seat within 3 um.
"""

LAB = """# Materials laboratory

    cte <material> <T>

reports the mean coefficient of expansion of a sample of the material from 20 C to T (%(t0)d to %(t1)d C), from a
dilatometer, with a repeatability of %(u).1f %% (one standard deviation). Materials: FV520B, Ti-6Al-4V, 42CrMo4,
26NiCrMoV14-5 (the rotor forging).

Run it from `/app`; each report is printed and saved under `/app/lab_reports`. The laboratory is booked for %(budget)d tests
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
    J = S.PARTS
    wcsv(data, "parts_register.csv", ["part", "description", "seat_nominal_mm", "hub_outside_diameter_mm",
                                      "hub_length_mm", "material"],
         [[k, j["desc"], "%g" % j["d"], "%g" % j["D"], "%g" % j["L"], REGISTER_MAT.get(k, NAME[j["mat"]])]
          for k, j in J.items()])
    wcsv(data, "material_certificates.csv", ["part", "material", "yield_strength_MPa", "heating_limit_C", "note"],
         [[k, NAME[j["mat"]], "%.0f" % j["Re"], "%.0f" % CERT_LIMIT.get(k, j["Tlim"]), NOTE.get(k, "")] for k, j in J.items()])
    wcsv(data, "rotor_inspection.csv", ["part", "seat_diameter_mm", "seat_Rz_um"],
         [[k, "%.3f" % S.reading(j), "%.1f" % j["Rz_s"]] for k, j in J.items()])
    wtext(data, "docs/inspection_report.md", INSPECTION % {"t": S.T_BAY, "e113": 0.0, "e114": S.MIC_ERR})
    wcsv(data, "thermal_survey.csv", ["part", "hub_C", "seat_C"], [[k, "%.0f" % j["Th"], "%.0f" % j["Ts"]] for k, j in J.items()])
    wcsv(data, "materials.csv", ["material", "E_GPa", "poisson", "density_kg_m3", "expansion_20_100C_um_per_m_K"],
         [[NAME[m], "%.0f" % p["E"], "%.2f" % p["nu"], "%.0f" % p["rho"], "%.2f" % (S.cte(m, 100.0) * 1e6)]
          for m, p in S.MAT.items()])
    wcsv(data, "maintenance_log.csv", ["date", "part", "entry"], [
        ["2025-06-11", "", "Overspeed governor replaced; overspeed trip reset to 110 % of MCS."],
        ["2026-02-20", "S5", "5th-stage impeller replaced after erosion by a titanium (Ti-6Al-4V) impeller to OEM data sheet rev. B."],
        ["2026-10-02", "", "Rotor overhaul: impellers, balance drum and thrust collar removed; seats reground and measured (inspection report)."],
        ["2026-10-05", "", "Spare impellers, balance drum and thrust collar received with undersized bores for finish honing to the bore sheet."],
        ["2026-10-06", "S2", "S2 spare: anti-fouling coating stripped and renewed by the coater (type AF-40) after the part was certified: do not exceed %d C." % J["S2"]["Tlim"]],
    ])
    rows = "\n".join("| %s | %.0f | %.0f | %.0f | %.0f |" % (k, j.get("spin", S.MCS), j["g_mcs"], j["h_mcs"], j["P_kW"])
                     for k, j in J.items() if j["g_mcs"])
    wtext(data, "docs/oem_rotor_data.md", OEM % {"mcs": S.MCS, "trip": OEM_TRIP * 100, "rows": rows})
    it = "\n".join("| up to %d | %d |" % (b, v) for b, v in S.IT5)
    wtext(data, "docs/standard.md", STD % {"rz": S.RZ_BORE, "pmin": S.P_MIN, "mf": S.MU["FV520B"], "mc": S.MU["42CrMo4"],
                                          "mt": S.MU["Ti64"], "it": it})
    wtext(data, "docs/laboratory.md", LAB % {"t0": S.LAB_T[0], "t1": S.LAB_T[1], "budget": S.BUDGET,
                                            "u": 100 * S.NOISE_CTE})
    sealed = os.path.join(outdir, "sealed")
    os.makedirs(sealed, exist_ok=True)
    shutil.copy(os.path.join(HERE, "isim.py"), sealed)
    shutil.copy(os.path.join(HERE, "seed.json"), sealed)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "out")
