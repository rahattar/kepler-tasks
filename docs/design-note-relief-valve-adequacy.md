# Design note: relief-valve-adequacy

Built Nov 10 2026 after reading all 36 task bundles for collisions. Subject: pressure relief adequacy of a gas
plant's nine relief valves. Chosen because the collision check found no catalogue entry in pressure relief or flare
systems, and because the deliverable shape the catalogue is thinnest on is a **categorical finding per item** -
a contingency name from a closed list, which a solver cannot sanity-check its way to.

## The deliverable and the gate

`relief.csv`, one row per valve: `valve,governing_case,required_area_mm2,verdict`.

- `governing_case`: one of `fire`, `blocked_outlet`, `control_valve_failure`, `cooling_failure`, `tube_rupture`,
  `thermal_expansion`.
- `required_area_mm2`: the effective orifice area that case needs, within 1 per cent relative.
- `verdict`: `adequate` or `inadequate`.

The gate is all nine rows right in all three columns. Truth: `authoring/provenance/isim.py`.

On the shipped records the answer is

| valve | item | governing case | area, mm2 | installed | verdict |
|---|---|---|---|---|---|
| PSV-401 | V-401 inlet separator | control_valve_failure | 480.19 | J 830 | adequate |
| PSV-402 | E-402 shell | tube_rupture | 516.64 | G 325 | inadequate |
| PSV-403 | T-401 deethaniser | cooling_failure | 1377.37 | K 1186 | inadequate |
| PSV-404 | V-403 reflux drum | blocked_outlet | 202.19 | H 506 | inadequate (inlet line) |
| PSV-405 | P-401 discharge | thermal_expansion | 0.052 | F 198 | adequate |
| PSV-406 | T-402 debutaniser | fire | 664.31 | J 830 | adequate |
| PSV-407 | V-405 product drum | control_valve_failure | 702.27 | H 506 | inadequate |
| PSV-408 | V-404 receiver | blocked_outlet | 425.63 | H 506 | adequate |
| PSV-409 | V-402 fuel gas drum | control_valve_failure | 347.50 | G 325 | inadequate |

All six case names govern somewhere; five valves are inadequate and four adequate.

## Why this subject

Three things in the catalogue's grain were deliberately broken:

1. **A categorical answer with no self-check.** Nothing in the records says which case governs any valve or whether
   any valve is adequate. The twelve probe reports behind `difficulty-calibration.md` all showed the agent
   validating its answer against a measured value before reporting; here there is nothing to validate against.
2. **Conservative error is fatal.** The answer is the maximum over candidate cases, so an error that *overstates*
   a non-governing case changes both the name and the area. In every other task in the catalogue, being
   conservative on a case that does not matter is free.
3. **Two quantities identified from records rather than read.** The control valves' coefficient at full travel
   (from their own operating trend, because two have been re-trimmed and no document says so) and the reboilers'
   coefficient-area (from the operating record, because the data sheet duty is at a throughput the unit no longer
   runs).

## The layers

Twenty-two, each load-bearing by `route_study.txt`:

1. the coefficient of each control valve at full travel, identified from its trend, against the data sheet
2. the equal percentage characteristic, so a point at 72 per cent travel is not 72 per cent of rated
3. the feed meter's fixed configured density against the current analysis
4. the reboiler coefficient-area at the throughput the unit runs, not the data sheet duty
5. the bottoms temperature at the relieving pressure, not at the normal one
6. instrumented protection credited on T-402 (SIL 3, independent initiator, 12 month proof)
7. instrumented protection refused on T-401 (initiator shared with the control whose failure causes the case)
8. instrumented protection refused on V-402 (24 month proof interval) and V-401 (SIL 1)
9. the two-thirds rule, which does not excuse the E-402 tube rupture
10. two tube ends discharging, not one
11. the orifice the valve carries, from the shop record, against the register's letter
12. the set pressure as last left, against the register's
13. the rupture disc combination factor on PSV-402
14. T-402 re-set 0.90 m higher since the vessel data book was issued
15. fire-resistant insulation credited on V-403 and T-401, refused on V-401's uncertified lagging
16. the viscosity correction, iterated, on the two liquid cases
17. the pump's shutoff head as last tested, which puts its blocked discharge out of reach
18. the source pressure below the relieving pressure, which puts PSV-408's control valve failure out of reach
19. the 3 per cent inlet line rule, which PSV-404 fails after a 2021 uprate left its pipework alone
20. the 7.6 m cut on wetted area, and the tray bands of a column below it
21. 21 per cent accumulation for fire against 10 per cent for the rest
22. the 2019 study, correct for the plant as built and wrong now on five of nine valves

The Kb and Kw tables are inert: every back pressure ratio on the unit is below the first tabulated entry, so both
factors are 1.00 throughout. They are a decoy a solver has to check, not a layer.

## Evidence

- `route_study.txt`: 25 defective routes. Every one fails on the shipped records and on all 20 laboratory seeds
  (0 of 20 each). Every valve is failed by at least 3 routes; the thinnest are PSV-404 and PSV-408 at 3.
- `method_spread.txt`: 9 sound variations, all 9 of 9 on the shipped records and on all 20 seeds. Worst relative
  area 0.24 per cent on the shipped seed, 0.51 per cent over all seeds, against a band of 1 per cent. The worst is
  always PSV-401, where the answer rides on the identified control valve coefficient.
- The nearest defective route is properties taken at the item's normal pressure, at 1.2 per cent: 5 times the
  worst sound method on the shipped seed.

## Fairness work the probes forced

Round 1 of three low-effort probes found three defects of mine, all of which made the task unfair rather than
hard:

- the vessel data book said T-401 held its *overhead* stream, while the sealed definition used its bottoms for the
  reboiler temperature difference. All three probes took the book at its word and got PSV-403's cooling case
  59 per cent high. Fixed by naming the bottoms liquid correctly and by having section 9 of the standard say that
  Tb is the saturation temperature of the liquid the column holds, as the vessel data book names it.
- the latest feed analysis was dated after the assessment date, so two probes used the previous one and carried a
  0.5 per cent molar mass error into the control valve fit. Fixed by ending the analyses before the date.
- `valve_history.csv` was hand written and had drifted from the sealed definition's orifice letters. Fixed by
  deriving the shop record's as-left setting and orifice from the sealed definition.

A fourth finding was a precision knife-edge rather than a defect: PSV-405's thermal expansion case needs
0.052 mm2, and all three probes rounded it to 0.05 or 0.1 and lost the valve on arithmetic. The instruction now
asks for at least three significant figures.

## Local probe rounds

Nine low-effort runs and three xhigh, each in its own sandbox with only the agent's records, each graded with
`tests/grade_relief.py`.

| round | effort | records | right of 9 | solved |
|---|---|---|---|---|
| 1 | low | before the three fairness fixes | 7, 7, 5 | 0 of 3 |
| 2 | low | after them, before the fire-properties clause | 7, 9, 7 | 1 of 3 |
| 3 | low | shipped | 8, 8, 8 | 0 of 3 |
| 4 | xhigh | shipped | 9, 8, 7 | 1 of 3 |

Easiness: 1 of 6 low-effort runs on records free of my own defects. Difficulty: xhigh fails on two of three.

**What separates a pass from a failure is one layer, and it is the same layer every time.** PV-4001's trend flow
is read by FE-4011, the one meter whose flow computer holds a density the gas no longer has, so the coefficient
fitted from that trend is 4 per cent low unless the flow is corrected first. Eight of the twelve runs corrected
the feed for the blocked-outlet cases and then fitted the coefficient from the uncorrected trend. The link is
stated - `control_valve_data.csv` names the meter for each valve and the instrument schedule says what that meter
holds - but it has to be made rather than read, and that is what the runs miss.

The second discriminator is narrower: one xhigh run left the viscosity correction at 1 on PSV-405's thermal
expansion case, which is 5.9 per cent.

Everything else was found by every run at both efforts: the re-trimmed valves, the stale register rows, the field
reset, the raised column, the insulation certificates, the three refused instrumented credits and the one
accepted, the two contingencies that cannot happen, the inlet line after the 2021 uprate, and the superseded
study. Several runs validated themselves by reproducing the 2019 study from its own stated basis, which is a check
I had not anticipated and which worked: the study is dated, so reproducing it confirms the method without
confirming the answer.

## Lesson for the lever list

Three of the levers `difficulty-calibration.md` lists as untried were aimed at deliberately, and the probe rounds
say what each was worth:

- **An answer the solver cannot confirm from its inputs.** Worth little on its own. The contingency name and the
  finding are nowhere in the records, but a run that gets the physics right gets the name right as a by-product,
  and the runs found their own anchor anyway by reproducing the dated 2019 study.
- **A quantity where the natural estimator is biased.** Worth nothing as stated. The data sheet coefficient is the
  biased estimator, and every run went to the trend instead - because section 8 of the standard has to tell them
  to, or the task is unfair.
- **A fault visible only in raw data.** Worth something, but only in the one form where the fault is not a fact to
  be read but a *link between two records that has to be made*. The meter's configured density is stated and
  every run found it; what they missed is that the same meter supplies a column in a different file. That is the
  only layer of twenty-two that separated the runs.

Which sharpens the lever, and is the finding worth carrying forward: **what frontier runs miss is not hidden
facts, it is connections between facts they have already read.** A fact stated anywhere is found, as
impeller-shrink-fits established. A fact that must be carried from one record into the use of another is found
about two thirds of the time, at both efforts. Twenty-two layers produced one such link by accident; a task built
deliberately out of six or eight of them would have real headroom.

A second finding, from building this one rather than from the probes: **the fairness requirement is what destroys
these layers.** Every one of the twenty-two had to be derivable from the agent's files, which meant writing it
down, and writing it down is what made it findable. The three defects the first probe round exposed were all
places where I had made a layer unfair by *not* writing something down - a stream named inconsistently, an
analysis dated in the future, a shop record out of step with the sealed definition - and fixing each of them
removed a failure. The tension is structural, not a matter of craft.
