# recip-cylinder-limits

> **Status: not shipped.** Built, tune-clean and probed, but it does not meet the easiness gate: three low-effort
> probes solved it 12 of 12 after the coupled-duty rebuild, as six did before it. See
> `docs/design-note-recip-cylinder-limits.md` for the calibration record. The sealed definition, the records, the
> reference solution and `tune.py` are current and consistent; the evidence set, `preflight.py`, `task.toml` and the
> sections below still describe the earlier fixed-stage-pressure design and have not been brought forward.

Determine the lowest suction pressure at which each of the six cylinders of a three-stage reciprocating gas booster may be run, and the requirement of the plant's standard that governs it, from the machine data sheet, the overhaul register, a service bulletin, the operating and instrument records, the drive record, a feed gas analysis and the maintenance log, with the laboratory and the weigh shop available for 2 readings.

- **Deliverable:** `/app/output/cylinder_limits.csv`, a row for each of 1A, 1B, 2A, 2B, 3A and 3B with the lowest
  suction pressure at which the cylinder may be run, in bar absolute, and the requirement of RC-4 that governs it.
- **Allowance:** `gc <stage>` and `weigh <cylinder>`, 2 readings in all.
- **Gate:** all twelve values right - each pressure within 0.5 per cent of the sealed definition and each
  requirement named exactly.

## Difficulty

A rotating equipment or reciprocating machinery engineer does this whenever a booster on a declining field has to be run further down than it was selected for: the load diagram of each throw is rebuilt for the machine as it now stands, each limit the plant's standard sets is checked across the range of suction pressures the field will reach, and the lowest pressure the cylinder can hold is reported with the limit that stops it. API 618 and the plant standards built on it set this out, and the calculation is the one every reciprocating compressor sizing program performs. Its engineering analogue is the mechanics of a slider-crank under gas load: the gas force on a double-acting piston as the two ends alternate between suction and discharge pressure, the inertia force of the reciprocating weight with its primary and secondary terms, the requirement that the combined load reverse for long enough each revolution to let the crosshead pin take oil, the adiabatic rise of discharge temperature with pressure ratio, the fall of volumetric efficiency as each end's clearance re-expands, and the peak of indicated power at an intermediate ratio. The machine, the records and the standard are synthetic, written by authoring/provenance from a sealed definition. They are realistic, and so is the level of challenge they present:

- **The machine:** a six-throw balanced opposed frame, 305 mm stroke, three stages at 48, 110 and 170 bar a discharge, six double-acting cylinders from 205 mm bore on the first stage to 100 and 110 mm on the third, each with its own rated power, allowable gas load and head and crank end clearances.
- **The records:** the machine data sheet, the overhaul register, an OEM service bulletin, the cylinder schedule, the liner records, the operating record, the instrument schedule, a nine-month temperature trend, the drive record, a feed gas analysis, a component property table against temperature and a thirty-eight line maintenance log.
- **The allowance:** a gas chromatograph and the weigh shop, 2 readings in all, of either a stage's gas analysis or the reciprocating weight of a throw.

The core difficulty is that none of what decides the answer is written down as a conclusion. The standard gives the method and the names; the data sheet gives the machine as it was bought; the register, the bulletin, the trend, the drive record and the log record what was done, in the flat voice of a register, without drawing an inference from any of it. What the machine now is has to be assembled out of them, and then four facts want a reading and the allowance pays for two:

- **Four things look as though they need a reading, and there are two.** The second stage's gas is nowhere on file; the third stage's is not either; and the log calls for the reciprocating weights of three throws, one of which carries a spare assembly whose weight the register records as not taken. Two of the four come out of the records: the third-stage separator has been out of service and bypassed since August, so that stage takes the gas the second stage discharges, and the shop ticket for the re-bored throw gives the weight of the piston fitted and of the piston removed, so that assembly's weight is the data sheet's plus the difference. A third throw the log asks about was never altered at all. A plan that draws both analyses, or both weighings, leaves a fact unsettled that no record will supply.
- **Six requirements, five of which govern a cylinder.** The gas load alone is rated against the cylinder body; the gas and inertia loads together against the frame, or against the lower figure where a throw is de-rated. Which of the six is reached first differs from throw to throw, and the two throws of the first stage differ only in the diameter of their piston rods.
- **The exponent and the discharge temperature have to be found together.** The property table gives each component's molar heat capacity against temperature, and the standard takes the mixture's at the mean of the suction and discharge temperatures, so the two are the solution of a fixed point. Taken at the suction temperature instead, which is the obvious reading, the temperature-limited cylinder moves by nineteen times the tolerance; and because the mean differs from cylinder to cylinder, there is no one exponent per stage to carry across.
- **The inertia load is what makes the problem a load diagram at all.** Dropped, every rod load is wrong, the reversal requirement fails everywhere, and no cylinder has an acceptable pressure at all. Kept to its primary term only, two cylinders come out on the wrong requirement.
- **Each end of a cylinder has its own clearance.** The data sheet gives the head end's and the crank end's separately, as fractions of their own swept volumes, and the volumetric efficiency and the power follow end by end. One clearance used for the whole cylinder moves a third-stage cylinder by ninety-seven times the tolerance.
- **The machine is not the data sheet's.** One liner is at the first repair size, so the as-bored diameter from the latest entry of the liner record, not the nameplate bore or the entry above it, sets the areas. One throw carries the heavier new piston that went in with that liner. Another carries a spare assembly and is de-rated below the frame's rating. Two clearance pockets stand open and are given as volumes, so the fraction they add has to be worked out against the head end's swept volume. The frame's rated rod load has been revised below the nameplate's by a bulletin the register enters. The drive holds a speed well below the rated one, which moves every inertia load by the square of the ratio.
- **The temperature that decides one cylinder is two corrections away from the reading.** The after-cooler ahead of the second stage is fouled, so its suction temperature is the trend's and not the design value, and its element sits on the suction bottle rather than at the valve flange, which the standard corrects by a fixed amount.
- **The gas is not one gas.** The analysis of record is of the feed, and each separator takes condensate out, so the mixture differs stage by stage.
- **The range is not scanned from the bottom.** The power of a cylinder peaks at an intermediate ratio, so one third-stage cylinder is acceptable, unacceptable and acceptable again as the pressure falls. The standard asks for the lowest pressure acceptable at that pressure and at every higher one. A solver who scans upward for the first acceptable pressure reports that lower run instead, 43 bar low and on the wrong requirement.

Each of these defeats an assumption the general approach makes on first reading:

- that a data sheet describes the machine in front of you;
- that one limit, once found, is the limit for every cylinder of the frame;
- that a rating stamped on a nameplate is the rating in force;
- that a gas property can be taken at the condition you start from;
- that a cylinder has one clearance;
- that the lowest acceptable pressure is the first one you meet coming up from the bottom;
- that a measurement can be bought whenever a record is silent.

The gate is all twelve values: a pressure and a governing requirement for each of six cylinders, the pressure within the tolerance and the requirement named exactly.

## Reference solution

solution/solve.py is the reference; solution/solve.sh runs it in the agent's environment. It uses only the records in /app/data and the `gc` and `weigh` commands.

1. **The plan for the allowance.** Four facts want a reading: the gas of the second stage, the gas of the third, and the reciprocating weights of throws 4 and 6, which the maintenance log calls for along with throw 2. Two come out of the records instead. The log records that the third-stage separator has been out of service and bypassed at its inlet spool since 2026-08-19, so the third stage takes the gas the second stage discharges and one analysis serves both. The register's shop ticket 6611 gives the piston fitted to throw 4 at 61.4 kg against the 43.4 kg of the piston removed, and records that nothing else in that assembly changed, so its weight is the data sheet's plus 18.0 kg. Throw 2 has no entry in the register at all, so the data sheet's weight stands. The two readings go on the second stage's analysis and the weighing of throw 6, whose spare assembly the register records with no weight taken.
2. **The machine as it now stands.** The bore of each cylinder is the mean bore of the latest entry in the liner record, which for throw 4 is the first repair size and not the nameplate bore of the entry above it. Each throw's own piston rod comes from the schedule, which gives the second throw the larger rod. The clearance of each end is the data sheet's fraction of that end's swept volume, and for the two throws the register shows opened, the head end carries the pocket's volume as well. The frame's rated rod load is the service bulletin's revision, 150 kN, not the nameplate's 165 kN, and the repaired throw carries the lower figure of that and its own de-rating of 128 kN. The speed is the one the drive record shows held, 327 rev/min.
3. **The gas, the exponent and the discharge temperature.** The property table gives each component's molar heat capacity at four temperatures. The standard takes the mixture's at the mean of the suction and the discharge temperature, so for each cylinder the reference starts from the suction temperature, takes the exponent at the mean, recomputes the discharge temperature and repeats until two successive values differ by less than a thousandth of a kelvin. The exponents that result run from 1.2325 to 1.2474 and differ cylinder by cylinder.
4. **The temperatures.** The suction temperature of each stage is its element's reading from the operating record, plus the standard's 6 K where the instrument schedule shows the element on the suction bottle, which is the second stage.
5. **The requirements.** For every pressure in the standard's range, in steps of 0.01 bar, the gas load and the combined rod load are taken at each whole crank angle, the discharge temperature by the iteration above, the volumetric efficiency of each end from its own clearance, the indicated power as the two ends added, and the reversal as the count of angles at which the combined load is negative.
6. **The answer.** The lowest pressure at which every requirement is met at that pressure and at every higher one in the range, and the requirement with the least margin one step below it.

**On the shipped scenario** (authoring/evidence/reference_run.txt), the reference draws the second stage's analysis and the weighing of 3B and gets 1A at 20.75 bar on the rod load in tension, 1B at 21.38 bar on the gas load, 2A at 31.09 bar on the discharge temperature, 2B at 44.56 bar on the rod load in compression, 3A at 88.72 bar on the cylinder power and 3B at 116.73 bar on the rod load in compression. All twelve values are right, the worst of them 0.034 per cent from the definition against a tolerance of 0.5 per cent.

**authoring/evidence/independent.py** is a second solution, written separately, with its own code: pandas for the records, its own reading of the register, its own interpolation in the property table, and a different algorithm - for each requirement it finds the highest pressure in the range at which that requirement fails, and takes the answer as the highest of those plus one step, with the reversal counted on a quarter-degree sweep. It also gets all twelve right, on the shipped seed and on all 20 laboratory seeds 4101 to 4120, its worst value 0.051 per cent from the definition.

## Verification

The deliverable is one CSV file, /app/output/cylinder_limits.csv, with a row for each of the six cylinders: the lowest suction pressure at which it may be run, in bar absolute, and the name of the requirement of RC-4 that governs it. The verifier (tests/grade_limits.py, run by tests/test_limits.py under pytest) grades the twelve values against the sealed definition in tests/sealed: a pressure is right when it is within 0.5 per cent of the definition's, relatively, and a requirement is right when it is the one the definition names. The sheet is accepted only when all twelve are right. One pytest test carries the reward. test.sh writes 0 first, and writes 1 only when pytest exits 0 and the ctrf report shows exactly 1 test, 1 passed.

The truth comes from the sealed definition authoring/provenance/isim.py, never from running the reference, and the agent never sees it. authoring/provenance/tune.py recomputes the five fitted ratings of that definition from the design rules it states, checks that the five intended requirements govern the six cylinders with at least 5 per cent to each runner-up, that pin reversal governs none of them and is met throughout every window with at least twice the standard's least angle, and that every cylinder is capable at the pressure its stage runs at today.

**Why the tolerance is 0.5 per cent.** The design rule is that every choice a solver can get wrong must move at least one value by at least twice the tolerance, or name a different requirement. That is what makes the band unhedgeable: for a value graded inside a relative band, one number is right under both answers to a choice exactly when the two answers lie within two tolerances of each other, so a 1 per cent bar on every route closes it (authoring/evidence/hedge_study.txt). The spread of correct methods is far inside the band: the reference's own worst value is 0.034 per cent from the definition and the worst of twelve sound variations is 0.169 per cent (method_spread.txt), against a nearest defective route of 3.72 per cent (route_study.txt), so the gap between the worst sound method and the nearest unsound one is about twenty times the sound spread.

**The seed.** The seed (4101) drives only the scatter of a weighing; the gas analyses are the laboratory's reports of record and the plant's own records carry their own fixed scatter, so nothing in the records moves with the seed. authoring/provenance/seed_screen.py chose it as the first seed from 4101 on which every sound variation of method_spread.py gets all twelve values right and none of them is further than 70 per cent of the tolerance from the definition, the separate solution gets all twelve right, and every defective route of route_study.py fails. On the shipped seed the weighing the reference draws is 1.33 standard deviations of the stated repeatability from the assembly's weight (seed_screen.txt).

**Correct methods** (method_spread.txt, independent.txt). The reference and these variations all get all twelve values right on the shipped seed and on all 20 laboratory seeds 4101 to 4120:

- the two readings booked in the other order;
- the third stage's sample stream drawn instead of the second's, which is the same stream;
- the crank swept every half degree or every two degrees instead of every degree;
- the pressure scanned in steps of 0.001 bar;
- the margins written as a difference rather than as a ratio;
- the bore taken at the largest or the smallest of the liner record rather than its mean;
- the second stage's temperature taken from the last month of the trend rather than from the operating record;
- the open clearance pockets read from the maintenance log rather than from the register;
- the discharge temperature iterated to a thousandth of the standard's convergence test.

Their worst value is 0.169 per cent from the definition. The separately written solution's worst, over all 20 seeds, is 0.051 per cent.

**Defective routes** (route_study.txt; the last column counts the laboratory seeds on which the route gets everything right):

| Route | Right of 12 | Worst value | Seeds right |
|---|---|---|---|
| the speed taken from the data sheet, not the drive | 6 | 1A +16.19 % | 0 of 20 |
| the rated rod load taken from the nameplate, not the bulletin | 8 | 2B -30.23 % | 0 of 20 |
| the de-rating of the repaired throw not applied | 10 | 3B -5.40 % | 0 of 20 |
| the nameplate bore used where the liner is at the repair size | 11 | 2B -12.25 % | 0 of 20 |
| the first liner entry used instead of the latest | 11 | 2B -12.25 % | 0 of 20 |
| the common piston rod used for every throw | 7 | 3A -41.64 % | 0 of 20 |
| the clearance taken from the data sheet, the open pockets missed | 11 | 3A +7.33 % | 0 of 20 |
| the open pocket taken over the swept volume of both ends | 11 | 3A +3.72 % | 0 of 20 |
| the head end's clearance used for both ends | 10 | 3A -48.62 % | 0 of 20 |
| the design suction temperatures used, the fouling missed | 11 | 2A -8.85 % | 0 of 20 |
| the bottle-mounted element not corrected to the valve flange | 11 | 2A -8.85 % | 0 of 20 |
| the data sheet's gas analysis used | 10 | 2A -7.33 % | 0 of 20 |
| the feed analysis used for every stage | 10 | 2A -4.63 % | 0 of 20 |
| the weights taken from the data sheet, the overhaul missed | 9 | 3B -5.40 % | 0 of 20 |
| the shop ticket's piston as fitted read as the difference | 11 | 2B +12.10 % | 0 of 20 |
| the valve losses left out of the ratio | 10 | 3A -4.11 % | 0 of 20 |
| the inertia load left out of the rod load | 0 | 1A no answer | 0 of 20 |
| the secondary inertia term left out | 4 | 2B +29.74 % | 0 of 20 |
| the gas load checked against the frame's rated rod load | 10 | 1B -6.13 % | 0 of 20 |
| the piston rod area ignored at the crank end | 2 | 3A +26.83 % | 0 of 20 |
| the isentropic exponent taken at the suction temperature, not iterated | 10 | 2A +9.55 % | 0 of 20 |
| the isentropic exponent taken at the discharge temperature | 10 | 2A -10.84 % | 0 of 20 |
| the isentropic exponent taken as 1.30 | 10 | 2A +27.15 % | 0 of 20 |
| the range scanned upward to the first acceptable pressure | 10 | 3A -48.62 % | 0 of 20 |
| the second stage's analysis not drawn, the feed carried forward | 10 | 2A -4.63 % | 0 of 20 |
| the spare assembly not weighed, the data sheet's weight used | 10 | 3B -5.40 % | 0 of 20 |
| the bypassed separator missed, the feed used for the third stage | 9 | 3B -5.58 % | 0 of 20 |
| pin reversal not checked | 12 | 3B -0.03 % | 20 of 20 |

Twenty-seven of the twenty-eight routes fail, and each of them fails a value by at least the 1 per cent bar or names a different requirement. The twenty-eighth is listed because it passes: leaving the reversal requirement unchecked changes no answer, because the reversal is met throughout every window with at least four times the standard's least angle. Nothing turns on that check in the shipped scenario and the record says so rather than leaving it out - though a solver who drops the inertia load finds the reversal failing everywhere and no acceptable pressure at all, which is the route above it. Every one of the twelve values is failed over the bar by at least three of the routes.

**The allowance** (budget.txt). Four facts want a reading and the allowance pays for two. Every plan that spends a reading on a fact the records already settle, or that leaves one they do not, loses at least one value: both analyses and no weighing costs 3B, both weighings and no analysis costs 2A and 3A, the first stage's analysis (which the records hold) and a weighing costs 2A and 3A, and no readings at all costs three values. The allowance does not refill; environment/rig/lab.py refuses the third reading.

**Hedging** (hedge_study.txt). No choice that decides the result can be hedged across a sheet: each of them moves a value by more than two tolerances or names a different requirement, and in neither case is one entry right under both answers. The only choice a whole sheet can hedge is whether the reversal is checked, whose answer is the same either way.

**Null answers** (null_baselines.txt). Each of the twelve values is graded on its own, so an answer made without the work can be right here and there; the file lists every such free pass. The machine as the data sheet describes it with no readings drawn gets 4 of 12; the pressure each stage runs at today, 2; the bottom of the standard's range, 1; half the discharge pressure, 2; a flat 50 bar with the commonest requirement, 2; the right pressures with one requirement named for all six, 8; the right requirements with the data sheet's machine behind the pressures, 7; and the requirement guessed from the least margin at today's pressure, with the right pressures given to it, 10. The gate is all 12, so none of them is accepted.

**Malformed sheets** are rejected as a whole (verifier_checks.txt), and every case is built from the current reference sheet when the script runs, so the file cannot go stale. This covers a sheet that is a symlink, empty or absent; has a missing, misspelt or extended header; has a missing, repeated, unknown or lower-case cylinder; has a row of the wrong length or non-ASCII text; has a pressure that is NaN, infinite, empty, text, negative or outside 1 to 500 bar; or names a requirement that is not one of the standard's six, in upper case or empty. 34 cases were run and none crashed the grader. The reference sheet is accepted with CRLF line ends, blank lines, spaces around the fields, rows in any order, pressures to four decimals and a pressure in exponent notation; a pressure exactly at the edge of the band is accepted and one 0.55 per cent out is graded wrong.

In the agent's container the sealed definition and the services' records live under /opt/lab, in directories owned by the user lab with mode 700. The agent reaches the services only through `gc` and `weigh`, sudo wrappers for /opt/lab/lab.py. The program validates its arguments, creates one exclusive record file per reading, refuses any reading beyond the allowance of 2, and refuses to run at all if its directories are not as installed. The agent works as a separate user that can write only to /app/output; /app/data is read-only. The verifier runs in a separate container without network, and /logs/verifier is root-only.
## Layout (for maintainers)

```
instruction.md            the agent's brief
task.toml                 the manifest; its three explanation fields are the three sections above
environment/
  Dockerfile              the agent's image: the users agent and lab, /app/data, /opt/lab, the two wrappers
  data/                   the records installed read-only at /app/data (written by authoring/provenance/gen.py)
  rig/lab.py              the laboratory and the weigh shop, run as the lab user through sudo
  rig/sealed/             isim.py + seed.json, mode 700, unreadable to the agent
solution/
  solve.py solve.sh       the reference
tests/
  Dockerfile test.sh      the verifier image and the reward
  test_limits.py          the one pytest test that carries the reward
  grade_limits.py         the grader
  sealed/                 the same isim.py + seed.json for the verifier
  app_data/               a copy of environment/data, installed at /app/data in the verifier image
authoring/
  provenance/isim.py      the sealed definition: the frame, the six cylinders, the gas and the standard's limits
  provenance/gen.py       writes environment/data from isim.py
  provenance/build.py     populates environment/data, the two sealed copies and tests/app_data
  provenance/tune.py      the design rules behind the fitted ratings, and a check that they still hold
  provenance/seed_screen.py  how the laboratory seed was chosen
  evidence/common.py      the in-process laboratory, the reference model with switches, grading
  evidence/budget.py      the allowance: which facts need a reading and what each plan costs
  evidence/route_study.py defective routes, and which values each fails
  evidence/method_spread.py  sound variations
  evidence/independent.py a second solution, written separately
  evidence/null_baselines.py  answers made without the readings
  evidence/hedge_study.py whether one entry can be right under both answers to a choice
  evidence/verifier_checks.py  malformed and edge-case sheets, built from the current reference
  evidence/reference_run.py  the reference through the real laboratory program
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

Change `authoring/provenance/isim.py` and nothing downstream by hand: the records, both sealed copies and the
verifier's data all come from it through `build.py`. Then rerun `tune.py`, every evidence script and `preflight.py`,
in that order. `tune.py` fails if a fitted rating no longer follows from its design rule, and `preflight.py` fails if
an evidence file reports an unexpected case, if the three copies of the sealed definition differ, if the records stop
regenerating byte for byte, or if a number quoted in an explanation is in no evidence file.
