# Design note: flare-load-study

Built 10-11 November 2026, delivered as `flare-load-study-20261111b.zip`. It began as the reshape of
relief-valve-adequacy after that task's fourth rejection, and ended as a different kind of task: the first in
the catalogue keyed on the contingency rather than on the equipment, and the first of mine whose difficulty
comes from deciding what to measure rather than from reading records carefully.

## The deliverable and the gate

Six rows, one for each contingency RP-7 names: `power_failure`, `cooling_water_failure`,
`instrument_air_failure`, `fire_zone_a`, `fire_zone_b`, `fire_zone_c`. Each row carries the set of relief
devices that discharge under it, the load they put on the flare header together in kg/h, and the pressure that
load raises at the header's inlet in barg. A row stands only when the device set is exactly right, the load is
within 1 per cent and the pressure is within 1 per cent, or under 0.002 barg where the sealed figure is under
that floor, which one fire case is. The study is taken only when all six rows stand.

The answer on the shipped records:

| contingency | devices | load, kg/h | header inlet, barg |
|---|---|---|---|
| power_failure | PSV-401 PSV-403 PSV-407 PSV-409 | 99148.6 | 1.3262 |
| cooling_water_failure | PSV-403 | 54237.3 | 0.4869 |
| instrument_air_failure | PSV-401 PSV-407 PSV-409 | 44911.3 | 0.3529 |
| fire_zone_a | PSV-401 PSV-402 PSV-409 | 19957.5 | 0.0523 |
| fire_zone_b | PSV-403 PSV-404 | 517.5 | below the floor |
| fire_zone_c | PSV-406 PSV-407 PSV-408 | 38847.4 | 0.1280 |

## Why this shape, and not the valve

relief-valve-adequacy asked, for each of nine valves, which contingency governs it and whether it is adequate.
That is the archetype the validator finally rejected it for: a per-item assessment against a multi-requirement
plant standard, which hoist-brake-sizing, surge-vessel-sizing, bore-form-acceptance and impeller-shrink-fits
already occupy. The collision was not in the subject - no other bundle touches pressure relief - but in the
shape of the answer.

A flare load study is the natural question that is not that shape. A relief device is sized against the worst
case it will ever see, one device at a time; a flare system is sized against what the plant does all at once. A
single contingency reaches many items together, and the header and the tip have to pass their sum. So the row
is a scenario, the device set is part of the answer rather than the index of it, and the two numbers are an
aggregate and a system pressure. Nothing else in the catalogue answers a question of that form.

## The layers

Twenty-two readings of the records separate a right answer from a wrong one. The ones worth naming:

- **Loss of power now carries loss of air.** The 2019 study treated them separately and said in a note that any
  change to the supply the air compressor stands on should be referred back. MOD-2024-11 moved it to the normal
  supply. This makes power failure the governing case and is the thread the whole study pulls.
- **The same modification left the safety system on the essential supply**, which is what lets one instrumented
  credit survive the power failure. An assessment that assumes the system moved with the compressor loses it.
- **One instrumented function of four may be credited.** One is below SIL 2, one is proof tested at 24 months
  against an 18 month limit, and one initiates on the very measurement the control whose failure causes the
  cause uses. T-401 is the one protected item with no separate protection transmitter, and that asymmetry is
  what decides it.
- **Three of six control valves fail open and three fail closed**, so an assessment that takes them all one way
  either empties the air failure case or fills it with devices that cannot be reached.
- **The segmented header.** Devices tie in at nine distances from the stack base, so each length between two
  tie-ins carries only what ties in beyond it, and carries that mixture rather than the whole load. The walk
  runs from the tip outwards, each length with its own flow, mixture and density. One tie-in was moved 114 m
  out after the isometrics were last issued.
- **The feed meter's stale configured density**, worth 4.6 per cent, carried into the one control valve
  coefficient that is fitted from its trend.
- **The reboiler duty divided by the latent heat of the liquid the column is boiling**, which is its bottoms,
  not its overhead. Three probes found this before I did; see below.

`authoring/provenance/tune.py` measures what each layer is worth by setting the sealed state back to what the
records would say if the layer were missed. Against a band of 1 per cent: insulation 3265 per cent, reboiler
coefficient-area 25.5 per cent, tie-in 10.7 per cent, tip 9.0 per cent, elevation 6.8 per cent, meter 4.6 per
cent, set pressures 4.1 per cent, coefficients 3.8 per cent, and three that change the device set outright.

## The booking, and why it exists

The task was built first as records only, and it was too easy: three low-effort probe runs solved all six rows
exactly. Adding layers did not help - the segmented header, the relocated tie-in and the SIL floor were all
handled by every low-effort run. Written-down layers are findable by a careful reader, and frontier models read
carefully. See `difficulty-calibration.md`.

What defeats effort is information the agent does not have and must decide to buy. So the unit's test crew now
offers six field tests and the booking is two, ordered before any result is known:

| test | reaches a graded value? | why |
|---|---|---|
| `tip-backpressure` | yes | the 2025 replacement tip came with no performance data, so its loss coefficient is written down nowhere, and it enters every pressure |
| `pump-shutoff` | yes | P-401's rotating element was renewed with a trimmed impeller and not performance tested, and its present shutoff decides whether a blocked discharge is credible at all |
| `reboiler-E406` | no | E-406's coefficient-area is only ever used for a cause the credit for SIF-4061 sets aside |
| `valve-PV4031` | no | no device admits a cause PV-4031 could create |
| `condenser-E404` | no | a loss of cooling is total however capable the condenser is |
| `popcheck-PSV404` | no | PSV-404's set pressure is already in the shop record |

Both gaps are made by the records rather than hidden: the flare note says the tip's coefficient is on no record,
and the maintenance log says the element was renewed and not tested while section 7 says the present condition
governs. The 2019 study publishes the coefficient it worked to, 1.55, which belongs to the tip that was
replaced and is 16 per cent away from the one installed - so the shortcut that avoids spending an order is
punished. `authoring/evidence/booking_study.txt` grades all fifteen ways of spending the booking: only
`tip-backpressure` with `pump-shutoff` gets six, every other pair gets at most five, and nothing ordered gets
one.

The crew follows the contract bore-form-acceptance established: a user of its own, the sealed definition in a
directory the agent cannot open, the booking charged before the test runs, repeats refused, state created with
`O_EXCL` and `O_NOFOLLOW`, reports written where the agent can read but not write.

## Evidence

- 32 defective routes, every one failing on the shipped records and on all 20 laboratory seeds. Each of the six
  rows is failed by at least seven of them; power failure by 22.
- 8 sound variations, all six rows on every seed, worst departure 0.16 per cent on a load and 0.38 per cent on
  a pressure against a 1 per cent band. Two readings the standard does not sanction but the tolerance absorbs
  are reported in the same file rather than counted as sound.
- Three implementations agree: the sealed definition, `solution/solve.py`, and a second study written
  separately in pandas and numpy that builds one table of every device and contingency pair and groups it.
- 7 null answers, the best getting 1 of 6.
- 54 malformed-sheet cases through the real grader, 0 unexpected, plus 4 that drive `test.sh` with pytest
  stubbed and confirm the reward follows the run.
- 88 preflight checks, 0 failed, from a clean unpack of the delivered zip.

## Fairness work the probes forced

Six defects, all found by probe runs rather than by me:

1. **The reboiler latent heat.** My model divided the duty by the overhead vapour's latent heat; all three
   probes used the bottoms liquid's, which is right. I had the physics wrong and they corrected it.
2. **T-402's geometry.** The bottoms liquid stood above the lowest tray, so tray bands double-counted shell
   that was already wetted. A probe flagged it as "internally odd" and followed the standard's wording rather
   than reinterpreting. The trays moved to 8.30 m.
3. **A flat extrapolation.** PSV-403's relieving pressure fell past the end of the propane saturation table, so
   the answer was insensitive to its set pressure and "held flat" became a load-bearing convention. The table
   now runs to 42 bara.
4. **The component basis.** Reading `c5plus` as hexane rather than pentane moved the feed-gas rates 1.1 per
   cent, past the band. The component masses are now published.
5. **The cut convention.** Dividing the header only at the tie-ins of discharging devices differs from
   dividing it at all of them by up to 5.1 per cent. The standard now says which, explicitly.
6. **The leaked answer.** My first draft of the flare note said the 2019 figure was 1.80 - the true
   coefficient of the tip the agent is supposed to measure. The note now quotes nothing and the 2019 study
   states its own basis, 1.55.
7. **How a liquid joins the mixture.** Section 5 said nothing about it, so two probes validating against the
   2019 study reproduced five of its six rows and not the air-failure pressure, which is the one row a pumped
   liquid enters. It touches no graded value - the pump screen keeps PSV-405 out of all six present rows - but
   it cost a probe real effort and could have led one to "fix" a correct method. Section 5 now states that a
   liquid enters on the molar mass of what it passes, k 1.05, Z 1, at its pumped temperature.

## Local probe rounds

Twelve runs in all. Before the booking: three low runs solved all six rows, three xhigh runs failed on plain
slips (two skipped the meter correction, one dropped a device from a fire zone). After the booking: one low run
of three solved it, one credited an instrumented function it should not have, one missed the meter correction;
all three xhigh runs solved it.

Every one of the six runs ordered the right two tests and said why the other four were pointless. So the
booking is decidable from the records, which is what fairness requires, but **the choice of tests was not
itself the discriminator**. What the booking did was add two more steps that have to be right, and the low-effort runs
spent their care there instead of on the meter. That is worth knowing before building the next one: a budget
raises difficulty by lengthening the chain, not by making the choice hard, unless the useless tests are made
genuinely tempting.

## Similarity

Two of relief-valve-adequacy's four rejections turned on similarity, so this was measured before packaging, per
file and per class, against all 38 other bundles. Against every task but its own predecessor nothing exceeds
0.11. Against relief-valve-adequacy the first measurement was 0.43 on the solution, 0.55 on the verifier and
0.98 to 1.00 on the harness files.

Collapsing every identifier *raised* those numbers, which settled the question of what to do: the overlap was
structural, not nominal, so renaming the plant would have achieved nothing. What worked was rewriting the
harness around the mandated literals (0.98 to 0.31 on `test.sh`, 0.98 to 0.35 on `tests/Dockerfile`, 1.00 to
0.21 on the agent Dockerfile) and rewriting the grader's reader as a table of column specs (0.41 to 0.25), with
the 54 verifier cases holding the behaviour fixed. Nothing now sits above 0.35 per file; the verifier class is
0.386, inside the 0.390 that accepted pairs in the catalogue reach at the ninetieth percentile.

The precedent that made shipping reasonable rather than rebuilding from scratch: shrink-fit-hubs was rejected
as too similar to flange-torque-spec and reworked as impeller-shrink-fits, which passed while its rejected
predecessor sat in the pool. A reworked sibling is not blocked by its predecessor; what the gate caught in
November was scaffolding shared with *other, independent* tasks, and the archetype.
