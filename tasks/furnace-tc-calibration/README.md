# furnace-tc-calibration

Diffusion bay 2 has eight vertical furnaces with five heater zones each. Every zone's controller adds a correction
to its profile thermocouple's raw reading (entered at 850 C and 1050 C, linear between) and holds the corrected
reading at the setpoint. The yearly calibration must give every zone corrections that put the wafers within 2 K of
the setpoint at 850 C and 1050 C. The records are the furnace register, the maintenance log, the 2025 TC-wafer
calibration, the corrections loaded now, four weeks of 15-minute controller trends per furnace (raw profile and
spike readings, state, setpoint, product wafers in the boat) and six documents (controller manual, thermocouple notes, TC-wafer procedure,
calibration requirement, SiC liner change summary, the new furnace's factory acceptance report). The metrology
group can run three TC-wafer temperature steps across the bay, each run choosing among a 600 C isothermal soak,
850 C and 1050 C, on the calibration day. The deliverable is `/app/output/corrections.csv`.

## Difficulty

This is a thermal-process or equipment engineer's yearly calibration of a furnace bay. Two physical effects set
each zone. The profile thermocouple drifts low, in proportion to temperature in C (an assembly 1 K low at 600 C is
1.75 K low at 1050 C). The wafer-to-junction offset is radiative: zero in an isothermal soak, growing roughly with
the fourth power of absolute temperature, and set by where the junction sits relative to the boat and wafers. The
spike thermocouple at the heater reads the junction temperature plus a heater-to-load difference that is radiative
in the same way and is set by what lies between heater and load, so spike minus raw is the drift in an isothermal
soak and the drift plus that difference at a process temperature.

The records settle much of the bay. The 2025 calibration was made with new assemblies, so it is pure offset. Any
600 C soak with the boat in and the door closed is isothermal, and the spike thermocouples were replaced at the
start of the trends, so spike minus raw there is the drift. That covers the furnace whose cracked sheath (repaired
in 2025) left it up to 3.7 K low at 600 C and the furnace whose assembly was replaced in the same well. One doping
furnace, F6, has had a cracked profile sheath since September and its replacement assembly arrives after the
calibration; its drift is growing (1.4 to 4.0 K per month at 1000 C, by zone). Its only isothermal soak is a
ten-hour operator hold on 15 September, logged as `hold`, four weeks before the calibration; the steady rise of its
spike minus raw at its 850 C process setpoint carries the drift forward. As loaded today, 27 of the 40 zones miss,
by up to 17.2 K.

The records leave three furnaces open, and there are three steps: F3 (a POCl3 doping furnace that never soaks, so
its drift, 4 to 8 K at 600 C, is unknown, and whose 2026 SiC liner changed its offset), F5 (process tube replaced;
the thermocouple well is part of the tube, so its offsets moved by -2.5 to +3.7 K) and F8 (only the vendor's
factory profile, taken with a different tube and boat, up to 3.1 K off). One process step per furnace gives both
corrections, because the 2025 data show the 850 C offset is a fixed fraction (0.40) of the 1050 C offset. F3's
step has to settle its drift and its offset together: at 1050 C, its spike minus raw there and on its 850 C trend
separate the drift (proportional to temperature) from the heater-to-load difference (radiative).

The hard part is the other two retrofitted furnaces, F2 and F7, which no step is left for. Their liners are
slip-cast and vary in wall thickness, so each shields its zones differently: the offset change is +3 to +9 K on F2,
+3 to +7 K on F3 and +1 to +3 K on F7 at 1050 C. F3's change carried over to them misses by 4.4 K. The liner is an
extra shield between heater and load, so it also raises the heater-to-load difference, and that rise is in every
furnace's trend: spike minus raw at the process setpoint less the drift there, against the bare-quartz furnaces of
the same model, which agree zone by zone. The rise is +6 to +14 K on F2, +4 to +10 K on F3 and +2 to +4 K on F7. The
two changes come from one shield, so they keep one ratio; F3, measured, gives it (0.65), and F2 and F7 take their own
rise times that ratio. Since July, F2 and F7 run the low-volume lots, whose boats are not filled with dummies
(maintenance log); a partial boat absorbs less heat and shows a smaller heater-to-load difference (controller
manual), and most of their process rows are partial boats (50 to 100 of 150 wafers). Their rise has to be read on
full boats, or with the boat load as a regressor; read over every process row it comes out low and misses by 4.3 K.
A step spent on a second retrofitted furnace to check the liner, on F6 or on a second F3 temperature leaves F5 or F8
unmeasured (3.4 to 4.0 K).

The bay, its records, trends and run readings are synthetic, written by the disclosed generator in
`authoring/provenance/` from the sealed definition.

## Reference solution

`solution/solve.py` (run by `solution/solve.sh`) takes drift at 600 C as the median spike minus raw over the
600 C rows logged as standby or hold, carried to the calibration by the slope of spike minus raw on the furnace's
process rows (scaled to 600 C) and to 850 C and 1050 C by T / 600; the 850/1050 offset ratio is the least-squares
slope of the 2025 offsets (0.399). From the records it lists what they cannot settle (no site calibration: F8; tube
replaced after the 2025 calibration: F5; no isothermal rows: F3) and runs each at 1050 C. For F3 it carries its
850 C spike minus raw to the calibration along the same line and solves spike minus raw at 850 C and 1050 C for the
drift and the heater-to-load difference (each at the junction's own temperature); the run's wafer minus raw less
the drift is the new offset, and its change from 2025 is F3's liner change. Every other furnace's heater-to-load
difference comes from its process trend on full boats (spike minus raw less the drift there, over the radiative shape); the
median over the bare-quartz T-200 furnaces (F1, F4, F5, F6) is the baseline, and each retrofitted furnace's rise
over it, zone by zone, times F3's ratio of liner change to rise gives its liner change. Measured furnaces take the
measured correction at 1050 C and, at 850 C, the drift plus the ratio times the 1050 C offset; F2 and F7 take their
2025 offsets plus their liner change plus their drift; the rest take the 2025 offsets plus their drift. On the
shipped bay every zone is within 0.98 K. It never reads the sealed definition or the verifier.

## Verification

`tests/grade_tc.py` loads each submitted pair of corrections into the sealed definition (`tests/tc.py`, the module
that also drives the run service), holds the corrected reading at 850 C and 1050 C, and computes the wafer
temperature from the zone's true drift on the calibration day and its true offset, both at the junction's actual
temperature. Every zone must be within 2 K at both temperatures; the file must carry the columns `furnace`, `zone`,
`correction_850_c` and `correction_1050_c`, one row for each of the 40 zones and no others, and finite values. The
record goes to `/logs/verifier/metrics.json`.

The 2 K is process engineering's requirement from the documents. Against it (worst-zone wafer error, K):

- `authoring/evidence/method_spread.txt`: 12288 sound calibrations: every complete three-step plan in every run
  order, four estimates of the offset ratio (least squares or median of the 2025 data, the T^4 law zero at 600 C,
  the factory table), median or mean soak readings, F6's growth from a fitted line or from the first and last two
  days, F3's split evaluated at the junction or at the setpoints with its 850 C trend carried by the line or by the
  last two days, and the bare-quartz baseline as the median or mean of the four quartz T-200 furnaces or of the three
  that soak in standby, and partial boats left out or kept with the boat load as a regressor. All pass; the worst is
  1.05 K.
- `authoring/evidence/route_study.txt`: shortcuts on the reference plan and plans that spend the steps differently.
  F3's liner change carried over to F2 and F7 4.4 K; F2's and F7's partial boats read as full boats 4.3 K; liner
  change not applied 8.6 K; F6's hold used as read 4.0 K;
  F6's hold not read 6.5 to 6.8 K; drift not carried to temperature 5.9 K; offset ratio taken in proportion to
  temperature 3.9 K; drift carried in kelvin, against the stated factor, 2.2 K; a step on a second retrofitted
  furnace, on F6 or on a second F3 temperature 3.4 to 4.0 K; F3 run at 850 C (which repeats its trend) or not run
  8 to 17 K. Three slips still pass: the T^4 law without the zero at 600 C (1.4 K), F3's split on its four-week mean
  trend (1.0 K; F3 grows slowly) and F6's 850 C growth added as if it were 600 C drift (1.6 K).
- `authoring/evidence/campaign_study.txt`: all 2024 ways to place the three steps, each with every defensible
  fallback for what it leaves unmeasured. The 4 that pass are exactly those that run F3 at 1050 C and F5 and F8 at a
  process temperature; every other placement misses by at least 3.25 K.

`methods.py` is the shared engine of the three studies; it emulates runs with the service's own function and
seeds, and uses the sealed definition only for that, for the calibration date and for grading.

## Layout

- `environment/`: one image. Records in `/app/data`; the run service in `environment/tcwafer/` (installed to
  `/opt/tcwafer`, owned by the `metrology` user, mode 700; step count in `/var/lib/tcwafer`, also 700);
  `start-tcwafer` starts it through one sudo rule; reports, dated with the calibration day, are written to
  `/app/runs`. The agent runs as `agent` (`[agent] user`), which cannot read the service's files or state, signal it
  or reset its count. `/app` is root's with the sticky bit (group-writable for `agent`), so the agent can create its
  own files there but cannot rename or replace `/app/runs`. The service creates each report as a new file inside
  the directory it opened at start (no links followed, nothing overwritten), refuses a report directory it does not
  own, and counts an unreadable or inconsistent step record as no steps left.
- `tests/`: verifier (separate container, no network).
- `solution/`: reference.
- `authoring/provenance/`: the generator (`gen.py`) and the sealed definition it reads (`tc.py`); the documents in
  `environment/data/docs` are written by hand. `authoring/evidence/`: the three studies, `preflight.py` (bundle) and
  `check_instruction.py` (instruction.md); `authoring/instruction-fact-sheet.md`: what instruction.md must state.

The fab, the furnaces, the vendor and the records are fictional; the data are synthetic.
