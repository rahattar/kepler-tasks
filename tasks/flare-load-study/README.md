# flare-load-study

Work out what each unit-wide contingency now puts on a gas plant's flare header after the unit's capacity was increased: for each contingency the relief devices that discharge, the load they put on the header together and the pressure that load raises at the header's inlet, from the relief valve register, the shop records of every overhaul, the operating record, the control valve trends, the drive schedule, the fire zone and header tie-in schedules, the instrument and safety instrumented system registers, the vessel data book, the superseded flare load study, and a booking of two field tests chosen from six before any result is known.

## Difficulty

A flare load study is what a process safety or mechanical engineer does whenever a unit is modified, and it is a different exercise from sizing a relief device. A device is sized against the worst case it will ever see, one device at a time. A flare system is sized against what the plant does all at once: a single contingency reaches many items together, and the header and the stack tip have to pass the sum of what those items relieve. So the question is not how big each valve must be, but which valves a given contingency actually opens, how much they put into the header between them, and what pressure that raises at the far end of it. The answer is a table keyed on the contingency, not on the equipment.

The method is the one API 521 and the plant standards built on it set out, here RP-7. Its research analogue is the mechanics and thermodynamics of emergency relief in a collecting system: the heat a pool fire puts into a wetted vessel and the vapour that heat generates, the capacity of a control valve at full travel from its installed characteristic, the heat transfer of a reboiler at a duty other than its design duty, orifice metering when the density has moved away from the value the flow computer holds, a centrifugal pump's reach against a closed discharge, the mixing of streams of different molar mass and temperature into one header, and compressible pressure loss along a header whose flow accumulates towards the stack. The unit, its records and its documents are synthetic, written by authoring/provenance from a sealed definition. They are realistic, and so is the level of challenge they present:

- **The unit:** a natural gas liquids recovery train of nine relief devices, PSV-401 to PSV-409, on an inlet separator, a fuel gas knock-out drum, two reflux or receiver drums, a product drum, two fractionating columns, a feed/bottoms exchanger shell and a pump discharge, all nine discharging to one flare header with a 457 mm bore, 380 m of developed length and a 305 mm stack tip.
- **The contingencies:** loss of the normal electrical supply, loss of cooling water, loss of instrument air, and a pool fire in each of three fire zones. Six rows.
- **The deliverable:** for each contingency, the devices that discharge, the load in kg/h and the pressure at the header's inlet in barg. Nothing in the records states any of the three.
- **The booking:** the unit's test crew is on site for one shift and will run two of the six tests it offers. A test is charged when it is ordered, whatever it returns, and no test is run twice, so both orders have to be placed on what the records already say. Two of the six reach a graded value and four cannot.

The core difficulty is that the chain from a contingency to a relieving device runs through records that have moved on since the documents were written, and that the two numbers in each row depend on the device set being right first:

- **Loss of power now carries loss of air with it.** The 2019 study treated them as separate contingencies and said so in a note, because the instrument air compressor stood on the essential supply. A switchboard rebuild moved it to the normal supply; the drive schedule shows where it stands now, and the modification register says when it moved. So loss of power now opens the three control valves that fail open as well as taking the cooling away, and it becomes the governing case by a wide margin. The same modification left the safety instrumented system on the essential supply, which is what lets one instrumented credit survive the power failure.
- **Which control valves fail open is a record, not an assumption.** Three of six fail open and three fail closed. An assessment that takes them all one way either empties the air failure case or fills it with devices that cannot be reached.
- **One instrumented function of four may be credited.** Of the other three, one is below SIL 2, one is proof tested at 24 months against an 18 month limit, and one initiates on the very measurement the control whose failure causes the contingency uses, so it is not independent of it. The qualifying one removes a column's loss of cooling from two rows.
- **One device discharges under nothing at all.** A pump's blocked discharge is the only cause its register row admits besides fire, and its shutoff head has decayed to the point where it can no longer reach the relieving pressure. Only its latest performance test shows this; the data sheet curve would still reach.
- **The control valves do not have the coefficients on their data sheets.** Three of five have been re-trimmed and no document says so. The coefficient at full travel has to be fitted from the valve's own logged travel, pressures and flow through the equal percentage characteristic. One valve's flow column is read by the unit's feed meter, an orifice meter whose flow computer still holds the relative density entered at commissioning; the feed has got richer since, as the dated analyses show, so that flow is low by about 4 per cent and has to be corrected before the coefficient can be fitted. On the two valves whose coefficients do match their sheets, the fit confirms the sheet, which is how the method can be checked.
- **The reboilers are not at their design duty.** The data sheet duties are at the original feed rate and the unit now runs above it, so the coefficient-area has to come from the operating record. The vapour a column makes on total loss of cooling then follows from the steam supply temperature and the temperature of the liquid the column is boiling at the relieving pressure, which is its bottoms, not its overhead.
- **The fire cases turn on geometry and on insulation that changed after the data book.** A column was re-set 0.90 m higher on an extended skirt, which moves how much of it falls below the 7.6 m the fire case counts; the vessel data book is still the 2019 issue. Two items were re-insulated to a fire-resistant specification and now earn an environment factor, which collapses one zone's load by a factor of thirty; a third carries lagging with no certificate and earns nothing.
- **The header is not one pipe carrying one flow.** Devices tie into it at nine different distances from the stack base, so each length of header between two tie-ins carries only what ties in beyond it, and carries that mixture rather than the whole load. The pressure has to be worked out from the tip outwards, length by length, each with its own flow, its own mixture and its own density. One tie-in was moved 114 m out onto a new lateral after the isometrics were last issued, which changes which lengths carry its flow and moves the inlet pressure of three of the six rows.
- **The superseded study.** The 2019 flare load study on file is correct for the plant as built and states its basis. Taken as the answer now it gets none of the six rows right, and the note it ends on is the thread the whole study pulls.
- **Two quantities are in no record at all, and the booking is what gets them.** The stack tip was replaced in 2025 by another vendor who supplied no performance data, so the loss coefficient of the tip now installed is written down nowhere; the figure in the 2019 study belongs to the tip it replaced and is 16 per cent away from it, which is enough to fail five of the six rows. P-401's rotating element was renewed in 2026 with a trimmed impeller and not performance tested, so every curve on record describes a pump that could still reach PSV-405's relieving pressure, where the one now installed cannot: an assessment made on the record carries a device that does not discharge. Both have to be measured, and the booking is exactly two tests, so neither order may be spent on the four tests that cannot reach a row. Working out which those are is the study in miniature: E-406's coefficient-area is only ever used for a cause the credit for SIF-4061 sets aside, no device admits a cause PV-4031 could create, a loss of cooling is total however capable E-404 is, and PSV-404's set pressure is already in the shop record.

Each of these defeats an assumption the general approach makes on first reading:
- that contingencies named separately in a standard stay separate on a particular plant;
- that a data sheet describes the equipment installed;
- that a meter's indication is the flow;
- that a design duty is the duty;
- that every cause a register admits is a cause that can happen, and that a protective function listed may be credited;
- that a data book or an isometric issued with the plant still describes it;
- that a header can be treated as one pipe passing the whole load;
- that every figure the files carry describes the equipment that is there now, and that a measurement is worth making because it can be made.

The gate is all six contingencies, in all three columns.

## Reference solution

solution/solve.py is the reference; solution/solve.sh runs it in the agent's environment. It uses only the records in /app/data.

1. **The booking.** Two of the crew's six tests reach a graded value and the other four cannot, so the orders are `tip-backpressure` and `pump-shutoff`. The tip's coefficient enters every pressure and is on no record; P-401's present shutoff decides whether its blocked discharge is credible at all, so which devices discharge on a loss of air. The reference places both orders itself before it reads anything the crew wrote.
2. **The device as it stands.** The set pressure is the one the shop record of the last work leaves, not the register's: PSV-403 was reset in situ to 29.5 barg against the register's 31.0, and PSV-409 to 9.5 against 11.0.
3. **What the contingency reaches.** The drive schedule gives the supply and the cooling medium of each driven item, so loss of power takes the cooling from both columns and, because the air compressor now stands on the normal supply, also puts the air-failure valves into the power case. The control valve data give each valve's position on a loss of air. The fire zone schedule gives the items in each zone.
4. **Credit for instrumented protection.** A cause is set aside only where a function prevents it, is SIL 2 or better, is proof tested at not more than 18 months, initiates on a measurement other than the one the failing control uses, and still has the supply the drive schedule shows. One of the four qualifies.
5. **The feed.** FE-4011's flow computer holds a fixed relative density, so the true flow is the indication times the square root of the ratio of the current relative density to the one it holds. The current molar mass comes from the most recent analysis and the published component masses. Every other meter is a coriolis meter and is read as it stands.
6. **The control valves.** For each logged point of a valve's trend the standard's compressible expression gives the coefficient at that travel; the equal percentage characteristic and the data sheet rangeability refer it to full travel, and the record's mean is used. PV-4001's flow column is FE-4011's, so it takes the feed correction first.
7. **The reboilers.** For each day of the operating record the steam flow and the latent heat at the steam pressure give the duty, and the duty over the difference between the steam saturation temperature and the bottoms temperature gives the coefficient-area; the mean is used. The relieving rate uses the supply header pressure with the steam valve wide open, the bottoms temperature at the relieving pressure, and the latent heat of the bottoms liquid.
8. **The rates.** Fire gives the absorbed heat from the wetted area below 7.6 m, the environment factor from a certified fire-resistant system where there is one, and the vapour from the latent heat of the liquid held; a control valve failure gives the flow the valve passes at full travel from its source pressure to the relieving pressure; a loss of cooling gives the vapour the reboiler makes; a blocked discharge gives what the pump delivers at the head the relieving pressure needs, or nothing where it cannot reach it.
9. **The header.** The load is the sum of the rates, and what arrives is their mixture: molar mass from the total mass over the total moles, the ratio of specific heats, compressibility and temperature mass-weighted. The tip carries the whole load and gives the pressure at the stack base. Then each length of header between two tie-ins is taken in turn, from the stack base outwards, carrying only the devices that tie in beyond it and their mixture, with the density at the pressure already reached at its downstream end. The pressure at the blinded end is the answer. One tie-in is the isometrics' overtaken by a later modification; a length that carries nothing adds nothing.

**On the shipped records** (authoring/evidence/reference_run.txt) the reference identifies PV-4001 at 54.88 against a data sheet 64.0, PV-4071 at 37.78 against 27.0, PV-4021 at 3.08 against 2.50, and PV-4031 and PV-4061 within half a per cent of their sheets; E-403 at 26.73 kW/K and E-406 at 42.73 kW/K, 18.1 per cent above their data sheet basis; the feed 3.9 per cent above FE-4011's indication; P-401's shutoff head 7.6 per cent below its data sheet, which is what puts the blocked discharge out of reach; PSV-407's tie-in 114 m further out than the isometrics show; and T-402's wetted area 10.6 per cent below what the data book elevation would give. Its answer is power failure 99086 kg/h at 1.3247 barg, cooling water failure 54234 at 0.4869, instrument air failure 44852 at 0.3519, fire zone A 19958 at 0.0523, fire zone B 518 at effectively zero, fire zone C 38847 at 0.1280. All six rows stand, the worst relative departure from the sealed definition being 0.0013 on a load and 0.0027 on a pressure.

**authoring/evidence/independent.py** is a second study, written separately, sharing no code with the reference. It reads the records with pandas, builds one table of every device and contingency pair and groups it, and marches the header with numpy. It takes its own choices where the standard leaves room: the control valve coefficient by a least squares fit through the origin, the reboiler coefficient-area by a least squares fit of duty against temperature difference, and the pump curve by a least squares quadratic. It gets all six rows on the shipped records and on all 20 laboratory seeds, its worst relative departure being 0.0016 on a load and 0.0033 on a pressure.

## Verification

The deliverable is one CSV file, /app/output/flare_load.csv, with the devices that discharge, the load in kg/h and the pressure at the header's inlet in barg for each of the six contingencies. The verifier (tests/grade_flare.py, run by tests/test_flare.py under pytest) grades it against the sealed definition in tests/sealed:

- the set of devices must be exactly the set that discharges, in any order and separated by semicolons, spaces or commas;
- the load must be within 1 per cent of it, relative;
- the pressure must be within 1 per cent of it, relative, or below 0.002 barg where the sealed pressure is below that floor, which one fire case is.

The agent also has a booking of two field tests from the six the crew offers, ordered through a `fieldtest` wrapper before any result is known. The crew runs as a user of its own, charges the booking before it runs a test, refuses a test it has already run, and writes its reports where the agent can read but not write; the sealed definition it works from sits in a directory the agent cannot open.

The study is accepted only when all six rows stand. One pytest test carries the reward. test.sh writes 0 first, and writes 1 only when pytest exits 0 and the ctrf report shows exactly 1 test, 1 passed.

The truth comes from the sealed definition authoring/provenance/isim.py, never from running the reference, and the agent never sees it: the task is records only, so no copy of it is anywhere in the agent's environment. authoring/provenance/tune.py recomputes the design rules from it and checks them: that every contingency puts at least one device on the header, that no two contingencies name the same devices, that every device discharges somewhere bar the one the pump screen removes, that fire, loss of cooling and control valve failure all arise, that the governing load is at least ten times the smallest (192 times), that exactly one row sits below the pressure floor and every other stands at least ten times clear of it, that the governing contingency passes the 1.0 barg the 2019 study called the end of the margin (1.3262 barg), and that every identified quantity either differs from its data sheet by at least 2 per cent or matches within 1 per cent.

authoring/evidence/booking_study.txt grades every way the booking could be spent. Only `tip-backpressure` with `pump-shutoff` gets all six rows; every one of the other fourteen pairs gets at most five, and a study made with no test at all gets one. The four tests that reach no row are shown to reach none by getting the same count with and without them.

tune.py also measures what each layer of the study is worth, by setting the sealed state back to what the records would say if that layer were missed and recomputing the six rows. Against a band of 1 per cent: the column re-set 0.90 m higher 6.8 per cent, the tie-in moved after the isometrics 10.7 per cent, the two valves reset in situ 4.1 per cent, the fire-resistant insulation 3265 per cent, the feed meter's stale density 4.6 per cent, the control valve coefficients 3.8 per cent, the reboiler coefficient-area 25.5 per cent, the tip measured rather than taken from the 2019 study 9.0 per cent, and three layers that change the device set outright: the air compressor's supply, the safety system's supply, and the pump taken from the record rather than measured. No layer is worth less than the tolerance.

Two further rules cover the booking: that the tip now installed differs from the one the 2019 study worked to by more than the tolerance (16.1 per cent), and that the pump's recorded shutoff and its present one fall either side of the head section 7 screens on (582.0 m on record, 577.3 m needed, 545.0 m now), so that an assessment made on the record carries a device that does not discharge.

The seed (7301) drives only the scatter of the records; every answer comes from the parameters in the sealed definition. authoring/provenance/seed_screen.py screens seeds on three conditions (authoring/evidence/seed_screen.txt): every sound variation gets all six rows, every defective route fails, and the worst relative departure of any sound variation is within half the band. 19 of the 20 screened seeds are acceptable, the shipped one among them.

Why the gate is all six, measured on the shipped records. Every number below is copied from the named file in authoring/evidence.

Correct methods (method_spread.txt, independent.txt). The reference and seven sound variations all get 6 of 6 on the shipped records and on all 20 laboratory seeds:
- the trend fitted by least squares through the origin, or from the points above 60 per cent travel only;
- the reboiler coefficient-area from the record's mean duty over its mean temperature difference;
- the pump curve by least squares on all four points of the latest test;
- and three combinations of these.

Their worst relative departure is 0.0016 on a load and 0.0038 on a pressure, against a band of 0.0100, the pressure figure including the 0.11 per cent by which a five point back pressure test recovers the tip's coefficient. Two readings the standard does not sanction, which the tolerance nevertheless absorbs, are reported in the same file: taking every length of the header with the whole mixture's properties rather than with the mixture that length carries reaches 0.0050 on a pressure.

Defective routes (route_study.txt; the last column counts the laboratory seeds 7301 to 7320 on which the route gets all six). Every one of the 29 fails on the shipped records and on every seed, and so does the 2019 study taken as the answer:
| Route | Right of 6 | Worst contingency |
|---|---|---|
| the register's set pressure, not the setting the valve carries | 3 | cooling_water_failure load +2.5% |
| the air compressor taken on the essential supply | 5 | power_failure devices PSV-403 |
| the safety system taken onto the normal supply with it | 5 | power_failure devices PSV-401 PSV-403 PSV-406 PSV-407 PSV-409 |
| every control valve taken to close on a loss of air | 4 | instrument_air_failure devices none |
| the pump's rated flow taken as its blocked outlet rate | 5 | instrument_air_failure devices PSV-401 PSV-405 PSV-407 PSV-409 |
| no credit for instrumented protection | 5 | power_failure devices PSV-401 PSV-403 PSV-406 PSV-407 PSV-409 |
| credit taken without testing any condition | 3 | cooling_water_failure devices none |
| credit taken without the SIL floor | 4 | instrument_air_failure devices PSV-407 PSV-409 |
| credit taken without the proof test interval | 4 | instrument_air_failure devices PSV-401 PSV-407 |
| the data sheet coefficient for every control valve | 4 | instrument_air_failure load -2.0% |
| a linear characteristic for every control valve | 4 | instrument_air_failure load -56.6% |
| the largest logged flow taken as the relieving rate | 4 | instrument_air_failure load -51.8% |
| the feed meter read as indicated | 4 | instrument_air_failure load -2.3% |
| the reboiler coefficient-area from the data sheet duty | 4 | cooling_water_failure load -15.3% |
| the data sheet duty taken as the relieving duty | 4 | cooling_water_failure load -15.3% |
| the duty divided by the overhead's latent heat | 4 | cooling_water_failure load -18.5% |
| the pump's data sheet curve | 5 | instrument_air_failure devices PSV-401 PSV-405 PSV-407 PSV-409 |
| the last pump test on record, made before the element was renewed | 5 | instrument_air_failure devices PSV-401 PSV-405 PSV-407 PSV-409 |
| the tip coefficient the 2019 study worked to | 1 | cooling_water_failure pressure -4.9% |
| the booking spent on a test that reaches no row | 1 | cooling_water_failure pressure -4.9% |
| elevation changes since the data book left out | 5 | fire_zone_c load +3.5% |
| wetted area not cut at 7.6 m above grade | 4 | fire_zone_b load +25.9% |
| no drainage or firefighting credit | 3 | fire_zone_a load +64.1% |
| the whole shell taken as wetted | 3 | fire_zone_a load +100.7% |
| no insulation credit anywhere | 5 | fire_zone_b load +3265.4% |
| insulation credit without a certificate | 5 | fire_zone_a load -43.2% |
| 10 per cent accumulation for the fire case | 3 | fire_zone_a load -4.8% |
| the tie-in the isometrics show, the modification missed | 3 | fire_zone_c pressure -8.7% |
| the whole load along the whole header, in one length | 1 | cooling_water_failure pressure +11.8% |
| only the discharging tie-ins dividing the header | 5 | cooling_water_failure pressure +5.2% |
| the loss through the tip left out | 1 | cooling_water_failure pressure -34.4% |
| every density taken at atmospheric pressure | 1 | cooling_water_failure pressure +18.2% |
| the 2019 study's findings taken as the answer | 0 | cooling_water_failure load -13.2% |

Each of the six contingencies is failed by at least seven of the routes: power failure by 22, instrument air failure by 18, cooling water failure and fire zone C by 12 each, fire zone A by 10 and fire zone B by 7.

Hedging (hedge_study.txt). A hedge would need a defective reading to name the same devices as the sealed answer and to put both of its numbers within twice the tolerance, so that one row could satisfy both readings. Hedges exist on two rows only, fire zone A and power failure, and never on more than one row of a route that fails elsewhere; the gate is all six.

Null answers (null_baselines.txt). Each contingency is graded on its own, so a sheet made without the study can be right on one row by luck; the file lists every such free pass:
| Null answer | Right of 6 |
|---|---|
| every device that admits a cause, under every contingency | 0 |
| no device discharges anywhere | 0 |
| only the device with the lowest set pressure | 0 |
| the first zone's fire case, whatever the contingency | 1 |
| the 2019 study's findings copied | 0 |
| the right device sets with the 2019 numbers | 0 |
| the right loads with the header never computed | 1 |

Malformed sheets are rejected as a whole (verifier_checks.txt), every case built from the current reference at run time. This covers a sheet that is absent, a symbolic link, a directory, empty, header only, headerless, misspelt in its header or extended by a column; that has a row of the wrong length, a contingency missing, repeated, unknown or in upper case, or non-ASCII text, or that is larger than the 100 kB cap; that names a device that is not one, names a device twice in a cell, or writes one in lower case; or that carries a load or a pressure which is not a number, is empty, NaN, infinite, negative or above its ceiling. 54 cases were run and none was unexpected or crashed the grader. Four further cases drive tests/test.sh itself with pytest stubbed, forcing each combination of its exit status and its report's counts, and confirm that the reward follows the run: one only when pytest exits clean and the report holds exactly one passing test, zero when the report holds two tests, zero when pytest fails though the report looks right, and zero when no report is written at all. The reference sheet is accepted with CRLF line ends, blank lines, padded fields, rows in any order, devices separated by semicolons, spaces or commas and in any order, and numbers in exponent form, with any number of decimals, or with a leading plus.

The agent works as a separate user that can write only to /app/output. /app/data is read-only and root-owned. The verifier runs in a separate container without network, and /logs/verifier is root-only.
