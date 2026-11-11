# relief-valve-adequacy

Reassess the pressure relief of a gas plant's nine relief valves to the plant's standard after the unit's capacity was increased: for each valve the contingency that governs, the effective orifice area it requires and whether the valve as it now stands is adequate, from the relief valve register, the shop records of every overhaul, the operating record, the control valve trends, the instrument and safety instrumented system registers, the vessel data book and the superseded relief study.

## Difficulty

A process safety or mechanical engineer does this whenever a unit is modified: every relief valve on it has to be shown adequate for the contingency that governs it, on the plant as it now stands rather than as it was designed. API 520 and 521 and the plant standards built on them, here RP-7, set out the method. Its research analogue is the mechanics and thermodynamics of emergency relief: critical and subcritical compressible flow through a nozzle, the certified-capacity treatment of liquid relief with its viscosity correction, the heat a pool fire puts into a wetted vessel and the vapour that heat generates, the capacity of a control valve at full travel from its installed characteristic, the heat transfer of a reboiler at a duty other than its design duty, orifice metering when the density has moved away from the value the flow computer holds, and non-recoverable pressure loss in an inlet line. The unit, its records and its documents are synthetic, written by authoring/provenance from a sealed definition. They are realistic, and so is the level of challenge they present:

- **The unit:** a natural gas liquids recovery train of nine protected items, an inlet separator, a fuel gas knock-out drum, two reflux or product drums, a product drum, two fractionating columns, a feed/bottoms exchanger shell and a pump discharge, with set pressures from 9.5 to 62 barg and orifices from D to K.
- **The contingencies:** fire, blocked outlet, control valve failure, loss of overhead cooling, tube rupture and thermal expansion. The register lists those each item's service admits; which of them governs has to be worked out, and all six govern somewhere on the unit.
- **The deliverable:** for each valve the name of the governing contingency, the effective orifice area it requires, and whether the valve is adequate. Nothing in the records states any of the three.

The core difficulty is that the plant is not the plant its documents describe, and that two of the quantities the answer turns on are not written down anywhere:

- **The control valves do not have the coefficients on their data sheets.** Two of five have been re-trimmed and no document says so. RP-7 requires the coefficient at full travel to be verified against the valve's own operating record, which means fitting it from the logged travel, pressures and flow through the equal-percentage characteristic. One valve's record is read by the unit's feed meter, so its flow has to be corrected before it can be fitted. On the two valves whose coefficients do match their sheets, the fit confirms the sheet.
- **The feed meter holds a density the gas no longer has.** It is an orifice meter whose flow computer was given a fixed relative density at commissioning; the feed has got richer since, as the dated analyses show. The indication is low by about 4 per cent, which the unit's own mass balance confirms, and it carries into every contingency that depends on the feed.
- **The reboilers are not at their design duty.** The data sheet duties are at the original feed rate and the unit now runs above it, so the coefficient-area has to come from the operating record. The vapour a column makes on total loss of cooling then follows from the steam supply temperature and the bottoms temperature at the relieving pressure, not from the design duty.
- **Three contingencies cannot happen and one credit may be taken.** A pump's blocked discharge is out of reach because its shutoff head has decayed, which only its latest performance test shows; a control valve failure is out of reach because the device protecting its source is set below the item's relieving pressure; a tube rupture must still be considered because the two-thirds rule does not reach it. Of four instrumented functions that would prevent a contingency, one qualifies: of the other three, one is below SIL 2, one is proof tested too rarely, and one initiates on the very measurement whose control failure causes the contingency it is claimed against.
- **The records that have moved on.** A column was re-set 0.90 m higher than the vessel data book shows, which changes how much of it falls below the 7.6 m the fire case counts. Two items were re-insulated to a fire-resistant specification and now earn an environment factor; a third carries lagging without a certificate and does not. One valve carries a smaller nozzle than its register row, fitted from stores after the original was found damaged. One valve was reset in the field to a lower set pressure. One valve was uprated to a larger orifice and its inlet pipework was left alone, which is what now puts its inlet loss over the 3 per cent limit.
- **The superseded study.** The relief study on file is correct for the plant as built and states its basis. It is wrong now on the governing contingency or the finding of most of the unit, and one of its own actions was never closed.

Each of these defeats an assumption the general approach makes on first reading:
- that a data sheet describes the equipment installed;
- that a meter's indication is the flow;
- that a design duty is the duty;
- that every contingency listed is a contingency that can happen, and that a protective function listed may be credited;
- that a data book issued with the plant still describes it.

The gate is all 9 valves, in all three columns.

## Reference solution

solution/solve.py is the reference; solution/solve.sh runs it in the agent's environment. It uses only the records in /app/data.

1. **The valve as it stands.** The set pressure and the orifice are those the shop record of the last overhaul leaves; the register was issued with the plant. PSV-407 carries an H nozzle against the register's J, and PSV-409 is set at 9.5 barg against the register's 11.0.
2. **The feed.** FE-4011's flow computer holds a fixed relative density, so the true flow is the indication times the square root of the ratio of the current relative density to the one it holds. The current molar mass comes from the most recent analysis. Every other meter is a coriolis meter and is read as it stands.
3. **The control valves.** For each logged point of a valve's trend the standard's compressible expression gives the coefficient at that travel; the equal-percentage characteristic and the data sheet rangeability refer it to full travel, and the record's mean is used. PV-4001's flow column is FE-4011's, so it takes the feed correction first.
4. **The reboilers.** For each day of the operating record the steam flow and the latent heat at the steam pressure give the duty, and the duty over the difference between the steam saturation temperature and the bottoms temperature gives the coefficient-area; the mean is used. The relieving duty uses the supply header pressure with the steam valve wide open and the bottoms temperature at the relieving pressure.
5. **The pump.** The latest performance test gives the shutoff head on the curve shape the data sheet fixes. Where the shutoff pressure cannot reach the relieving pressure the blocked discharge is set aside.
6. **The contingencies.** Each listed contingency is sized by its section of RP-7, with the relieving pressure at 21 per cent accumulation for fire and 10 per cent otherwise, the properties at relieving conditions, the viscosity correction iterated on the liquid cases, and the rupture disc factor where one is fitted. An instrumented function sets a contingency aside only when it is SIL 2 or better, proof tested at not more than 18 months, and initiated on a measurement other than the one the failing control uses.
7. **The finding.** The largest area is the requirement and its contingency is the governing one. The valve is adequate when the orifice it carries covers that area, its type is permitted at its back pressure, and the inlet loss at the installed orifice's capacity under that contingency is within 3 per cent of the set pressure.

**On the shipped records** (authoring/evidence/reference_run.txt) the reference identifies PV-4001 at 54.9 against a data sheet 64.0, PV-4071 at 37.7 against 27.0, PV-4021 at 3.08 against 2.50, and PV-4031 and PV-4061 within a per cent of their sheets; E-403 at 26.7 kW/K and E-406 at 42.8 kW/K, 18 per cent above their data sheet basis; the feed 3.9 per cent above FE-4011's indication; and P-401's shutoff head 7.6 per cent below its data sheet. All 9 valves are right, the worst relative area being 0.0021.

**authoring/evidence/independent.py** is a second assessment, written separately, sharing no code with the reference. It reads the records with pandas, builds one table of every valve and contingency and reduces it, and takes its own choices where the standard leaves room: the control valve coefficient by a least squares fit through the origin, the reboiler coefficient-area by a least squares fit of duty against temperature difference, and the pump curve by a least squares quadratic. It gets all 9 right on the shipped records and on all 20 laboratory seeds, its worst relative area being 0.0050.

## Verification

The deliverable is one CSV file, /app/output/relief.csv, with the governing contingency, the required effective orifice area and the finding for each of the 9 valves. The verifier (tests/grade_relief.py, run by tests/test_relief.py under pytest) grades it against the sealed definition in tests/sealed:

- the contingency name must be exactly the one that requires the largest area;
- the area must be within 1 per cent of it, relative;
- the finding must be exactly adequate or inadequate.

The sheet is accepted only when all 9 valves are right in all three columns. One pytest test carries the reward. test.sh writes 0 first, and writes 1 only when pytest exits 0 and the ctrf report shows exactly 1 test, 1 passed.

The truth comes from the sealed definition authoring/provenance/isim.py, never from running the reference, and the agent never sees it: the task is records only, so no copy of it is anywhere in the agent's environment. authoring/provenance/tune.py recomputes the design rules from it and checks them: that all six contingency names govern somewhere, that the governing contingency beats the next contender by at least 5 per cent (worst 8.9 per cent, at PSV-408), that every finding is decided by at least 10 per cent on some condition (worst 37.1 per cent, at PSV-402), that each control valve coefficient either differs from its data sheet by at least 10 per cent or matches within 1 per cent, that at least one matches, that the reboiler coefficient-area differs from its data sheet basis by at least 10 per cent (worst 18.1 per cent), that between 3 and 6 valves are inadequate (5 of 9), and that the feed meter's indication is 2 to 8 per cent from the truth (3.8 per cent).

The seed (7301) drives only the scatter of the records; every answer comes from the parameters in the sealed definition. authoring/provenance/seed_screen.py screens seeds on three conditions (authoring/evidence/seed_screen.txt): every sound variation gets all 9 valves right, every defective route fails, and the worst relative area of any sound variation is within half the band.

Why the gate is all 9, measured on the shipped records. Every number below is copied from the named file in authoring/evidence.

Correct methods (method_spread.txt, independent.txt). The reference and 8 sound variations all get 9 of 9 on the shipped records and on all 20 laboratory seeds:
- the trend fitted by least squares through the origin, or from the points above 60 per cent travel only;
- the reboiler coefficient-area from the record's mean duty over its mean temperature difference;
- the pump curve by least squares on all four points of the latest test;
- the viscosity iteration stopped after two passes;
- and three combinations of these.

Their worst relative area is 0.0024 on the shipped records and 0.0051 over all 20 seeds, against a band of 0.0100. The worst is always PSV-401, whose answer rides on the identified control valve coefficient.

Defective routes (route_study.txt; the last column counts the laboratory seeds 7301 to 7320 on which the route gets all 9):
| Route | Right of 9 | Worst valve | Seeds with 9 |
|---|---|---|---|
| the data sheet coefficient for every control valve | 6 | PSV-401 area +16.4% | 0 of 20 |
| a linear characteristic for every control valve | 6 | PSV-401 case blocked_outlet | 0 of 20 |
| the largest logged flow taken as the relieving rate | 6 | PSV-401 case blocked_outlet | 0 of 20 |
| the feed meter read as indicated | 8 | PSV-401 area -4.0% | 0 of 20 |
| the reboiler coefficient-area from the data sheet duty | 8 | PSV-403 area -15.3%, finding adequate | 0 of 20 |
| the data sheet duty taken as the relieving duty | 7 | PSV-403 area -15.3%, finding adequate | 0 of 20 |
| no credit for instrumented protection | 8 | PSV-406 case cooling_failure, finding inadequate | 0 of 20 |
| credit taken without testing independence | 7 | PSV-403 case blocked_outlet, finding adequate | 0 of 20 |
| credit taken without the proof test interval | 8 | PSV-409 case fire | 0 of 20 |
| the two-thirds rule applied to the wrong ratio | 8 | PSV-402 case fire, finding adequate | 0 of 20 |
| one tube area discharging instead of two | 8 | PSV-402 case fire, finding adequate | 0 of 20 |
| the register's orifice letter | 8 | PSV-407 finding adequate | 0 of 20 |
| the register's set pressure | 8 | PSV-409 area -12.7% | 0 of 20 |
| the rupture disc combination factor left out | 8 | PSV-402 area -10.0% | 0 of 20 |
| elevation changes since the data book left out | 8 | PSV-406 area +11.1% | 0 of 20 |
| no insulation credit anywhere | 8 | PSV-404 case fire | 0 of 20 |
| the viscosity correction left at 1 | 8 | PSV-405 area -5.9% | 0 of 20 |
| the pump's data sheet curve | 8 | PSV-405 case blocked_outlet | 0 of 20 |
| properties at the item's normal pressure | 6 | PSV-401 area +1.2% | 0 of 20 |
| the inlet line rule not checked | 8 | PSV-404 finding adequate | 0 of 20 |
| 10 per cent accumulation for the fire case | 8 | PSV-406 area +6.2% | 0 of 20 |
| no drainage or firefighting credit | 5 | PSV-406 area +64.1%, finding inadequate | 0 of 20 |
| the whole shell taken as wetted | 6 | PSV-407 case fire | 0 of 20 |
| the vapour discharge coefficient used for liquid | 7 | PSV-402 area -33.3% | 0 of 20 |
| the 2019 study's findings taken as the answer | 1 | PSV-401 area +16.4% | 0 of 20 |

Every valve is failed by at least 3 of the 25 routes, and no route is rescued by scatter on any seed.

Hedging (hedge_study.txt). A hedge would need a defective reading to give the same contingency name and the same finding as the sealed answer, with two area bands that overlap. The only valve on which any hedge exists at all is PSV-401, between the correct properties and properties taken at the normal pressure; that route fails PSV-403 and PSV-406 anyway, and the gate is all 9.

Null answers (null_baselines.txt). Each valve is graded on its own, so a sheet made without the assessment can be right on individual valves; the file lists every such free pass:
| Null answer | Right of 9 |
|---|---|
| fire taken as governing everywhere | 1 |
| blocked outlet taken as governing everywhere | 1 |
| the orifice fitted quoted as the requirement, every valve adequate | 0 |
| the register and data sheets taken as the whole truth | 2 |
| the 2019 study copied out | 1 |

Malformed sheets are rejected as a whole (verifier_checks.txt), every case built from the current reference at run time. This covers a sheet that is absent, a symbolic link, a directory, empty, header only, headerless, misspelt in its header or extended by a column; that has a row of the wrong length, a valve missing, repeated, unknown or in lower case, or non-ASCII text; that carries an unknown or empty contingency name or finding, or one in the wrong case; or an area that is not a number, empty, NaN, infinite, negative, zero, or outside 0.001 to 100000 mm2. 41 cases were run and none was unexpected or crashed the grader. The reference sheet is accepted with CRLF line ends, blank lines, padded fields, rows in any order, an area in exponent form, with any number of decimals, or with a leading plus.

The agent works as a separate user that can write only to /app/output. /app/data is read-only and root-owned. The verifier runs in a separate container without network, and /logs/verifier is root-only.
