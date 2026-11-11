# Design note: flare-load-study

Built 10-11 November 2026, delivered as `flare-load-study-20261111b.zip`, now `flare-load-study-20261111e.zip`. It began as the reshape of
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

## Rounds 2 and 3, after the screen rejected it

The screen solved it 3 of 3 at low effort in about two minutes. Two rounds of design followed.

**Round 2: the study stops coming out in sequence.** A conventional spring device is referenced to atmosphere,
so it opens at its set pressure plus whatever stands at its outlet, which is the header pressure at its own
tie-in, built up by the flow every device is putting in. The register says which devices carry a balanced
bellows and are immune. So rates, relieving pressures and header pressures are one system: section 6 now says
to sweep from no built-up pressure until no tie-in moves by more than 0.0001 bar. The feedback is negative, so
the sweeps close from below at about a tenth of the gap each pass and the fixed point is unique; nothing has to
be guessed and nothing can be skipped. A sequential reading is 8 per cent out on the governing load and gets
three of six contingencies wrong; ignoring the bonnet column gets two wrong.

Section 9 was added with it: the smallest tip the vendor supplies at which no conventional device is left
standing against more than 5 per cent of its own set pressure, reported as a second artifact with the binding
device named. That is an outer search with the whole coupled system inside it, because each candidate bore
changes the tip's loss and so every back pressure and so every rate. Scaling the shares off the installed tip
instead of re-converging picks 355.6 mm, one size too small. The answer is 406.4 mm, binding on PSV-409 at 4.45
per cent, with 355.6 mm failing at 5.96.

**Round 3: two silent two-state traps.** Each of the three re-trimmed valves has a trend in two blocks, one
before the work the maintenance log records on its trim and one in the last days of the record; all three came
back about 14 per cent below their data sheets, so a trend read whole overstates all three and the errors add.
E-403's operating record splits the same way at the steam trap renewal, the exchanger having been flooding and
making 85 per cent of its surface before it. Both figures that come out of a pooled read sit between the data
sheet and the truth, so there is nothing in them to check. Section 1 states the principle.

## What the three rounds actually measured

| Round | Low probes that solved it | What the failures failed on |
|---|---|---|
| 1, records only | 3 of 3 | nothing |
| 2, coupled system and the re-rating | 1 of 3 | the feed meter |
| 3, the two-state traps | 1 of 3 | the feed meter |

Nine probe runs. Every one implemented the coupled sweep. Every one found both two-state traps and cut both
records at the right day. Every one got the re-rating bore and the binding device right. The only thing that has
ever separated one run from another is the feed meter's stale configured density.

**The lesson, which is now in difficulty-calibration.md: stated against unstated, not hard against easy.** Every
layer these runs found is a principle written in the standard. The meter is the one layer no rule asks for: the
instrument schedule records a fixed relative density, the analyses record the gas, and the solver has to know
unprompted that mass through an orifice goes as the square root of density. One such correction at a
one-in-three failure rate leaves a two-in-three chance a run solves the task, which is a reject at screening;
three or four independent ones would put it at 0 of 3. Stated layers are what make a task fair and long. They
are not what makes it hard.

## Similarity, against the live pool

`tools/similarity.py` with relief-valve-adequacy, impeller-shrink-fits and shrink-fit-hubs excluded, those
being out of the pool: the sealed model 0.081, solution/solve.py 0.104, tests/grade_flare.py 0.240,
instruction.md 0.329, tests/Dockerfile 0.398. Four short files that the structure literals and the harness fix
sit higher: environment/Dockerfile 0.804, solution/solve.sh 0.560, tests/test.sh 0.521, tests/test_flare.py
0.471. Left alone on the evidence recorded in answers-bore-form-2026-11-11.md, where bore-form cleared
similarity five times with test_form.py at 0.855 and solve.sh at 0.749 against a task known to be live. The
substantive files are the ones that carry originality, and they are all far below.

## Round 4: the condensate and the level transmitter

Round 4 answered the screening rejection's demand for a harder core problem by adding two more corrections of
the shape round 3's analysis prescribed: a fact published in a record, with no rule pointing at it, needing
textbook equipment physics to notice.

**E-403's condensate leaves sub-cooled.** The exchanger data now publishes a condensate outlet temperature and
the condensate's specific heat beside the surface and the design duty. The duty a day of the record carries is
therefore the steam flow times the latent heat *plus* the sub-cooling from saturation to that outlet, and the
standard asks only for "each day's duty". Taken as latent heat alone the coefficient-area comes out 13.1 per
cent low (23.22 kW/K against 26.73), which is 21.7 per cent on the cooling-failure pressure and 3 of the 7
parts. The sealed definition derives the published steam flows from the full enthalpy drop, so the record is
consistent with itself and with the design duty scaled to the throughput; nothing in it looks odd.

**V-405's level transmitter is mis-ranged.** The vessel data book now states that its levels are what the level
transmitters indicate and publishes each item's liquid specific gravity; the instrument schedule carries a row
for each transmitter and records, for LT-4075 alone, that it was ranged for a specific gravity of 0.500 at
commissioning. The drum holds propane at 0.447. A differential-pressure transmitter reports the head it sees
divided by the density it was ranged for, so the level is 1.450 x 0.500 / 0.447 = 1.622 m. That is 53.99 m2 of
wetted area against 49.81, 6.9 per cent on PSV-407's fire rate, 2.7 per cent on fire zone C's load and 5.7 per
cent on its pressure. Both numbers are already in the published tables — propane at ambient is 0.500 in the
liquid properties, the drum's liquid is 0.447 in the data book — so no new data was needed, only the column
that says which is which. The other six transmitters are ranged for the liquid they read and their cells are
blank, exactly as the ten coriolis meters read "measured" beside FE-4011's fixed density.

Both are fair against the standard, which was the check that mattered. Section 4.4 asks for the duty and never
says how the steam delivers it. The fire section asks for the area in contact with liquid "at its highest normal
operating level" - the level itself, not the figure the data book prints - and the data book says its figure is
an indication. Neither correction is contradicted anywhere.

**What the probes then showed.** Three low-effort probes on a working rig scored 7 of 7, 4 of 7 and 4 of 7, and
all three found both new corrections and named them. The solve rate was 1 of 3, as it had been in rounds 2 and
3. The single step that separated the runs was the one that has separated every round: FE-4011's stale
configured density. The two failing runs reported that the pre-overhaul trend rows reproduced the data sheet and
that this confirmed their uncorrected reading; read uncorrected those rows give 61.70 against a sheet of 64.00,
and read corrected they give 64.13. The check was available, cheap and decisive, and the run that actually ran
it was the run that solved the task.

The finding is recorded in docs/difficulty-calibration.md: what defeats these runs is not an obscure fact but a
wrong answer that looks already validated.

### Similarity after round 4

Round 4 touched two of the files a similarity gate compares, `solution/solve.py` and `tests/sealed/isim.py`,
and both edits were additive: a `level` method and a `steam_drop` method in the solver, a `level` function and
the ranged-gravity table in the sealed definition. Measured with `tools/similarity.py`'s own normalisation and
`autojunk=False` against the nearest neighbour the full sweep found, relief-valve-adequacy:

| file | before | after |
|---|---|---|
| `solution/solve.py` | 0.476 ratio, 0.303 jaccard | 0.463, 0.293 |
| `tests/sealed/isim.py` | 0.557 ratio, 0.411 jaccard | 0.541, 0.391 |

Both fell, which is what adding original content to a file must do to either measure: the matching material is
unchanged while the total grows. The position is otherwise the one already accepted here - the two files share
the synthetic unit with their sibling by design, and bore-form-acceptance cleared the gate five times with a
file at 0.855 against a task known to be live.

A note on the instrument: the full sweep now takes longer than ten minutes, because `autojunk=False` on
whitespace-normalised files of this size is quadratic and the pool is 38 tasks. A targeted comparison against
the nearest neighbour the last full sweep found answers the only question a round of edits raises, and takes
seconds. Running the sweep without `autojunk=False` is not a shortcut: on files this long nearly every
character is popular enough to be treated as junk, which collapsed `solve.py` to 0.069 in a first attempt here.

## Official easiness screen on 20261111e: 3 of 3, rejected as too easy

All eight quality checks passed on all three trials; the precision rule and the single-order booking both held
(every trial placed the two tests together and wrote at least three figures). The screen, claude-opus-5-5 at low
effort, solved it 3 of 3 in about three minutes each, worst departure 0.34 per cent. Local probes with the model
matched to the screen then gave 7 of 7 twice in three minutes. The earlier local counts of 1 of 3 were the
weaker session model.

The task is finished as an engineering artefact and is not hard enough for the gate. Nothing of the kind added
in rounds 1 to 4 can change that: the screen found every layer, the carried fact included, in one reading. See
docs/difficulty-calibration.md for what that settles and what the next design has to be built around.
