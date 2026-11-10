"""Writes the plant's records into environment/data from the sealed definition.

    python3 authoring/provenance/gen.py [outdir]

Every number comes from isim, so the records and the definition cannot drift apart. Nothing here states a
conclusion: the standard gives the method, the data sheets give the machine as it was bought, and the registers,
the trend, the drive record and the maintenance log give what has changed since.
"""
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import isim as S  # noqa: E402

IDS = ("1A", "1B", "2A", "2B", "3A", "3B")
SEPARATOR = {1: "V-4112", 2: "V-4113"}

LOG = [
    ("2026-01-12", "K-4101", "WO-21140", "annual oil change on the frame, filters renewed, no findings"),
    ("2026-01-28", "K-4101", "WO-21188", "suction and discharge valves of throw 1 lapped, seats within limits"),
    ("2026-02-03", "P-2210", "WO-21205", "seal flush line on the condensate pump re-routed"),
    ("2026-02-14", "K-4101", "WO-21241", "crosshead guide clearance measured on all six throws, within limits"),
    ("2026-02-26", "K-4101", "WO-21277", "packing case of throw 4 repacked, rings renewed"),
    ("2026-03-05", "E-4121", "WO-21309", "second-stage after-cooler tube bundle inspected, fouling noted, "
                                         "cleaning deferred to the next shutdown"),
    ("2026-03-11", "K-4101", "WO-21330", "variable speed drive retuned after the control upgrade"),
    ("2026-03-19", "K-4102", "WO-21358", "spare train turned over by hand, no findings"),
    ("2026-03-27", "K-4101", "WO-21390", "lube oil cooler cleaned, differential restored"),
    ("2026-04-02", "TI-3201", "WO-21412", "third-stage suction temperature element re-terminated at the bottle "
                                          "boss; loop calibrated against a dry block, error 0.3 K"),
    ("2026-04-15", "K-4101", "WO-21455", "throw 5 piston rings renewed, rod run-out checked"),
    ("2026-04-21", "V-4111", "WO-21478", "feed separator level bridle flushed"),
    ("2026-05-06", "K-4101", "WO-21516", "valve covers of throws 3 and 4 torqued to the revised figure"),
    ("2026-05-13", "K-4101", "WO-21540", "performance run on all six cylinders; indicator cards taken with every "
                                         "clearance pocket closed"),
    ("2026-05-22", "K-4102", "WO-21571", "spare train barring gear motor replaced"),
    ("2026-06-02", "K-4101", "WO-21604", "throw 4 liner found scored past the honing limit at the inspection; "
                                         "liner withdrawn for re-boring and a new piston ordered"),
    ("2026-06-09", "E-4122", "WO-21633", "third-stage after-cooler fan belts renewed"),
    ("2026-06-18", "K-4101", "WO-21661", "throw 4 liner refitted after re-boring and the new piston fitted"),
    ("2026-06-25", "K-4101", "WO-21690", "throw 2 packing vent piping renewed"),
    ("2026-07-01", "PI-3104", "WO-21712", "third-stage suction pressure transmitter calibrated"),
    ("2026-07-08", "K-4101", "WO-21738", "clearance pockets of throws 3 and 5 opened at the process engineer's "
                                         "request"),
    ("2026-07-16", "K-4101", "WO-21766", "frame foundation bolts checked for tightness"),
    ("2026-07-23", "V-4112", "WO-21791", "first interstage separator demister pad renewed"),
    ("2026-07-30", "K-4101", "WO-21819", "throw 5 crosshead pin found out of round at the inspection; running "
                                         "assembly refitted with a new pin and bush"),
    ("2026-08-06", "K-4101", "WO-21844", "suction valves of throw 6 renewed"),
    ("2026-08-19", "V-4113", "WO-21882", "second interstage separator taken out of service with a leaking level "
                                         "bridle and bypassed at the inlet spool"),
    ("2026-08-27", "K-4101", "WO-21910", "frame vibration survey, all throws within the alarm setting"),
    ("2026-09-04", "E-4121", "WO-21938", "second-stage after-cooler cleaning deferred again"),
    ("2026-09-11", "K-4101", "WO-21966", "throw 1 and throw 2 valve seats inspected through the covers"),
    ("2026-09-18", "K-4102", "WO-21994", "spare train suction strainer renewed"),
    ("2026-09-25", "K-4101", "WO-22021", "oil mist eliminator element renewed"),
    ("2026-10-02", "V-4111", "WO-22048", "feed sample drawn at the feed separator outlet and sent to the "
                                         "laboratory; the result is filed as gas_analysis_feed.csv"),
    ("2026-10-09", "K-4101", "WO-22077", "distance piece vent flows checked on all six throws"),
    ("2026-10-14", "K-4101", "WO-22092", "throw 6 running assembly withdrawn complete at the inspection and the "
                                         "spare assembly fitted"),
    ("2026-10-16", "K-4101", "WO-22105", "throw 3 and throw 4 rider band wear measured, within limits"),
    ("2026-10-23", "PI-1102", "WO-22133", "field suction pressure transmitter calibrated"),
    ("2026-10-28", "K-4101", "WO-22158", "OEM service bulletin SB-4101-11 entered against the machine"),
    ("2026-11-03", "K-4101", "WO-22184", "reciprocating weights of throws 2, 4 and 6 called for by the turndown "
                                         "study"),
    ("2026-11-05", "E-4120", "WO-22196", "feed cooler differential checked, normal"),
]


def wcsv(path, head, rows):
    with open(path, "w") as f:
        f.write(",".join(head) + "\n")
        for r in rows:
            f.write(",".join(str(x) for x in r) + "\n")


def standard():
    return """# RC-4  Lowest allowable field pressure of a reciprocating booster

Plant standard RC-4, revision 8. Applies to every reciprocating compressor cylinder on the plant.

## 1  Purpose

A booster on a declining field reaches a mechanical or a process limit at some field pressure. This standard fixes
how that pressure is found for each cylinder and how it is reported, so that the figure is the same whoever works
it out.

## 2  The duty

The unit takes suction from the field and discharges into the pipeline. The field pressure, the pipeline pressure
and the contract flow the unit has to hold are in the operating record. Nothing else about the duty is set.

### 2.1  The pressures between the stages

They are not set by anyone. They settle where each stage passes the molar flow the stage before it delivers, less
whatever the separator between them knocks out as condensate:

    n(stage 2) = n(stage 1) * ( 1 - f1 )
    n(stage 3) = n(stage 2) * ( 1 - f2 )

with f1 and f2 the condensate fractions of the two interstage separators. A separator that is out of service knocks
nothing out.

The molar flow of a stage, per revolution of the frame, is

    n = ( p_suction - %.2f ) * V_stage / ( R * T_suction )

in absolute units, with R the molar gas constant, T_suction the suction temperature at the valve flange of 2.4, and

    V_stage = sum over the stage's cylinders and over each end of ( V_end * E_v,end )

the swept volume of each end times that end's volumetric efficiency of 2.5. The two equations leave one pressure
between the first and second stages and one between the second and third; they are to be found to within 0.001 bar.

### 2.2  The speed

The contract flow is measured at the export meter, so it is the molar flow the last stage delivers. The unit has to
hold it, so the speed is whatever that flow needs at the pressures that settle:

    N = contract flow / n(stage 3)

in revolutions per unit time, with the flow and n in the same units of amount per unit time. By 2.1 the molar flow
of the last stage is the molar flow of the first less what the separators between them knock out.

### 2.3  The range

The drive may not be run above the rated speed of the frame. The range of field pressures considered therefore runs
from the field pressure of the operating record down to the lower of

- the field pressure at which the speed of 2.2 reaches the rated speed, and
- %.0f per cent of the field pressure of the operating record.

### 2.4  The suction temperature

The suction temperature of a stage is the reading of its element, as the operating record gives it. Where the
instrument schedule shows the element mounted on the suction bottle rather than at the valve flange, the
temperature at the flange is the reading plus %.0f K.

## 3  The isentropic exponent

The isentropic exponent of a stage's gas is taken from the mol-average molar heat capacity of its analysis:

    Cp_mix / R = sum over components of ( mol fraction * Cp_i / R )
    k = ( Cp_mix / R ) / ( Cp_mix / R - 1 )

The component figures are those of the plant's property table, which gives them against temperature, and they are
taken at the mean of the suction and the discharge temperature of the cylinder. The discharge temperature of 4.3 is
therefore found together with the exponent: start from the suction temperature, take the exponent at the mean,
compute the discharge temperature, and repeat until two successive discharge temperatures differ by less than
%.3f K.

The gas of a stage is the gas that enters it, which is the gas the stage before it discharges less whatever its
separator knocks out. Where a separator is out of service, the stage sees the gas of the stage before it.

## 4  The requirements

A cylinder is acceptable at a field pressure when all of the following are met at the pressures and the speed that
field pressure brings, by 2.1 and 2.2.

The pressure ratio of a cylinder is taken across its valves:

    R_p = ( p_discharge + %.2f ) / ( p_suction - %.2f )

the valve losses being this standard's figures for the valve type fitted.

### 4.1  Gas load

The gas load on the piston rod is taken through one revolution at each whole crank angle. For a double-acting
cylinder, with the head end leading, the gas load is

    F_gas = p_head * A_head - p_crank * A_crank

where the head end sees the discharge pressure and the crank end the suction pressure through the first half
revolution, and the other way about through the second. A_head is the bore area and A_crank the bore area less the
area of the piston rod. Compression is positive. The peak of its magnitude shall not exceed the maximum allowable
gas load of the cylinder, which is a rating of the cylinder body and its bolting and is on the cylinder data sheet.

### 4.2  Rod load in compression and in tension

The inertia load of the reciprocating weight is added to the gas load at the same crank angle:

    F_inertia = -m * omega^2 * r * ( cos(theta) + cos(2 theta) / L )

with m the reciprocating weight of the running assembly, omega the angular speed at the speed of 2.2, r half the
stroke, theta the crank angle from the head end dead centre and L the ratio of connecting rod length to crank
radius, which is %.1f on this frame. The peak of the sum in compression and the peak in tension shall each not
exceed the rated rod load of the throw, which is the figure on the frame data sheet as the OEM's service bulletins
revise it, or the de-rated figure of the throw where one has been issued, whichever is the lower.

### 4.3  Discharge temperature

    T_discharge = T_suction * R_p ^ ( ( k - 1 ) / k )

in absolute temperature, with T_suction the suction temperature at the valve flange of 2.4 and k the exponent of
clause 3. It shall not exceed %.0f C.

### 4.4  Volumetric efficiency and cylinder power

The volumetric efficiency of an end of a cylinder follows from that end's own clearance:

    E_v = 1 - C * ( R_p ^ ( 1 / k ) - 1 )

with C the clearance volume of that end as a fraction of that end's swept volume, as the pockets now stand. The
indicated power is the two ends added:

    P = sum over the ends of ( p_suction - %.2f ) * V_end * E_v,end * ( R_p ^ n - 1 ) / n ,    n = ( k - 1 ) / k

with V_end the swept volume of that end in volume per unit time at the speed of 2.2, and the suction pressure in
absolute units. It shall not exceed the rated power of the cylinder, which is on the cylinder data sheet.

### 4.5  Pin reversal

The combined rod load of 4.2 shall be in tension through at least %d whole degrees of the revolution, counted as
the number of whole crank angles at which it is negative.

## 5  The lowest allowable field pressure

Within the range of 2.3, the lowest allowable field pressure of a cylinder is the lowest whole %.2f bar at which
that cylinder is acceptable at that pressure and at every higher pressure in the range.

The requirement that fails at the next step below it is the governing requirement, and is reported with it under
one of these names:

    gas_load   rod_load_compression   rod_load_tension   discharge_temperature   cylinder_power   pin_reversal

## 6  The records to be used

The machine as it now stands, not as it was bought.
""" % (S.DPS, S.FIELD_FLOOR * 100.0, S.BOTTLE_OFFSET, S.TD_TOL, S.DPD, S.DPS, S.ROD_LENGTH_RATIO,
       S.TD_LIMIT, S.DPS, S.REV_MIN, S.PS_STEP)


def data_sheet():
    rows = []
    for cid in IDS:
        j = S.CYL[cid]
        rows.append("| %s | %d | %d | %.0f | %.0f | double | %.3f | %.3f | %s | %.1f | %.0f | %.0f |" % (
            cid, j["throw"], j["stage"], j["bore_plate"], j["rod"], j["clear_he_sheet"], j["clear_ce_sheet"],
            "%.0f" % j["pocket_cm3"] if j["pocket_cm3"] else "none", j["mrec_sheet"], j["kw"], j["glim"]))
    throws = "\n".join("| %d | %.0f |" % (t, S.ROD_RATED[t]) for t in sorted(S.ROD_RATED))
    gas = "\n".join("| %s | %.2f |" % (c.replace("_", " "), S.GAS_SHEET[c]) for c in S.COMPONENTS)
    return """# K-4101  three-stage reciprocating gas booster: machine data sheet

Issued with the machine. Figures are as bought. Changes since are in the overhaul register, the drive record and
the maintenance log.

## Frame

| item | value |
|---|---|
| frame | six throw, horizontal balanced opposed, two throws to a stage |
| stroke | %.0f mm |
| rated speed | %.0f rev/min |
| connecting rod length / crank radius | %.1f |
| driver | synchronous motor through a variable speed drive |

The rated speed is the highest the drive may hold continuously.

### Rated rod load by throw

| throw | rated rod load kN |
|---|---|
%s

These are the figures at issue, in compression and in tension alike. Revisions are carried in the overhaul
register.

## Cylinders

| cylinder | throw | stage | bore mm | piston rod mm | acting | clearance, head end | clearance, crank end | clearance pocket cm3 | reciprocating weight kg | rated power kW | maximum allowable gas load kN |
|---|---|---|---|---|---|---|---|---|---|---|---|
%s

Each clearance column is that end's clearance volume as a fraction of that end's own swept volume, with every
pocket closed. The pocket column is the swept volume of the pocket itself; the pockets of this machine are on the
head end.

The reciprocating weight is the weight of the running assembly as supplied: piston, piston nut, rod, crosshead
and crosshead pin.

## Separators

| separator | stands after stage | condensate fraction of the molar flow, design |
|---|---|---|
| %s | 1 | %.3f |
| %s | 2 | %.3f |

## Stage conditions, design

| stage | suction pressure bar a | discharge pressure bar a | suction temperature C |
|---|---|---|---|
| 1 | 32.0 | 58.0 | %.0f |
| 2 | 57.0 | 108.0 | %.0f |
| 3 | 106.0 | %.0f | %.0f |

## Gas analysis, design

| component | mol per cent |
|---|---|
%s

This analysis is the one the machine was sold against.
""" % (S.FRAME["stroke"], S.FRAME["rpm_rated"], S.ROD_LENGTH_RATIO, throws, "\n".join(rows),
       SEPARATOR[1], S.CONDENSATE_DESIGN[1], SEPARATOR[2], S.CONDENSATE_DESIGN[2],
       S.TS_DESIGN[1], S.TS_DESIGN[2], S.PIPE, S.TS_DESIGN[3], gas)


def register():
    fitted, removed = S.PISTON["2B"]
    der = sorted(S.DERATED)[0]
    return """# K-4101  overhaul register

Entries are made as work is closed out. The register carries dimensions and ratings; the maintenance log carries
the work.

## 2026-06-18  WO-21661  throw 4 liner and piston

Liner withdrawn 2026-06-02, scored past the honing limit. Re-bored and refitted; as-bored diameter entered in the
liner record.

New piston fitted at the same time. Shop ticket 6611: piston as fitted %.1f kg, piston removed %.1f kg. No other
part of the running assembly was changed.

## 2026-07-08  WO-21738  clearance pockets, throws 3 and 5

Both pockets opened and left open at the process engineer's request.

## 2026-07-30  WO-21819  throw %d crosshead

Crosshead pin 0.09 mm out of round at the inspection, past the 0.05 mm limit. Pin and bush renewed and the running
assembly refitted.

Crosshead bore found at the upper end of the fit range after the repair; referred to the OEM. OEM reply of
2026-08-11: rod load for throw %d limited to %.0f kN until the next inspection.

## 2026-10-14  WO-22092  throw 6 running assembly

Running assembly withdrawn complete at the inspection and the spare assembly fitted. Spare built up from a heavier
forged crosshead and a rod of the same diameter. Assembly weight: not recorded.

## 2026-10-28  WO-22158  rated rod load

Service bulletin SB-4101-11 entered against the machine; it is filed as docs/service_bulletin.md. The rated rod
load of every throw is the data sheet's figure reduced as the bulletin requires, from this date. The data sheet has
not been reissued.
""" % (fitted, removed, S.CYL[der]["throw"], S.CYL[der]["throw"], S.DERATED[der])


def bulletin():
    return """# SB-4101-11  rated rod load, R-series six throw frames

OEM service bulletin, issued 2026-10-19. Applies to every R-series six throw frame built before 2019.

## Finding

Fatigue testing of the crosshead to frame bolting completed in 2026 shows a lower endurance limit than the figure
the frames were rated against. The ratings were set from the bolting's proof load with the factor then in use.

## Action

The rated rod load of every throw of the frames covered is **reduced to %.0f per cent** of the figure on the frame
data sheet, in compression and in tension alike. The reduced figure applies to all load calculations from the date
of this bulletin.

Data sheets need not be reissued. Where a throw carries a de-rating of its own, the lower of the two figures
applies.

No change is made to the rated speed, to the stroke or to any cylinder rating.
""" % (S.BULLETIN * 100.0)


def laboratory():
    return """# Laboratory and shop services

Two services are available to the study. Both are booked against the same allowance.

## The allowance

**%d readings in all.** The allowance does not refill. Every reading is reported back and a copy is written to
`/app/lab_reports`.

## gc

    gc <stage>

Draws a sample from the stage's sample stream and reports the gas analysis, mol per cent of each component to 0.01.
The stages are 1, 2 and 3. A stage's sample stream is taken at its suction. One reading.

## weigh

    weigh <cylinder>

Has the shop weigh the reciprocating assembly of the throw and reports the weight in kg to 0.1. The cylinders are
%s. One reading.
""" % (S.BUDGET, " ".join(IDS))


def main(outdir):
    docs = os.path.join(outdir, "docs")
    os.makedirs(docs, exist_ok=True)
    for name, body in (("standard.md", standard()), ("machine_data_sheet.md", data_sheet()),
                       ("overhaul_register.md", register()), ("service_bulletin.md", bulletin()),
                       ("laboratory.md", laboratory())):
        with open(os.path.join(docs, name), "w") as f:
            f.write(body)

    wcsv(os.path.join(outdir, "cylinder_schedule.csv"),
         ["cylinder", "throw", "stage", "nominal_bore_mm", "piston_rod_mm", "acting",
          "clearance_head_end_sheet", "clearance_crank_end_sheet", "clearance_pocket_cm3",
          "reciprocating_weight_kg_sheet", "rated_power_kW", "allowable_gas_load_kN",
          "rated_rod_load_kN_sheet"],
         [[cid, S.CYL[cid]["throw"], S.CYL[cid]["stage"], "%.0f" % S.CYL[cid]["bore_plate"],
           "%.0f" % S.CYL[cid]["rod"], "double", "%.3f" % S.CYL[cid]["clear_he_sheet"],
           "%.3f" % S.CYL[cid]["clear_ce_sheet"], "%.0f" % S.CYL[cid]["pocket_cm3"],
           "%.1f" % S.CYL[cid]["mrec_sheet"], "%.0f" % S.CYL[cid]["kw"], "%.0f" % S.CYL[cid]["glim"],
           "%.0f" % S.ROD_RATED[S.CYL[cid]["throw"]]] for cid in IDS])

    liner = []
    for cid in IDS:
        j = S.CYL[cid]
        liner.append([cid, "2024-03-15", "nominal", "%.2f" % j["bore_plate"],
                      "%.2f" % (j["bore_plate"] + 0.02), "%.2f" % (j["bore_plate"] - 0.01), "WO-18802"])
        if j["bore"] != j["bore_plate"]:
            liner.append([cid, "2026-06-18", "first repair size", "%.2f" % j["bore"],
                          "%.2f" % (j["bore"] + 0.02), "%.2f" % (j["bore"] - 0.01), "WO-21661"])
    liner.sort(key=lambda r: (r[1], r[0]))
    wcsv(os.path.join(outdir, "liner_records.csv"),
         ["cylinder", "date", "size_designation", "mean_bore_mm", "largest_bore_mm", "smallest_bore_mm",
          "work_order"], liner)

    g, p12, p23, speed, _ = S.table()
    wcsv(os.path.join(outdir, "operating_record.csv"),
         ["item", "value", "unit", "instrument"],
         [["field pressure at the unit suction", "%.1f" % S.FIELD_TODAY, "bar a", "PI-1102"],
          ["pipeline pressure at the unit discharge", "%.1f" % S.PIPE, "bar a", "PI-4201"],
          ["contract flow", "%.1f" % S.CONTRACT, "kmol/h", "FI-4101"],
          ["first interstage pressure measured", "%.1f" % round(float(p12[-1]), 1), "bar a", "PI-2103"],
          ["second interstage pressure measured", "%.1f" % round(float(p23[-1]), 1), "bar a", "PI-3104"],
          ["frame speed measured", "%.0f" % round(float(speed[-1])), "rev/min", "SI-4101"],
          ["first stage suction temperature", "%.1f" % S.TS_READ[1], "C", "TI-1201"],
          ["second stage suction temperature", "%.1f" % S.TS_READ[2], "C", "TI-2201"],
          ["third stage suction temperature", "%.1f" % S.TS_READ[3], "C", "TI-3201"]])

    wcsv(os.path.join(outdir, "instrument_schedule.csv"),
         ["tag", "service", "mounting", "last_calibration", "error_K_or_bar"],
         [["TI-1201", "first stage suction temperature", "valve flange thermowell", "2026-02-18", "0.2"],
          ["TI-2201", "second stage suction temperature", "valve flange thermowell", "2026-02-18", "0.2"],
          ["TI-3201", "third stage suction temperature", "suction bottle boss", "2026-04-02", "0.3"],
          ["TI-1301", "first stage discharge temperature", "discharge bottle boss", "2026-02-18", "0.3"],
          ["TI-2301", "second stage discharge temperature", "discharge bottle boss", "2026-02-18", "0.3"],
          ["TI-3301", "third stage discharge temperature", "discharge bottle boss", "2026-02-18", "0.4"],
          ["PI-1102", "field suction pressure", "suction line", "2026-10-23", "0.05"],
          ["PI-2103", "first interstage pressure", "suction line", "2026-05-29", "0.08"],
          ["PI-3104", "second interstage pressure", "suction line", "2026-07-01", "0.10"],
          ["PI-4201", "pipeline pressure", "discharge line", "2026-05-29", "0.15"],
          ["FI-4101", "export flow", "pipeline orifice", "2026-06-11", "1.0"],
          ["SI-4101", "frame speed", "shaft end", "2026-03-11", "1"]])

    trend = []
    months = ("2026-03", "2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09", "2026-10", "2026-11")
    for i, m in enumerate(months):
        v = S.TS_DESIGN[3] + (S.TS_READ[3] - S.TS_DESIGN[3]) * i / (len(months) - 1.0)
        trend.append([m, "TI-1201", "%.1f" % S.TS_READ[1], "TI-2201", "%.1f" % S.TS_READ[2],
                      "TI-3201", "%.1f" % round(v, 1)])
    wcsv(os.path.join(outdir, "temperature_trend.csv"),
         ["month", "tag_1", "stage_1_suction_C", "tag_2", "stage_2_suction_C", "tag_3", "stage_3_suction_C"],
         trend)

    wcsv(os.path.join(outdir, "drive_record.csv"),
         ["date", "event", "speed_held_rev_min", "work_order"],
         [["2024-03-15", "commissioned", "268", "WO-18802"],
          ["2025-11-04", "field pressure stepped down; speed followed the flow", "249", "WO-20714"],
          ["2026-03-11", "drive retuned after the control upgrade", "238", "WO-21330"],
          ["2026-09-30", "quarterly check of the held speed", "%.0f" % round(float(speed[-1])), "WO-22012"]])

    a1 = S.analysis(1)
    wcsv(os.path.join(outdir, "gas_analysis_feed.csv"),
         ["date", "sample_point", "work_order", "component", "mol_per_cent"],
         [["2026-10-02", "V-4111 outlet (unit suction)", "WO-22048", c, "%.2f" % a1[c]] for c in S.COMPONENTS])

    wcsv(os.path.join(outdir, "component_properties.csv"),
         ["component", "molar_mass_kg_per_kmol"] + ["cp_over_R_at_%.0fC" % t for t in S.CP_T],
         [[c, "%.2f" % S.MW[c]] + ["%.2f" % v for v in S.CP_R[c]] for c in S.COMPONENTS])

    with open(os.path.join(outdir, "maintenance_log.csv"), "w") as f:
        f.write("date,equipment,work_order,description\n")
        for date, tag, wo, desc in LOG:
            f.write('%s,%s,%s,"%s"\n' % (date, tag, wo, desc))

    n = sum(len(files) for _, _, files in os.walk(outdir))
    print("wrote %d files to %s" % (n, outdir))


if __name__ == "__main__":
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, "environment", "data"))
