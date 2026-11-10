"""Writes the agent's documents and the sealed files from isim.py.

    python3 authoring/provenance/gen.py OUTDIR

OUTDIR/data    the documents installed read-only at /app/data
OUTDIR/sealed  isim.py and seed.json for the meter and the verifier

The survey is the contractor's: the band levels its meter indicated at each position of each machine's array, with
that machine running alone, and the background with all three off. Its scatter comes from isim.SURVEY_SEED, so the
records do not move with the laboratory seed. The register gives the nominal survey radius; the position table gives
the radius each position was set at. The maintenance log records what has been done to the hall and to the machines,
with dates, and nothing about what any of it does to a level.
"""
import csv
import os
import shutil
import sys

import numpy as np

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import isim as S  # noqa: E402

LP = ["lp_%s" % S.LABEL[b] for b in S.BANDS]

STD = """# Plant standard NS-7: the sound power of a machine in the compressor hall

The sound power level of a packaged machine is determined in each octave band from 63 Hz to 8 kHz, and as an
A-weighted level, from the sound pressure levels measured on a measurement surface around it while it runs alone.
Levels are in decibels. The machine is taken as it stands at the date of the determination.

## 1 The measurement surface

The surface is the one through the positions of the machine's array, at the radius the array was set at. A machine
standing %(clear).1f m or more from every wall radiates into a half space and its surface area is 2 pi r^2. A machine standing
closer than that to a wall radiates into a quarter space: its surface area is pi r^2 and its positions lie on the
available arc.

## 2 Valid positions

A position lies on the measurement surface. A position set at another radius is not a valid position. A position at
which the level with the machine running exceeds the level with every machine off by less than %(bg).0f dB in any band is
not a valid position. At least %(minp)d valid positions are needed.

## 3 Reduction

At each valid position the level with every machine off is subtracted from the level with the machine running, band by
band and position by position, in energy. The surface sound pressure level of the band is the energy average of those
levels over the valid positions:

    Lp = 10 lg ( (1/N) sum 10^(0.1 Lp,i) )

and the sound power level of the band is

    Lw = Lp + 10 lg (S / S0) - K2,   S0 = 1 m2

where K2 is the environmental correction of the hall,

    K2 = 10 lg (1 + 4 S / A).

A is the equivalent absorption area of the hall in that band, as the hall is at the date of the determination. It is
determined either from the hall's reverberation time T,

    A = %(sc).3f V / T,

with V the volume of the hall, or from a source of known sound power level standing in the hall, by the same relation
between level and surface as above applied to that source. The sound field of the hall away from the machines is
diffuse, so one station is enough for a reverberation measurement.

## 4 Corrections

The correction on the certificate of the instrument that took a level is added to the level as indicated.

Levels measured with the machine at a speed other than its rated speed are referred to the rated speed by adding

    50 lg (n_rated / n)

to every band.

Where a machine has been modified since the levels were measured, those levels are referred to the machine as it
stands now by adding, band by band, the difference between the level measured now and the level measured then at one
position of its own array, the hall being unchanged between the two. Where the modification is a part whose insertion
loss is certified by its supplier, the certified figures may be used in place of that measurement.

## 5 The A-weighted level

    LwA = 10 lg sum 10^(0.1 (Lw + Aw))

over the eight bands, with the weightings

| Band (Hz) | %(bands)s |
|---|%(dashes)s|
| Aw (dB) | %(aw)s |

## 6 Repeatability

One reading of a band level by a class 1 instrument on a steady source repeats to %(noise).2f dB, one standard deviation. One
reverberation time reading repeats to %(rt).0f per cent.
"""

ROOM = """# Compressor hall: acoustic commissioning report

Issued %(date)s, on the completion of the hall.

The hall is %(L).1f m by %(W).1f m, %(H).1f m to the underside of the roof steel, a volume of %(V).0f m3. The walls and floor are
painted concrete. The east wall is louvred over its upper half to the adjacent bay. Absorptive panels are fitted to
the ceiling over bays 2 and 3.

Reverberation time measured in the empty hall, at the centre station, as the hall was handed over:

| Band (Hz) | %(bands)s |
|---|%(dashes)s|
| T (s) | %(t60)s |

Away from the machines the sound field of the hall is diffuse: the levels measured at the four stations of the
commissioning agreed to within 0.4 dB in every band.
"""

METER_HEAD = """# Instrument certificates

Correction to be added to the indicated band level of each instrument, as calibrated.

| Band (Hz) | %(bands)s |
|---|%(dashes)s|
%(rows)s
"""
METER_NOTES = {
    "M-2": "class 1 sound level meter with octave filters, calibrated 2026-09-15, WS-2 windscreen fitted",
    "M-5": "class 1 sound level meter with octave filters, calibrated 2026-09-02, no windscreen",
    "M-9": "class 1 sound level meter with octave filters, calibrated 2026-09-08, WS-5 windscreen fitted",
    "M-7": "class 1 sound level meter with octave filters and decay analyser, calibrated 2026-10-28, no "
           "windscreen; the instrument of the laboratory booking",
}

SURVEY = """# Acceptance survey of C1 to C8

Carried out on %(dates)s by the supplier's acoustic contractor.

Each machine was run alone at its working load and its array was walked in one pass; the level recorded at a position
is the time average over 30 s, as indicated. The arrays are those of `positions.csv`, which governs which array a
position belongs to. The speed of the machine during its own pass is in the speed column of `survey_levels.csv`, and
the instrument that read each position is in its meter column.

The survey ran over three days. M-2 was at the calibration house when it began, so the first day was walked with M-5;
M-2 was used on the second day, and M-9 on the third.

The levels with every machine off were recorded at every position, with the instrument that read that position, and
are in `background_levels.csv`. The adjacent bay was in its normal service throughout.

The column `lpa` of `survey_levels.csv` is the A-weighted sound pressure level at the position, from the same
indications.

The contractor's own reduction to sound power is not part of this record: the plant's acoustic consultant did not
accept it, and the determination is to be made again from the measured levels above.
"""

ROOMCHECK = """# Room check of the survey: reference sound source RSS-1

A reference sound source was stood on the floor in the open part of the hall, clear of every wall by more than
%(clear).1f m, and the level around it was measured on a hemisphere of %(r).1f m at the six positions R1 to R6 of
`rss_levels.csv`, with instrument %(meter)s, in the same pass as the rest of the survey. The levels with every machine
and the source off are those of `background_levels.csv` away from the louvred wall.

Calibration certificate of RSS-1, sound power level by octave band, as supplied:

| Band (Hz) | %(bands)s |
|---|%(dashes)s|
| Lw (dB) | %(lw)s |

The source was run alone, with all eight packages shut down.
"""

LAB = """# Laboratory booking: instrument M-7

Two commands, run from `/app`:

    slm <position> <state>

one reading of the eight band levels at a position, dB as indicated by M-7, with `state` one of %(states)s:
which machine is running while the reading is taken, `off` for none of them and `all` for every one. `c1` is C1 and
so on through `c8`. Every machine runs at its rated speed and the adjacent bay is in its normal service.

    rt <position>

one reverberation time measurement at a position: the decay time of the eight bands, in seconds.

Positions are those of `positions.csv`. The two commands draw on one booking of %(budget)d readings in all. Each report is
printed and saved under `/app/lab_reports`.
"""


# the plant's maintenance log: work orders, with no acoustic comment on any of them
LOG = [
    ("2025-05-14", "C2", "WO-2811 Package: oil filter and separator elements changed; oil sample to the laboratory."),
    ("2025-05-29", "", "WO-2824 Hall: emergency lighting units 4 and 7 replaced."),
    ("2025-06-05", "C4", "WO-2832 Package: inlet filter panels changed."),
    ("2025-06-10", "C1", "WO-2838 Package: inlet filter panels changed; differential gauge reset."),
    ("2025-06-24", "C3", "WO-2851 Package: coupling guard refitted after the quarterly inspection."),
    ("2025-07-01", "C5", "WO-2859 Package: inlet filter panels changed."),
    ("2025-07-05", "C7", "WO-2863 Package: oil sample taken; result within limits."),
    ("2025-07-08", "", "WO-2866 Hall: floor drain in bay 1 rodded."),
    ("2025-07-21", "C2", "WO-2879 Package: vibration route readings taken; all within the alert band."),
    ("2025-08-05", "C1", "WO-2894 Package: oil cooler fan motor bearings regreased."),
    ("2025-08-19", "", "WO-2908 Hall: roller shutter door 2 track realigned."),
    ("2025-09-02", "C3", "WO-2921 Package: inlet filter panels changed."),
    ("2025-09-16", "C1", "WO-2934 Package: condensate drain valve replaced."),
    ("2025-09-30", "C2", "WO-2948 Package: oil change and filter elements; sample to the laboratory."),
    ("2025-10-07", "C4", "WO-2955 Package: oil change and filter elements; sample to the laboratory."),
    ("2025-10-14", "", "WO-2962 Hall: fire detection heads cleaned, bays 1 to 4."),
    ("2025-10-28", "C1", "WO-2976 Package: intercooler drain line cleared."),
    ("2025-11-05", "C6", "WO-2983 Package: inlet filter panels changed."),
    ("2025-11-08", "C8", "WO-2986 Package: vibration route readings taken; all within the alert band."),
    ("2025-11-11", "C3", "WO-2989 Package: motor terminal box gland replaced."),
    ("2025-11-25", "C2", "WO-3003 Package: inlet filter panels changed; gauge reset."),
    ("2025-12-09", "", "WO-3017 Hall: ventilation louvre actuator on the east wall serviced."),
    ("2025-12-18", "C1", "WO-3029 Package: vibration route readings taken; all within the alert band."),
    ("2026-01-13", "C3", "WO-3044 Package: oil change and filter elements."),
    ("2026-01-27", "", "WO-3058 Hall: lighting survey; 6 fittings relamped."),
    ("2026-02-03", "C4", "WO-3065 Package: vibration route readings taken; all within the alert band."),
    ("2026-02-10", "C2", "WO-3072 Package: cooling water strainer cleaned."),
    ("2026-02-24", "C1", "WO-3086 Package: inlet filter panels changed."),
    ("2026-03-03", "C5", "WO-3093 Package: oil change and filter elements."),
    ("2026-03-06", "C7", "WO-3096 Package: cooling water strainer cleaned."),
    ("2026-03-10", "C3", "WO-3100 Package: vibration route readings taken; all within the alert band."),
    ("2026-03-24", "", "WO-3114 Hall: eyewash station recommissioned."),
    ("2026-04-07", "C2", "WO-3128 Package: oil cooler cleaned on the water side."),
    ("2026-04-14", "C8", "WO-3135 Package: inlet filter panels changed; gauge reset."),
    ("2026-04-17", "C6", "WO-3138 Package: oil sample taken; result within limits."),
    ("2026-04-21", "C1", "WO-3142 Package: condensate drain valve replaced."),
    ("2026-05-04", "", "WO-3155 Adjacent bay: ventilation blower VB-2 commissioned and handed over; it runs "
                       "continuously."),
    ("2026-05-19", "C3", "WO-3169 Package: inlet filter panels changed."),
    ("2026-05-26", "C4", "WO-3176 Package: cooling water strainer cleaned."),
    ("2026-06-02", "C2", "WO-3183 Package: vibration route readings taken; all within the alert band."),
    ("2026-06-15", "", "WO-3380 Bays 2 to 4: roof deck leak over the walkway; ceiling lining panels taken down for "
                       "access."),
    ("2026-06-18", "", "WO-3391 Bays 2 to 4: roof deck patched and tested; the lining panels were not refitted "
                       "(MOC-402 raised)."),
    ("2026-06-30", "C1", "WO-3402 Package: oil change and filter elements; sample to the laboratory."),
    ("2026-07-03", "C7", "WO-3406 Package: inlet filter panels changed."),
    ("2026-07-06", "C5", "WO-3408 Package: vibration route readings taken; all within the alert band."),
    ("2026-07-09", "", "WO-3410 Hall: crane runway inspection, no defects."),
    ("2026-07-14", "C3", "WO-3415 Package: motor space heater replaced."),
    ("2026-07-23", "C2", "WO-3421 Package: inlet filter panels changed; gauge reset."),
    ("2026-08-04", "C1", "WO-3428 Package: intercooler drain line cleared."),
    ("2026-08-07", "C4", "WO-3430 Package: inlet filter panels changed; gauge reset."),
    ("2026-08-12", "", "WO-3433 Hall: east wall louvre blades washed down."),
    ("2026-08-18", "C6", "WO-3435 Package: cooling water strainer cleaned."),
    ("2026-09-08", "C6", "WO-3448 Package: drive speed limit set to %(c6low)d rpm at the variable speed drive "
                         "pending the impeller inspection."),
    ("2026-10-12", "C6", "WO-3486 Package: drive speed limit removed; the package runs at its rated %(c6hi)d rpm."),
    ("2026-08-20", "C3", "WO-3437 Package: coupling alignment checked after the motor was refitted."),
    ("2026-08-26", "C5", "WO-3438 Package: drive speed limit set to %(c5low)d rpm at the variable speed drive while "
                         "the inlet guide vanes are away for overhaul."),
    ("2026-09-02", "C2", "WO-3445 Package: cooling water strainer cleaned."),
    ("2026-09-09", "C2", "WO-3450 Package: drive speed limit set to %(c2low)d rpm at the variable speed drive for "
                         "the plant trial."),
    ("2026-09-11", "C1", "WO-3440 Package: oil change and filter elements; drive-end access cover removed for the "
                         "pump change and left off for the oil sample."),
    ("2026-09-12", "C8", "WO-3452 Package: inlet guard refitted after the cooler fan change."),
    ("2026-09-13", "C7", "WO-3454 Package: oil sample taken; result within limits."),
    ("2026-09-14", "", "WO-3455 Hall: acceptance survey of C1 to C8 by the supplier's contractor (survey report); "
                       "machines run one at a time at their working load."),
    ("2026-09-17", "C3", "WO-3460 Package: inlet filter panels changed."),
    ("2026-09-20", "C1", "WO-3465 Package: drive-end access cover refitted and latched; fasteners torqued."),
    ("2026-09-22", "C4", "WO-3466 Package: oil sample taken; result within limits."),
    ("2026-09-24", "", "WO-3468 Hall: walkway handrail in bay 2 repaired."),
    ("2026-09-28", "C2", "WO-3471 Package: drive speed limit removed; the package runs at its rated %(c2hi)d rpm."),
    ("2026-10-02", "C3", "WO-3478 Package: intake silencer SL-3 installed (MOC-407)."),
    ("2026-10-06", "C5", "WO-3481 Package: drive speed limit removed; the package runs at its rated %(c5hi)d rpm."),
    ("2026-10-07", "C6", "WO-3482 Package: inlet filter panels changed."),
    ("2026-10-09", "C1", "WO-3484 Package: vibration route readings taken; all within the alert band."),
    ("2026-10-15", "", "WO-3490 Hall: floor marking repainted, bays 1 to 4."),
    ("2026-10-21", "C2", "WO-3496 Package: oil cooler fan motor bearings regreased."),
    ("2026-10-24", "C4", "WO-3499 Package: vibration route readings taken; all within the alert band."),
    ("2026-10-28", "", "WO-3502 Hall: fire extinguishers serviced."),
    ("2026-09-10", "C7", "WO-3447 Package: acoustic lagging stripped from the discharge pipework to change the "
                         "non-return valve (MOC-409)."),
    ("2026-10-05", "C7", "WO-3480 Package: acoustic lagging on the discharge pipework refitted (MOC-409)."),
    ("2026-10-30", "C7", "WO-3504 Package: oil change and filter elements."),
    ("2026-11-01", "C4", "WO-3506 Package: inlet filter panels changed."),
    ("2026-11-02", "C8", "WO-3507 Package: vibration route readings taken; all within the alert band."),
    ("2026-11-03", "C3", "WO-3509 Package: condensate drain valve replaced."),
]


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


def bandrow(fmt, src):
    return " | ".join(fmt % src[b] for b in S.BANDS)


def main(outdir):
    data = os.path.join(outdir, "data")
    bands = " | ".join(S.LABEL[b] for b in S.BANDS)
    dashes = "|".join("---" for _ in S.BANDS)
    rng = np.random.default_rng([S.SURVEY_SEED, 7])

    note = {
        "C2": "inlet filter housing extended 2024; package otherwise to the original build",
        "C4": "spare rotor fitted 2025 to the original drawing",
        S.CERTIFIED: "SL-7 pipework lagging system, certified insertion loss by octave band %s dB" % "/".join(
            "%.1f" % S.MACHINES[S.CERTIFIED]["sdelta"][b] for b in S.BANDS),
        "C8": "cooler fan upgraded to the Mk 2 wheel 2026",
    }
    wcsv(data, "machines.csv",
         ["machine", "description", "rated_speed_rpm", "nominal_survey_radius_m", "wall_clearance_m",
          "guaranteed_lwa_db", "note"],
         [[m, j["desc"], "%.0f" % j["rated"], "%.1f" % S.NOMINAL_R,
           "%.1f" % S.WALL[m], "%.0f" % S.GUARANTEE[m], note.get(m, "")]
          for m, j in S.MACHINES.items()])

    compass = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]

    def bearing(arc):
        return compass[int(round(arc / 22.5)) % 16]

    wcsv(data, "positions.csv", ["position", "machine", "radius_m", "height_m", "bearing"],
         [[p, j["machine"], "%.2f" % j["r"], "%.1f" % j["height"], bearing(j["arc"])] for p, j in S.POS.items()])

    rows = []
    for m, j in S.MACHINES.items():
        for p in j["positions"]:
            v = S.lab_slm(p, m.lower(), rng, config="survey", survey=True)
            lpa = 10.0 * np.log10(sum(10.0 ** (0.1 * (x + S.AW[b])) for x, b in zip(v, S.BANDS)))
            rows.append([S.MISLABEL.get(p, m), p, S.meter_of(p), "%.0f" % j["survey_rpm"]]
                        + ["%.1f" % x for x in v] + ["%.1f" % lpa])
    wcsv(data, "survey_levels.csv", ["machine", "position", "meter", "speed_rpm"] + LP + ["lpa"], rows)

    wcsv(data, "background_levels.csv", ["position", "meter"] + LP,
         [[p, S.meter_of(p)] + ["%.1f" % x for x in S.lab_slm(p, "off", rng, survey=True)] for p in S.POS])

    rpm = {"c2low": S.MACHINES["C2"]["survey_rpm"], "c2hi": S.MACHINES["C2"]["rated"],
           "c5low": S.MACHINES["C5"]["survey_rpm"], "c5hi": S.MACHINES["C5"]["rated"],
           "c6low": S.MACHINES["C6"]["survey_rpm"], "c6hi": S.MACHINES["C6"]["rated"]}
    wcsv(data, "maintenance_log.csv", ["date", "machine", "entry"],
         [[d, m, e % rpm if "%(" in e else e] for d, m, e in sorted(LOG)])

    wtext(data, "docs/standard.md", STD % {
        "clear": S.WALL_CLEAR, "bg": S.BG_MARGIN, "minp": S.MIN_POSITIONS, "sc": S.SOUND_C, "bands": bands,
        "dashes": dashes, "aw": bandrow("%+.1f", S.AW), "noise": S.NOISE_SLM, "rt": 100 * S.NOISE_RT})
    wtext(data, "docs/room_report.md", ROOM % {
        "date": "2024-03-22", "L": S.ROOM["L"], "W": S.ROOM["W"], "H": S.ROOM["H"], "V": S.ROOM["V"],
        "bands": bands, "dashes": dashes, "t60": bandrow("%.2f", S.T60_REPORT)})
    rows = "\n".join("| %s (%s) | %s |" % (name, METER_NOTES[name], bandrow("%+.1f", S.METER[name]))
                     for name in ("M-2", "M-5", "M-9", "M-7"))
    wtext(data, "docs/meter_certificates.md", METER_HEAD % {"bands": bands, "dashes": dashes, "rows": rows})
    wtext(data, "docs/survey_report.md", SURVEY % {"dates": "14, 15 and 16 September 2026"})
    wcsv(data, "rss_levels.csv", ["position", "meter"] + LP,
         [[p, S.RSS_METER] + ["%.1f" % x for x in S.lab_rss(p, rng)] for p in S.RSS_POS])
    wtext(data, "docs/room_check.md", ROOMCHECK % {
        "clear": S.WALL_CLEAR, "r": S.RSS_R, "meter": S.RSS_METER, "bands": bands, "dashes": dashes,
        "lw": bandrow("%.1f", S.RSS_LW)})
    wtext(data, "docs/laboratory.md", LAB % {
        "budget": S.BUDGET,
        "states": ", ".join("`%s`" % x for x in S.STATES[:-1]) + " or `%s`" % S.STATES[-1]})

    sealed = os.path.join(outdir, "sealed")
    os.makedirs(sealed, exist_ok=True)
    shutil.copy(os.path.join(HERE, "isim.py"), sealed)
    shutil.copy(os.path.join(HERE, "seed.json"), sealed)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "out")
