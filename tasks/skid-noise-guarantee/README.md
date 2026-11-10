# skid-noise-guarantee

> **Status: not shipped.** Complete and preflight-clean, but it does not meet the easiness gate: low-effort probes
> solved it 3 of 3 in every one of five rounds. See `docs/difficulty-calibration.md` for what was tried.

Determine the octave-band and A-weighted sound power levels of three compressor packages as they now stand in a plant hall, to the plant's standard, from a contractor's acceptance survey, the hall's acoustic report, the instrument certificates and the maintenance log, with a sound level meter booked for 3 readings.

- **Deliverable:** `/app/output/sound_power.csv`, a row for each of C1, C2 and C3 with eight octave-band sound power
  levels and an A-weighted sound power level, in dB.
- **Booking:** `slm <position> <state>` and `rt <position>`, 3 readings in all.
- **Gate:** all 27 values within 1.0 dB of the sealed definition.

## Difficulty

A noise control or rotating equipment engineer does this whenever a packaged machine has to be shown against a sound power guarantee and the only measurements in hand are a survey somebody else took: the pressure levels are reduced to sound power on the measurement surface, the room is corrected for, the instrument is corrected for, invalid positions are dropped, and the result is referred to the machine as it stands now rather than as it stood on the day. ISO 3744 and the plant standards built on it set this out. Its research analogue is the acoustics of sound power determination in a semi-reverberant space: the division of the field into a direct part that falls with the measurement surface and a reverberant part set by the room's equivalent absorption area, Sabine's relation between that area and reverberation time, the energy averaging of levels over a surface, background subtraction and its validity margin, radiation into a restricted solid angle near a wall, and the scaling of aerodynamic machine noise with the fifth power of speed. The hall, the machines, the survey and the instruments are synthetic, written by authoring/provenance from a sealed definition. They are realistic, and so is the level of challenge they present:
- **The hall:** 24 m by 14 m by 6 m, painted concrete, louvred to an adjacent bay, with a reverberation time now of 2.50 s at 63 Hz falling to 1.10 s at 8 kHz.
- **The machines:** a 1250 kW centrifugal air compressor package and a 900 kW screw compressor package standing clear, and a 600 kW blower package 0.6 m from the east wall; arrays of 8, 8 and 7 positions at 3.0, 3.0 and 2.0 m; sound power levels of 84 to 103 dB in band.
- **The booking:** a class 1 sound level meter and its decay analyser, 3 readings in all, of either a band spectrum at a position with a chosen state of the machines or a reverberation time at a position.

The core difficulty is that none of what decides the answer is written down as a conclusion. The documents give the standard's method and its rules, the register, the position table, the survey's indicated levels with the levels measured with everything off, the hall's acoustic report, the two instrument certificates and the maintenance log. What decides the result has to be found in them and in 3 readings:

- **Four things look as though they need a reading, and there are three.** The hall's reverberation time is no longer the acoustic report's, because the roof repair took down the absorptive ceiling panels and they were not refitted, so the environmental correction has to come from a measurement made now. Two of the three machines were changed after the survey: C1's enclosure access panel, which had stood open through the survey, was closed, and C3's intake silencer was fitted. Each of those needs the standard's configuration difference, which is a reading. C2 looks as though it needs one too, because its survey pass ran at 2508 rpm against its rated 2950 rpm; the standard's speed rule settles it with no reading, and that is the way out. A plan that spends a reading on C2, or on a second reverberation station, leaves one of the two differences unmeasured.
- **The reverberation time is a spectrum.** The ceiling panels did most of their work above 250 Hz, so the report's values are nearly right at 63 Hz and far out in the middle of the range; and the hall's own reverberation time falls by more than a factor of two from 500 Hz to 8 kHz, so one value used for every band is wrong at both ends.
- **A configuration difference is a spectrum too.** An open enclosure panel and a missing intake silencer each change the mid bands by much more than the ends. Carried across as one A-weighted figure, the ends of the spectrum are wrong.
- **The positions.** The drive-end position of C1's array was set at 0.65 m to clear a pipe rack, so it is not on the measurement surface; the two positions of C2's array nearest the louvred wall sit where the adjacent bay's ventilation blower, commissioned before the survey and running continuously, exceeds the level with C2 running in two bands. Nothing says so: the position table gives the radius and the bearing, and the levels measured with everything off give the blower away only when the positions are compared with each other.
- **The surface.** C3's 0.6 m wall clearance puts it inside the standard's figure for a half space, so it radiates into a quarter space; and its array was set at 2.0 m, where the register gives a nominal 3.0 m for all three packages.
- **The instrument.** The survey meter carried a windscreen, and its certificate's correction is what makes the top band right. It cancels for the two machines whose levels are referred by a measured difference, and not for the third.

Each of these defeats an assumption the general approach makes on first reading:
- that a room's acoustic report describes the room as it is;
- that a survey measured the machine the answer is about;
- that every position a surveyor recorded is a position the standard allows;
- that a register's nominal geometry is the geometry of the measurement;
- that a correction worth a decibel or two can be left for later.

The gate is all 27 values: eight bands and an A-weighted level for each of three machines, each within the tolerance.

## Reference solution

solution/solve.py is the reference; solution/solve.sh runs it in the agent's environment. It uses only the documents in /app/data and the `slm` and `rt` commands.

1. **The hall as it is.** The maintenance log records that the roof repair of 2026-06-18 took down the absorptive ceiling panels and that they have not been refitted, so the acoustic report's reverberation time no longer describes the hall. The reference measures it instead, at one station, which the standard allows because the field away from the machines is diffuse, and gets the equivalent absorption area of each band from Sabine's relation with the volume in the report. That is one reading.
2. **The machines as they are.** The survey of 14 and 15 September 2026 recorded each machine as it then stood.
   - C2's speed column gives 2508 rpm against the register's rated 2950 rpm, so its levels are referred to the rated speed by the standard's 50 lg rule, which is +3.52 dB in every band. No reading is needed.
   - C1 and C3 were surveyed at their rated speed and the log records a change to each after the survey date, so each needs the standard's configuration difference: the per-band difference between a level measured now and the survey's level at one position of the machine's own array, the hall being unchanged between the two. That is one reading each, and with the reverberation measurement it is the whole booking.
3. **The levels.** Every indicated level of the survey, with the machine running and with everything off, is corrected by the certificate of M-2, which carried a windscreen; the booked meter M-7 needs no correction. At each position the level with everything off is subtracted in energy from the level with the machine running, band by band.
4. **The positions.** A position is valid when it lies on the machine's measurement surface, which the reference takes as the radius most of the array's positions share, and when the level with the machine running exceeds the level with everything off by at least the standard's margin in every band. P4 of C1's array, at 0.65 m, and P15 and P16 of C2's array, by the louvred wall, fail those rules, which leaves 7, 6 and 7 valid positions.
5. **The surface.** C3's wall clearance is inside the standard's figure, so its surface is pi r^2 at its own 2.0 m, which is 12.57 m2; C1's and C2's are 2 pi r^2 at 3.0 m, which is 56.55 m2.
6. **The result.** In each band the energy average of the levels over the valid positions, plus 10 lg S, less the environmental correction; then the speed referral or the configuration difference; and the A-weighted level as the energy sum of the weighted bands.

**On the shipped scenario** (authoring/evidence/reference_run.txt and budget.txt), the reference spends its booking on a reverberation time at P1 and on C1 at P1 and C3 at P17, and all 27 values are inside the band, the worst of them 0.44 dB from the definition against a tolerance of 1.0 dB.

**authoring/evidence/independent.py** is a second solution, written separately, with its own code: it works in mean-square ratios rather than decibels, reads the tables with pandas, takes the reverberation time at P12, measures each difference at the last valid position of the array instead of the first, and takes the array radius as the median of the position table. It also gets all 27 values right, on the shipped seed and on all 20 laboratory seeds 7101 to 7120, its worst value 0.30 dB from the definition.

## Verification

The deliverable is one CSV file, /app/output/sound_power.csv, with a row for each of the three machines: eight octave-band sound power levels from 63 Hz to 8 kHz and an A-weighted sound power level, in dB. The verifier (tests/grade_power.py, run by tests/test_power.py under pytest) grades each of the 27 values against the sealed definition in tests/sealed: a value is right when it is within 1.0 dB of the definition's level for that machine and band, as the machine now stands. The sheet is accepted only when all 27 are right. One pytest test carries the reward. test.sh writes 0 first, and writes 1 only when pytest exits 0 and the ctrf report shows exactly 1 test, 1 passed.

The truth comes from the sealed definition authoring/provenance/isim.py, never from running the reference, and the agent never sees it. authoring/provenance/tune.py recomputes the two tuned values of that definition from the design rules it states and checks every other value against them.

**Why the tolerance is 1.0 dB.** The design rule is that every choice a solver can get wrong must move at least one value by at least twice the tolerance. That is what makes the band unhedgeable: for a value graded inside a band, one number is right under both answers to a choice exactly when the two answers lie within two tolerances of each other, so a 2 dB bar on every route closes it (authoring/evidence/hedge_study.txt). The spread of correct methods is far inside the band: the reference's own worst value is 0.44 dB from the definition and the worst of ten sound variations is 0.57 dB (method_spread.txt), against a nearest defective route of 2.23 dB (route_study.txt), so the gap between the worst sound method and the nearest unsound one is about four times the sound spread.

**The seed.** The seed (7101) drives only the scatter of the three booked readings; the contractor's survey carries its own fixed scatter, so the records do not move with the seed. authoring/provenance/seed_screen.py chose it as the first seed from 7101 on which every sound method of method_spread.py gets all 27 values right and none of them is further than 70 per cent of the tolerance from the definition, the separate solution gets all 27 right, and every defective route of route_study.py fails. On the shipped seed the largest offset of a reading any of those plans drew is 2.66 sigma of the stated repeatability (seed_screen.txt).

**Correct methods** (method_spread.txt, independent.txt). The reference and these variations all get all 27 values right on the shipped seed and on all 20 laboratory seeds 7101 to 7120:
- the reverberation measurement at another station, by any of the three machines;
- the two configuration differences measured in the other order, or at other positions of their arrays;
- the positions by the louvred wall kept and corrected by energy subtraction instead of dropped;
- one more position dropped from each array than the standard requires;
- the mean background of the valid positions subtracted instead of each position's own;
- the background left out where the standard's margin is met.
Their worst value is 0.57 dB from the definition. The separately written solution's worst is 0.30 dB.

**Defective routes** (route_study.txt; the last column counts the laboratory seeds 7101 to 7120 on which the route gets everything right):
| Route | Right of 27 | Worst value | Seeds right |
|---|---|---|---|
| the environmental correction left out | 1 | C1 500 Hz +5.00 | 0 of 20 |
| the acoustic report's reverberation time used | 15 | C2 1 kHz +2.81 | 0 of 20 |
| one reverberation time for every band | 22 | C2 8 kHz -2.41 | 0 of 20 |
| C2 not referred to its rated speed | 18 | C2 8 kHz -3.64 | 0 of 20 |
| C2 referred with 20 lg instead of 50 lg | 18 | C2 8 kHz -2.23 | 0 of 20 |
| C2 referred the wrong way | 18 | C2 8 kHz -7.17 | 0 of 20 |
| neither configuration difference applied | 9 | C3 500 Hz +7.98 | 0 of 20 |
| the differences applied as one A-weighted figure | 17 | C3 8 kHz -3.95 | 0 of 20 |
| the differences applied with the wrong sign | 9 | C3 500 Hz +16.04 | 0 of 20 |
| a reading spent on C2 at its rated speed | 18 | C3 500 Hz +7.97 | 0 of 20 |
| a reading spent on a second reverberation station | 18 | C3 500 Hz +7.97 | 0 of 20 |
| every position kept, no background subtracted | 16 | C1 8 kHz +3.97 | 0 of 20 |
| every position kept, the first position's background for all | 16 | C1 8 kHz +3.97 | 0 of 20 |
| every position kept, each position's own background subtracted | 18 | C1 8 kHz +3.97 | 0 of 20 |
| the background rule applied but not the radius rule | 18 | C1 8 kHz +3.97 | 0 of 20 |
| C3 taken to radiate into a half space | 18 | C3 8 kHz +2.26 | 0 of 20 |
| the array radii taken from the register's nominal value | 18 | C3 8 kHz +2.63 | 0 of 20 |
| the survey meter's certificate correction left out | 26 | C2 8 kHz -2.52 | 0 of 20 |
| no readings at all | 3 | C3 500 Hz +8.96 | 0 of 20 |

Nineteen of the twenty routes fail, and each of them fails a value by at least the 2 dB bar. The twentieth is listed because it passes: averaging the levels arithmetically instead of in energy leaves every value inside the band, because the spread of levels over an array is a few tenths of a decibel. Nothing turns on that choice and the record says so rather than leaving it out. Every one of the 27 values is failed by at least three of the routes, and the two that fewest routes reach, C2 at 63 Hz and at 125 Hz, are failed by four.

**Hedging** (hedge_study.txt). No choice that decides the result can be hedged across a sheet: each of them moves at least one value by more than two tolerances, and there no single number is inside the band under both answers. The only choice a whole sheet can hedge is the arithmetic average, whose wrong answer is inside the band anyway.

**Null answers** (null_baselines.txt). Each value is graded on its own, so an answer made without the booking can be right on individual values; the file lists every such free pass. The survey read off as it stands gets 2 of 27; with the background subtracted and the invalid positions dropped, 1; the guaranteed A-weighted level as the answer for LwA, 1; the survey's own A-weighted pressure column, 1; a flat 100 dB everywhere, 4; and the survey read off with the best single offset, chosen with the truth, 6. The gate is all 27, so none of them is accepted.

**Malformed sheets** are rejected as a whole (verifier_checks.txt), and every case is built from the current reference sheet when the script runs, so the file cannot go stale. This covers a sheet that is a symlink, empty or absent; has a missing, misspelt or extended header; has a missing, repeated, unknown or lower-case machine; has a row of the wrong length or non-ASCII text; or has a level that is NaN, infinite, empty, text, negative or outside 40 to 160 dB. 30 cases were run and none crashed the grader. The reference sheet is accepted with CRLF line ends, blank lines, spaces around the fields, rows in any order and levels to four decimals; a value exactly at the edge of the band is accepted and one 0.05 dB past it is graded wrong.

In the agent's container the sealed definition and the instrument's records live under /opt/lab, in directories owned by the user lab with mode 700. The agent reaches the instrument only through `slm` and `rt`, sudo wrappers for /opt/lab/lab.py. The program validates its arguments, creates one exclusive record file per reading, refuses any reading beyond the booking of 3, and refuses to run at all if its directories are not as installed. The agent works as a separate user that can write only to /app/output; /app/data is read-only. The verifier runs in a separate container without network, and /logs/verifier is root-only.

## Layout (for maintainers)

```
instruction.md            the agent's brief
task.toml                 the manifest; its three explanation fields are the three sections above
environment/
  Dockerfile              the agent's image: the users agent and lab, /app/data, /opt/lab, the two wrappers
  data/                   the documents installed read-only at /app/data (written by authoring/provenance/gen.py)
  rig/lab.py              the booked instrument, run as the lab user through sudo
  rig/sealed/             isim.py + seed.json, mode 700, unreadable to the agent
solution/
  solve.py solve.sh       the reference
tests/
  Dockerfile test.sh      the verifier image and the reward
  test_power.py           the one pytest test that carries the reward
  grade_power.py          the grader
  sealed/                 the same isim.py + seed.json for the verifier
  app_data/               a copy of environment/data, installed at /app/data in the verifier image
authoring/
  provenance/isim.py      the sealed definition: the hall, the machines, the arrays and the instrument
  provenance/gen.py       writes environment/data and the sealed files from isim.py
  provenance/build.py     populates environment/data, the two sealed copies and tests/app_data
  provenance/tune.py      the design rules behind the tuned values, and a check that they still hold
  provenance/seed_screen.py  how the laboratory seed was chosen
  evidence/common.py      the in-process instrument, the reference model with switches, grading
  evidence/budget.py      where each of the 27 values comes from
  evidence/route_study.py defective routes, and which values each fails
  evidence/method_spread.py  sound variations
  evidence/independent.py a second solution, written separately
  evidence/null_baselines.py  answers made without the booking
  evidence/hedge_study.py whether one number can be right under both answers to a choice
  evidence/verifier_checks.py  malformed and edge-case sheets, built from the current reference
  evidence/reference_run.py  the reference through the real instrument program
  evidence/preflight.py   every rule above, checked mechanically
```

## Regenerating

From the bundle root:

```
python3 authoring/provenance/build.py          # environment/data, both sealed copies, tests/app_data
python3 authoring/provenance/tune.py           # the design rules still hold
python3 authoring/provenance/seed_screen.py    # the seed is still the first that qualifies
cd authoring/evidence
for s in budget route_study method_spread independent null_baselines hedge_study verifier_checks reference_run; do
    python3 $s.py > $s.txt
done
python3 ../provenance/seed_screen.py > seed_screen.txt
python3 preflight.py
```

## Changing the task

Change `authoring/provenance/isim.py` and nothing downstream by hand: the documents, both sealed copies and the
verifier's data all come from it through `build.py`. Then rerun `tune.py`, every evidence script and `preflight.py`,
in that order. `tune.py` fails if a tuned value no longer follows from its design rule, and `preflight.py` fails if an
evidence file reports an unexpected case, if the three copies of the sealed definition differ, if the documents stop
regenerating byte for byte, or if a number quoted in an explanation is in no evidence file.
