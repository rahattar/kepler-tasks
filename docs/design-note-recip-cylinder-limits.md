# Design note: recip-cylinder-limits (latest task, Nov 10 2026)

**Status:** built, preflight-clean (441 checks). Advisory and open: the task.name prefix.

**Task:** reciprocating gas booster K-4101 on a declining field. Six-throw balanced opposed frame, 305 mm stroke,
three stages discharging at 48, 110 and 170 bar a; six double-acting cylinders.
- **Deliverable:** /app/output/cylinder_limits.csv, a lowest allowable suction pressure in bar a and a governing
  requirement per cylinder. Twelve graded values, tolerance 0.5 per cent relative on the pressure, exact name on the
  requirement, gate 12 of 12.
- **Lab:** `gc <stage>` (gas analysis, mol per cent to 0.01) and `weigh <cylinder>` (reciprocating weight, kg to
  0.1). The allowance is 2 readings across both.
- **Standard RC-4:** six requirements - gas load against the cylinder's rating; combined rod load in compression and
  in tension against the frame's; discharge temperature; cylinder power; pin reversal. The answer is the lowest
  0.01 bar acceptable at that pressure **and at every higher pressure in the range**.
- **Answers:** 1A 20.75 tension, 1B 21.38 gas_load, 2A 35.69 discharge_temperature, 2B 44.56 compression,
  3A 85.81 cylinder_power, 3B 116.77 compression. Five requirements govern; runner-up gaps 5.1 to 38.9 per cent.
- **Seed:** 4101.

## Why this subject, after skid-noise-guarantee
The acoustics task failed its easiness gate five rounds running because every obstacle in it was a discoverable
record and the arithmetic was a reduction: find the fact, apply the correction, add decibels. Nothing had to be
*computed* against a narrow window. This task keeps the method (sealed definition, records that disagree with the
data sheet, a booking smaller than the number of unknowns) and moves it onto a quantity that is the root of many
small terms: a pressure found by scanning a load diagram, where the rod diameter, the as-bored bore, the speed, the
reciprocating weight, the clearance, the gas exponent and the valve losses each move the answer by 4 to 40 times the
tolerance, and several of them change which requirement governs.

## Layers
1. **Four facts want a reading, the allowance is 2.** Stage 2's gas and 3B's weight have no record; stage 3's gas
   follows from the bypassed separator (log), 2B's weight from the register's shop ticket (+18.0 kg).
2. **Inertia.** Dropped, no cylinder has an acceptable pressure at all (reversal fails everywhere). Primary term
   only, two cylinders come out on the wrong requirement.
3. **Speed** 327 rev/min (drive record), not the data sheet's 350: inertia goes as the square.
4. **Rated rod load** 150 kN by service bulletin, not the nameplate's 165.
5. **3B de-rated** to 128 kN for that throw alone, after its crosshead repair.
6. **2B liner at the first repair size,** 134.00 mm as bored against a 130 nominal.
7. **2B's new piston,** 18.0 kg heavier, from the register's ticket - the recoverable half of the squeeze.
8. **3B's spare assembly,** 331 kg, weight on no record: the reading that cannot be avoided.
9. **1B's larger piston rod,** 85 mm in one column of the schedule, which is what puts it on the gas load.
10. **Clearance pockets of 2A and 3A open,** so the clearance is the sheet's plus the pocket; 3A is power-governed,
    so this one is load-bearing.
11. **Fouled after-cooler:** stage 2's suction temperature is the trend's 42 C, not the design 36.
12. **Bottle-mounted element:** TI-2201 sits on the suction bottle, so +6 K to the valve flange.
13. **Gas per stage.** The analysis of record is the feed's; each separator takes condensate out, so k rises stage
    by stage (1.2543, 1.2657). Taken as 1.30, the temperature-limited cylinder is wrong.
14. **Gas load against the cylinder's rating, not the frame's** - API rates them separately, and conflating them
    moves 1B onto the wrong requirement.
15. **The scan rule.** Power peaks at an intermediate ratio, so 3A is acceptable, unacceptable and acceptable again
    as the pressure falls. Scanning upward for the first acceptable pressure gives 52.47 bar on the wrong
    requirement, 33 bar low.
16. **Pin reversal is a decoy** in the shipped scenario: met throughout every window with at least four times the
    least angle. It is what punishes layer 2.

## Evidence
- Reference worst value 0.034 per cent; worst of eleven sound variations 0.198 per cent (40 per cent of the band);
  separately written second solution 0.051 per cent over 20 seeds.
- Nearest defective route 3.92 per cent: about twenty times the sound spread, and 7.8 times the tolerance.
- 23 routes studied, 22 fail; every one of the twelve values failed over the 1 per cent bar by at least 3 routes.
- Best null answer 10 of 12, and that one is handed the true pressures.
- 34 malformed-sheet cases, none crashed the grader.

## Calibration (local)
- **Round 1** (records as first written): low 3/3 solved, xhigh 3/3 solved. Every probe reproduced the reference
  answers exactly. Their own reports named the cause: the standard quoted a worked value of k for the analysis of
  record, which all six used as a check on their gas handling; the register handed over the arithmetic ("the
  reciprocating weight of throw 4 is the data sheet's weight and this difference"); clause 4 explained *why* the
  reachability rule exists, which is the hardest layer; and the load-bearing numbers were in bold.
- **Changes made:** the worked k removed; clause 4's rationale removed; clause 5's checklist of what has changed
  reduced to one sentence; the register rewritten in a flat clerical voice with no conclusions and no emphasis;
  the log entries stripped of their pointers; the pocket given as a volume so the fraction must be worked out
  against the head end's swept volume; the shop ticket given as two piston weights rather than a difference; the
  liner record given a dated history so the bore of record must be picked by date; the exponent taken at the mean
  of suction and discharge temperature, so it and the discharge temperature must be iterated together and differ
  cylinder by cylinder; clearance split into head end and crank end.
- **Round 2** (all of the above): low 3/3 solved again. Each probe independently derived the piston difference,
  converted the pocket volume against the head end, iterated the exponent, took the latest liner entry and spent
  both readings correctly.
- **Conclusion of rounds 1 and 2:** the easiness gate is not met and the layers are not what is holding it. Six
  low-effort probes across two record designs solved the task; de-signposting and two extra computed steps changed
  nothing.

## The coupled rebuild (round 3)
The task was rebuilt so that the duty itself has to be solved rather than read. Nothing is set but the field
pressure, the pipeline pressure and the contract flow:
- the two interstage pressures settle where each stage passes the molar flow the one before it delivers, less the
  condensate its separator knocks out - two equations in two unknowns, with the volumetric efficiency, the
  exponent and the discharge temperature all inside them;
- the speed is whatever the contract flow needs at those pressures, so as the field declines the speed rises and
  the inertia load of every throw rises with the square of it;
- the range ends where that speed reaches the frame's rated speed, which the solver has to find;
- every cylinder is therefore coupled to every other: open a pocket on one and the stage loses capacity, the
  pressure above it rises, the speed rises, and all six throws are loaded differently.

The deliverable became the lowest **field** pressure per cylinder. Four requirements govern: rod load in tension
(1A), cylinder power (1B, 2A, 2B), rod load in compression (3A, on its de-rating) and discharge temperature (3B,
on a fouled cooler read through a bottle-mounted element). Answers 17.54 to 22.66 bar in a range of 15.99 to 26.00.

**Round 3a (3 low):** all three built the whole coupled model correctly and all three reported that their speed,
226.1 rev/min, disagreed with the operating record's 230. They were right: clause 2.2 of my standard said the
speed follows the flow through the first stage, while the sealed definition used the flow the last stage delivers,
which is what an export meter reads. The probes followed the clause. **That was an authoring bug, not a
discrimination** - difficulty from an ambiguity is the one kind the playbook forbids - and the records themselves
caught it, because the measured speed is in the operating record for exactly that reason.

**Round 3b (3 low), clause corrected:** 3/3 solved, 12 of 12 values each, in three to five minutes apiece. Every
probe solved the two-equation balance, derived the speed, found the range edge, iterated the exponent with the
discharge temperature, converted the pocket volume against the head end's swept volume, took the latest liner
entry, differenced the shop ticket's two piston weights, applied the bulletin factor and the de-rating, corrected
the bottle-mounted element, and validated its own model against the measured interstage pressures and speed before
reporting.

## Calibration, all three designs
| design | what it asked for | low probes solved |
|---|---|---|
| skid-noise-guarantee | reduce a survey to sound power, 5 rounds | 15 of 15 |
| recip-cylinder-limits, fixed stage pressures | reduce records to a limit, 2 rounds | 6 of 6 |
| recip-cylinder-limits, coupled duty | solve the duty, then the limits | 3 of 3 (after a doc fix) |

Twelve low-effort probes, twelve solves. Adding modelling depth did not move the gate: a two-equation nonlinear
balance inside a scan is no harder for the model than a fixed-point iteration, and both are specified in the
standard because they have to be.

The impeller-shrink-fits official run of Nov 9 (8 of 8 solved, rejected as too easy) points the same way, and it
also disposes of the one hypothesis I had left: that the micron-scale precision of that task was what made it hard
for low effort. It was not. What is untried is inference - an answer that cannot be read out of the records at any
level of care, because it has to be estimated from raw data, or because only physics settles which of two records
is right, or because the wrong measurement plan leaves it unobtainable.
