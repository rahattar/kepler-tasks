# Difficulty calibration lessons (from Alex's Kepler tasks, Oct-Nov 2026)

**The bar these lessons are read against (Alex, Nov 13):** easiness probe, 0 of 3 solved at low effort;
difficulty probe, pass band 0 to 5 of 8 at xhigh. **And the gate since the evening of Nov 13:** every condition
that decides a hidden case is stated in the documents (`docs/playbook.md`, design gate). Rates measured on cores
whose condition was unstated do not carry over; `docs/review-2026-11-13-five-cores.md` reads five of them. The sections below were written as the bar moved, and say so
where they were written against an older one.

## What makes official xhigh fail
- Official xhigh fails on rare coverage slips spread over many independent layers, not on hard modelling.
  pump-wear-assessment: about 10 layers went 8 of 8 officially; about 13 layers went 7 of 8.
- Layers that only the data reveal (records disagree, and only the data settle which is right) slip more often
  than documented corrections. Aim for 13-15 independent layers, several of them data-only.
- Heavy modelling alone does not open the effort gap. Identifying and simulating a lightly damped two-mode
  suspension (screen-fatigue) was done by low effort and xhigh alike.
- superheater-tube-life passed every stage: records-only, about 12 layers, several data-only (thermocouple offsets
  visible only as a ratio step against a neighbour, a silent drift, swapped tags, a tube thinner than the
  register). Local probes: low 1/3, xhigh 2/2. Official: all green, with one difficulty trial failing.
- Local xhigh probes (Claude subagents at xhigh) are stronger than official runs. A local 3/3 has shipped and
  still passed the official difficulty screen.

## What did not work
- Rotor field balancing (three designs): low effort solved it every time. Influence-coefficient balancing is
  linear algebra on documented conventions.
- A one-shot measurement budget whose gaps are flagged plainly in the log is found by low effort. Hiding a gap
  behind a correctable-looking fault traps xhigh more than low.
- The service-plus-budget skeleton (a fieldwork command, ten units, a JSON damage file) failed similarity against
  screen-fatigue. Don't reuse it.
- Clean steps get found: a fault that shows as a clean step against peers, or in a single balance, is found by low
  effort. Opus low runs header balances, peer ratios and step searches unprompted.
- Procedure lines can hint. "Hours whose inputs are unknown are left out", combined with a repaired fault, invites
  the solver to use only the post-repair window.
- Noise-driven difficulty: an agent hugging a single lab reading with no stated repeatability fails on unlucky
  draws. That is a knife-edge, and reviewers dislike it. State the repeatability, then ship a seed on which a
  bore placed only 1 sd inside a limit fails (impeller-shrink-fits).

## What opened the effort gap
- Several faults projecting onto one diagnostic (cooling-tower: three faults all sit in the
  header-minus-risers residual).
- A test budget smaller than the number of things needing measurement, with one escape hidden in a record
  (impeller-shrink-fits: four materials need data above 100 C, 3 tests, and a mill value in one certificate).
- A dated change in the log that makes an earlier survey or certificate stop applying.
- A one-column detail in a table (a spin-test speed differing for one row), or an instrument calibration error
  given in an inspection report.

## Fairness
- Zero-flow windows must be unambiguous. Show a zero error where zero flow is certain (blind flange, pump trip).
- Correct methods can be fragile too. Check method_spread before keeping a layer: every sound method must pass on
  the shipped seed and on nearly all of the 20 laboratory seeds.
- Quality review wants:
  - the solution text to match the code exactly;
  - a structurally independent second implementation;
  - the nearest trap at 1.5x the bound or more;
  - a difficulty explanation that says who does the work;
  - the load-bearing document named by absolute path in the instruction;
  - no narration.

## impeller-shrink-fits official difficulty run (Nov 9): 8 of 8 solved, rejected as too easy
- Every trial found all 12 layers in 14-28 minutes, including those meant to be subtle:
  - the rotor steel test;
  - the mill value in a certificate note;
  - the micrometer error in an inspection-report table;
  - S4's spin speed in one table column;
  - the S2 recoat in the log.
- Frontier agents read every file in full and reconcile every record. A fact that is stated anywhere (a note, a
  column, a log line) is not a trap, however small.
- Narrow windows don't help either. Agents placed bores to within micrometres; one passed with an S4 stress margin
  of +0.00004 (relative).
- Local xhigh 3/3 predicted this correctly. Treat local 3/3 as "too easy"; don't ship on the hope that official
  runs are weaker.
- **What is left to try:** layers that need inference rather than reading.
  - A fault visible only in raw data: a drifting sensor, swapped tags, an instrument offset that must be estimated
    from repeated readings of a standard.
  - A quantity that must be identified from noisy measurements, where the natural model is biased.
  - Conflicts no record resolves, where only physics or a consistency check settles which source is right.

## What does not open the effort gap (Nov 2026, skid-noise-guarantee and recip-cylinder-limits)
Two tasks in a row failed the easiness gate with low effort solving 3/3, in five and two rounds respectively.
Both were of the shape **reduce supplied records by a fully documented method to a computed quantity**. What was
tried and did not help:
- More records, more machines, more positions, more work orders. Scaling the data scales the reading, not the
  difficulty.
- More trap layers. recip-cylinder-limits carries sixteen; every one of them is load-bearing by route_study, and
  low effort found all sixteen.
- A test budget smaller than the number of unknowns, with escapes hidden in records. Low effort planned the
  allowance correctly in 6 of 6 runs, including both deductions.
- Extra computed steps in place of handed-over numbers (a pocket given as a volume to convert, a shop ticket given
  as two weights to difference, a liner history to pick by date, an exponent that must be iterated with the
  discharge temperature). None of these changed a single probe's answer.

What the probes' own reports say is that when the standard states the method in full and every fact is in a
record, the work is bounded: read the records, implement the formulas, scan. The model does that reliably at low
effort however many layers are stacked on it.

A third design was then tried: the same subject with the **duty itself unsolved** - two interstage pressures
settling on a molar balance, a speed set by a contract flow, a range edge the solver has to find, and every
cylinder coupled to every other through the machine. Low effort solved that 3/3 as well, each probe in minutes,
each validating its own duty model against the plant's measured pressures and speed before reporting. Modelling
depth is not the lever either: a two-equation nonlinear solve is no harder for the model than the fixed point it
already did, and both have to be written down in the standard for the task to be fair.

Three corollaries for the next task:
- **Precision is not the lever.** I had thought impeller-shrink-fits was hard because its answer was a 7-12 um
  window built from a dozen micron-scale contributions. The official run above settles that: agents placed bores
  to within micrometres and one passed with a relative margin of 0.00004. A tight band makes a task unforgiving,
  not hard.
- **Coupling is not the lever either.** Making the duty itself the unknown, so that no cylinder can be worked out
  on its own, cost me a day and moved nothing.
- **Signposting is worth removing anyway,** but do not expect it to move the gate. It was worth about nothing here.

Which leaves the three things listed above as untried: inference from raw data, identification where the natural
model is biased, and conflicts that only physics resolves. Two more of the same kind, from the twelve probe
reports:
- **the agent could always check itself.** Every probe validated its own answer before reporting - against a
  measured value in the records, against a stated figure in the standard, or by re-deriving a few cylinders with
  separate code - and every one of those checks passed. A task where the answer cannot be confirmed from the
  inputs would make effort buy something;
- **the measurement plan was always recoverable.** A budget smaller than the number of unknowns is not a squeeze
  if every allocation still leaves the answer obtainable. A plan that leaves the system under-determined - the
  wrong set of measurements and two of six unknowns are simply not identifiable - cannot be fixed by working
  harder afterwards.

## Fairness note
Removing a signpost is not the same as removing a fact. The register must still record that a weight was not
taken, or the reading cannot fairly be required; what it must not do is tell the solver which reading to buy.

## Fairness note from the coupled design
The sloppy clause that cost round 3a is worth remembering. The standard said the speed follows the molar flow of
the first stage; the definition used the flow the last stage delivers, which is what the export meter reads. All
three probes followed the clause, got a speed 1.8 per cent from the record's measured value, said so, and carried
on. Two lessons:
- put a measured value of every solved quantity in the records (here the interstage pressures and the speed).
  It costs nothing in difficulty - the answers are at other field pressures - and it is what lets a solver tell a
  misreading from a modelling error. It is also what caught my own bug;
- any clause that names a derived quantity ("the flow", "the load", "the temperature") has to say *which* one, at
  which point in the machine. A quantity that a solver can reasonably read two ways is a defect, not a layer.

## The measurement-allocation lever is already taken (Nov 10)
I designed and verified a sixth-of-a-bank identifiability task - six air-cooler bays, five unknown fouling
resistances, four survey points, where the plant's own mixed return temperature and common pressure drop can carry
one unmeasured bay and no more, so any wasted point leaves two that nothing recovers. The numbers came out well: a
good plan recovered the fouling to 2.9-6.3 per cent and the flows to 0.82-1.29 per cent against bands of 10 and 3,
and every wasted point put a flow four to five times outside its band.

Then cooler-fouling-assessment landed, which is the same task: cooler fouling, a fouling resistance per unit in
fouling.csv, and a slot allocation where two of the hundred and twenty ways to spend three slots pass. Backed mine
out unbuilt.

The lesson for choosing the next one: **"a measurement budget that a bad plan cannot recover from" is now covered**,
and covered better than I had it. Of the three things listed above as untried, that leaves two, and they are both
about inference from data already in hand rather than about what to go and measure:
- a fault visible only in the raw data (a drifting instrument, swapped tags, an offset estimated from repeats);
- a quantity to be identified where the natural estimator is biased, so care alone does not get it right.
To which the twelve probe reports add a third: an answer the solver cannot confirm from its own inputs.

## What the untried levers were actually worth (Nov 10, relief-valve-adequacy)

A task built deliberately on three of the levers above: a categorical deliverable (which of six contingencies
governs each of nine relief valves, plus the area it needs and whether the valve is adequate), two quantities
identified from records rather than read, and twenty-two layers. Twelve local probe rounds, nine at low effort and
three at xhigh, each graded with the task's own grader.

Result: low effort 1 of 6 solved on clean records, xhigh 1 of 3. Both gates met, which is the first design since
superheater-tube-life to meet them. But **what separates a pass from a failure is a single layer**, and the lever
it belongs to is narrower than the list above suggests.

- **An answer the solver cannot confirm from its inputs** was worth little. Nothing in the records states any
  valve's governing contingency or finding, yet a run that gets the physics right gets the name right as a
  by-product. Worse, the runs found their own anchor: most of them reproduced the superseded 2019 relief study
  from its own stated basis and used the match to validate their implementation. A dated wrong answer is a
  self-check, not just a decoy - which is worth knowing before putting one in a task again.
- **A quantity whose natural estimator is biased** was worth nothing as stated. The valves' data sheet
  coefficients are the biased estimator and the plant's trends the unbiased one; every single run used the
  trends, because the standard has to tell them to for the task to be fair.
- **A fault visible only in raw data** was worth something, but only in one form. The feed meter's flow computer
  holds a density the gas no longer has; every run found that and corrected the feed. What two thirds of them
  missed is that the same meter also supplies the flow column of one control valve's trend, so the coefficient
  fitted from it is 4 per cent low. That one link is the whole difficulty of the task.

**The sharpened lever: a fact that has to be carried from one record into the use of another.** Not a hidden fact
- impeller-shrink-fits settled that a fact stated anywhere is found. A fact that is read, understood, and then
not applied in the second place it bears on. Across twelve runs this went wrong about two thirds of the time, at
low effort and at xhigh alike, which is the only behaviour yet observed that effort does not fix. Twenty-two
layers threw up exactly one such link, and by accident. A task built out of six or eight of them deliberately -
one quantity used in two places, one correction that bears on two files, one instrument feeding two derived
numbers - would have headroom instead of riding on one.

**And the structural tension behind all of this.** Every layer had to be derivable from the agent's files to be
fair, which meant writing it down, and writing it down is what made it findable. The first probe round of
relief-valve-adequacy found three defects, and all three were places where a layer was unfair because something
had *not* been written down: a stream named inconsistently between two documents, the latest analysis dated after
the assessment, a shop record out of step with the sealed definition. Fixing each removed a failure and made the
task easier. Expect that trade on every future design: the honest ceiling on difficulty for a records-reduction
task is set by what fairness obliges you to state.

## flare-load-study, Nov 10-11: twelve more runs, and the ceiling confirmed

The reshape of relief-valve-adequacy was built records-only first, keeping every layer above and adding four
more: a header walked segment by segment from the tip outwards with each length carrying its own mixture, a
tie-in moved after the isometrics were issued, a SIL floor that bites on a live cause, and a second valve reset
in situ. Then three low-effort probe runs **solved all six rows exactly**, and three xhigh runs failed only on
plain slips. That is the ceiling in the paragraph above, met head on: the new layers were all written down, so
all three low runs found all four of them.

So the lever list gains the one that worked, and loses an illusion.

**What did not work: more layers.** Four layers were added and the low-effort pass rate did not move. A layer
that is written down costs a careful reader one paragraph of attention. Adding paragraphs does not add
difficulty; it adds length.

**What did work: a measurement the records cannot supply.** A booking of two field tests from six, ordered
before any result is known, with two quantities that appear in no record at all - the loss coefficient of a tip
replaced by a vendor who supplied no data, and the shutoff head of a pump whose rotating element was renewed
and not tested. Low effort went from 3 of 3 solved to 1 of 3. Information the agent does not have is the only
thing yet seen that effort cannot substitute for.

**But not for the reason expected, and this is the part to remember.** Every one of the six runs ordered the
right two tests, and each said in its own words why the other four were pointless - that E-406's
coefficient-area only serves a cause the SIS credit sets aside, that no device admits a cause PV-4031 could
create, that a loss of cooling is total however capable the condenser, that the shop record already gives
PSV-404's set pressure. The choice was not hard. What the booking actually did was **lengthen the chain**: two
more quantities that have to be obtained and used correctly, and the low-effort runs spent their care there and
dropped it elsewhere - one credited an instrumented function it should not have, one missed the feed meter
correction it would probably have caught otherwise.

Two consequences for the next build:

- **A budget raises difficulty by adding required steps, not by making the choice of measurement hard.** Budget
  it that way deliberately: size the booking so the orders are work, and do not count on the decoys to
  discriminate.
- **To make the choice itself hard, the useless test has to be genuinely tempting** - its quantity must appear
  to enter the answer until a specific piece of reasoning rules it out, and that reasoning must be one the agent
  would plausibly skip. All four decoys here were ruled out by reasoning the agent had already done for another
  part of the study, so they cost nothing to reject. A decoy whose uselessness turns on a layer *not* otherwise
  needed would be a real test.

**The profile that resulted is the one to aim for anyway**: 1 of 3 at low effort, 3 of 3 at xhigh. The task
rewards care and correct reasoning rather than luck, and the two xhigh reports read like competent engineering
work. A task that no run solves is not better calibrated, it is just unsolved.

*Superseded. The bar as of Nov 13 is 0 of 3 at low effort and 0 to 5 of 8 at xhigh, so this profile is now on
the wrong side of both probes, and 0 of 8 is inside the band (`docs/playbook.md`, Calibration targets).*

## The proxy was wrong (Nov 11)

flare-load-study went to screening with local probes reading 1 of 3 at low effort. The screen solved it **3 of 3,
median about two minutes**, and rejected it: more than zero solves is below the bar.

So the local harness is not a calibration instrument, and the gap is not small. Two differences stand out:

- **Time.** The probe runs took 270 to 390 seconds; the screening runs took 123 to 141. The screen's attempts
  were roughly twice as fast and still correct, which means the probes were not merely unlucky - they were
  working harder on an easier problem than the screen found it to be.
- **What a failure meant.** The two probe failures were a wrongly credited instrumented function and a skipped
  meter correction, both one-line slips. None of the screening runs made either. Treating two slips as evidence
  of difficulty was the error: a slip rate is not a difficulty measure, and three runs cannot distinguish them.

How to screen from now on:

- **Any low-effort solve is a failure.** The bar is zero solves, so the decision rule is not "1 of 3" but "0 of
  3", and with three runs even that is weak evidence of clearing it.
- **Read the clock, not just the verdict.** A run that solves in two minutes has found a short path. If a probe
  solves quickly, the task is far below the bar whatever the pass count says.
- **Ask what the failures were.** If the failing runs failed on slips rather than on the task's core, the task
  has no difficulty of its own and the pass count is noise. Record the failure reason beside the count.
- **Distrust a result that needs the probes to be weaker than the screen.** Where a task passes calibration only
  because two runs blundered, it has not passed.

## Three iterations on flare-load-study, and the only lever that ever separated a run (Nov 11)

After the screen rejected it, three rounds of design went in, each measured with three low-effort probes.

| What was added | Low probes that solved it | What the failures failed on |
|---|---|---|
| Segmented header, relocated tie-in, SIL floor | 3 of 3 | nothing - all three got everything |
| Coupled system (a conventional device opens at set plus what stands at its own tie-in) and a tip re-rating duty with an outer search | 1 of 3 | the feed meter |
| Two silent two-state traps: valve trends split by the retrim the log records, reboiler record split by the steam trap renewal | 1 of 3 | the feed meter |

Every run implemented the coupled sweep correctly. Every run found both two-state traps, cut both records at the
right day, and said so. Every run got the re-rating bore and the binding device right. Across nine probe runs the
only thing that ever separated one from another was the **feed meter's stale configured density** - and the two
runs that failed in each later round failed on exactly that.

**The distinction that matters is not hard against easy, it is stated against unstated.** Every layer these runs
found is a *principle written in the standard*: section 1 says only the part of a record describing the item's
present condition may be used, section 4.1 says a conventional device's opening pressure includes what stands at
its outlet, section 9 sets the re-rating duty. Write the principle down, however subtle its consequences, and a
capable run applies it. The meter is different: nothing in the standard mentions it. The instrument schedule
records a fixed relative density, the dated analyses record the gas, and the solver has to know unprompted that
mass through an orifice goes as the square root of density and that one of those two numbers has moved. That is
the only kind of layer that has ever failed a run at any effort.

So the arithmetic for calibration is:

- one unstated correction at about a one-in-three failure rate gives a two-in-three chance a run solves the
  task, which is 3-of-3 or 2-of-3 at screening, which is a reject;
- four independent ones at the same rate give (2/3)^4 = 20 per cent per run, so 0 of 3 most of the time.

**Design rule: count the unstated corrections, not the layers.** A task needs three or four facts that sit in a
record with no rule pointing at them, each needing textbook instrument or equipment physics to notice, each
worth more than the band on a graded value, and each independent of the others so the failures do not correlate.
Layers that the standard states are what make a task *fair* and what make it long; they are not what makes it
hard. This is a sharper statement of the Nov 10 lesson about carrying a fact from one record into another: what
mattered there was not the carrying, it was that no rule asked for it.

## The probe harness broke the rig, and two of three probes patched it rather than stopping

`tools/mkprobe.sh` wrote the sandbox seed file as `{"seed": N}`. The shipped file carries two keys, `seed` and
`test_seed`, and `lab.py` reads `test_seed`, so every sandbox the tool built had a laboratory program that died
on a `KeyError` at the first order. The shipped bundle was never affected; only the probe sandboxes were.

What the three probes did with it is the part worth keeping:

- two of them edited the sealed configuration to add the missing key and carried on, one of them keeping a
  backup and stating that it had not read the value;
- the third reported the rig as broken, closed both gaps from the records instead, used the superseded tip
  coefficient that the standard forbids, and failed every pressure.

Three lessons. The first is mine: a probe sandbox has to be verified before probes are launched into it, and the
check is one command (`./fieldtest` with no argument, which prints its usage, then one real order). The second is
about the measurement: a round run on a broken rig measures nothing about difficulty, and the run that honoured
the breakage scored worst of the three, so a broken harness does not even bias the result in the safe direction.
The third is about the environment the task ships: an agent that meets a broken rig will try to repair it, and in
a sandbox where the sealed files are writable by the agent it succeeds. The container closes that off (the sealed
definition and state are crew-owned and 700, and preflight checks the image does it), and the probe builder
should match the container rather than being more permissive than it.

## Round 4: two more unstated corrections, and they changed nothing

Round 4 added the two corrections the arithmetic above called for, both of the prescribed shape — a fact in a
record with no rule pointing at it, needing textbook equipment physics, worth more than the band:

| correction | what the record says | what it is worth if missed |
|---|---|---|
| E-403's condensate leaves sub-cooled | the exchanger data gives a condensate outlet temperature of 128 C and a specific heat; the steam gives up its latent heat *and* that sub-cooling | coefficient-area 13.1 per cent low, 21.7 per cent on the cooling pressure, 3 of 7 parts |
| V-405's level transmitter is mis-ranged | the schedule says LT-4075 is ranged for specific gravity 0.500; the data book gives the drum's liquid as 0.447, and says its level is what the transmitter indicates | wetted area 8.4 per cent low, 5.7 per cent on fire zone C's pressure, 1 of 7 parts |

Three low-effort probes on a working rig scored **7 of 7, 4 of 7, 4 of 7**. All three found both new corrections
and named them in their reports. The solve rate did not move: it was 1 of 3 in round 2, 1 of 3 in round 3, and
1 of 3 now.

**The premise was wrong.** Counting unstated corrections does not predict difficulty. All three of these probes
walk every record and cross-reference it against every other, so a fact that is *published* gets found however
little the standard points at it. What actually separated the runs was the same single step as in every previous
round: FE-4011's stale configured density, missed by two of the three.

Why that one and not the others is the useful part. The two failing runs did not merely skip the correction —
both of them *claimed a cross-check they had not run*, reporting that the pre-overhaul trend rows reproduced the
data sheet and that this confirmed their reading. The numbers say the opposite:

| PV-4001 from the trend | as FE-4011 indicates | with the density corrected | data sheet |
|---|---|---|---|
| the 24 rows before the re-trim | 61.70 | 64.13 | 64.00 |
| the 48 rows after it | 52.84 | 54.92 | - |

The check is there, it is cheap, and it points at the correction. The run that ran it solved the task; the two
that asserted it without running it failed. So the trap does not work because the physics is obscure — every
probe knows that orifice mass flow goes as the square root of density. It works because the wrong reading has a
*tempting cross-check that nobody runs*, and a quick agent reports the check as passed because it expects it to.

**Revised design rule: build traps where a false confirmation is available.** A hidden fact is found by a
systematic reader. What defeats a quick reader is a wrong answer that looks already validated. The ingredients
are a plausible reference value (the data sheet), a block of record that appears to agree with the wrong reading
(the pre-work rows, which agree to 3.6 per cent — close enough to pass an eyeball, far enough to fail the band),
and no log entry pointing at the discrepancy. Count traps of that shape, not unstated corrections in general.

## The probe model is part of the instrument: a controlled comparison (bore-form-acceptance, Nov 11)

Local probes run on whatever model the authoring session is on, and that changed part way through a day. The
same task then read completely differently, and for a while the change was mistaken for the effect of a
redesign. A controlled comparison separated the two:

| Bundle | Probe model | Low-effort probes |
|---|---|---|
| bore-form 20261111 (round 4) | the session's earlier model | 0 of 3, each 7 of 14 |
| bore-form 20261111d (round 5, same records) | the session's current, stronger model | solved, 5 minutes |
| bore-form round 6 (branch bore-form-round6) | current model | 3 of 3 solved, 3 to 8 minutes |
| bore-form round 6 | earlier model, forced with the Agent tool's `model` argument | 0 of 2, each 7 of 14 |

The second probe on 20261111d also solved it, so that row is 2 of 2. At xhigh the current model solved round 6
3 of 3, in about 40 minutes each, by the same route as its low-effort runs. Effort bought nothing on this
task: the low-effort runs were already complete.

So "0 of 3 with a seven-feature gap" was a statement about the weaker model. On the stronger one the same bundle
is solved at low effort in minutes. The official screen had already said as much: it solved round 2 once in
three, in three minutes, when the local probes of the day read 0 of 3.

What the stronger model did at low effort, unprompted and in under five minutes, on a task with none of it
stated: found the tester's error motion from phase agreement across records, split it at a maintenance date in
the log, noticed that setup twins disagreed in amplitude at one order, solved the machine's vector from the
pairs with the clamping angle fitted from the other orders, cross-checked it on three pairs, and reported the
weakest point of its own estimate. Every one of those is an unstated correction with a signature in the data.
A signature in the data is enough. This agrees with the rule above and sharpens it: an unstated correction
that the records betray is found; only one that leaves the records self-consistent, or that has to be bought
before it can be seen, is not.

Rules taken from this:
- **Record the model with every probe result**, in the design note and in the README's calibration line. A count
  without the model is not a measurement.
- **Calibrate on the strongest model available**, and when the session's model changes, re-run the last
  round's probes before believing any comparison across the change.
- **Use the weaker model only as a sanity check** that the layers bind at all. It says nothing about the gate.
- When a redesign and a model change coincide, run the two-by-two (old and new bundle, old and new model)
  before drawing any conclusion. It costs four probes and about eight minutes.

## flare-load-study official easiness screen, Nov 11 (20261111e): 3 of 3 in three minutes, and the instrument finally matched

The official screen (claude-opus-5-5, low effort, allowed 0 solves) solved the bundle 3 of 3 in 2m39s to 3m06s,
each on its first numerical run, with a worst departure of 0.34 per cent against the 1 per cent band. All eight
quality checks passed on every trial, so the bundle is clean; it is only easy. The trial notes list what each
run did unprompted: the post-maintenance windows, the meter and level corrections, the condensate sub-cooling,
the SIF credit, the fire geometry and insulation, the segmented header, the coupled sweep, the re-converged
sizing, and the right two tests in the one booking. That is every layer in the task, including the carried
fact (FE-4011's density applied to PV-4001's trend) that had been the only step ever to separate a local run.

Local probes of the same bundle, with the model forced to the screen's (`model: "opus"`, effort low): 7 of 7 and
7 of 7 in about three minutes each; the third did not finish and left no study, so the count is 2 of 2 completed runs. The local
probes that had read 1 of 3 on rounds 2, 3 and 4 were on the session's earlier, weaker model. **With the model
matched, the local probe reproduces the official screen.** Every local count in the flare sections above is a
statement about the weaker model and nothing else.

What this settles, on top of the skid-noise, recip-cylinder and impeller sections:

- **The carried fact is not a lever against this model either.** It was the one behaviour "effort does not
  fix"; a stronger model fixes it. It joins layers, coupling, precision, budgets with flagged gaps and unstated
  corrections on the list of things that were measured and are worth nothing at this gate.
- **The shape is the problem, not the content.** "Reduce supplied records by a documented method to a computed
  quantity" is read in one pass and written in one script. Fifteen layers and one script took 500k input tokens
  and 18k output tokens. Nothing that fairness obliges the standard to state survives that reading.
- **Five rounds on this task went into levers this file already recorded as dead**, because each round was
  checked against a probe that could not see the gate. The process failure is the instrument, and it is now
  fixed: probes run with `model: "opus"` at low effort, three of them, before anything is called calibrated.
- **The bar has moved.** The playbook's target of at most 1 of 3 at low effort was written when 1 of 3 passed.
  This screen states allowed 0. A design is not worth building out until a first rough version of its core
  already defeats three matched probes.

What a matched probe has not yet been seen to do in one pass, and so what the next design should be built
around: get right something that cannot be had by reading and computing once. Candidates, none of them measured
yet on the matched model: a result that has to be earned by iterating against a simulator or plant that answers
back (the controller tasks); a program that must stay right on hidden cases over a documented envelope
(turbine-tool-repair went 0 of 8 and was accepted); a measurement plan that a wrong first choice leaves
unrecoverable. Measure the core of any of them on three matched probes first, before the evidence harness, the
second implementation or the README exist.

### Correction to the section above (Alex, Nov 11): the placement of the traps, not the shape

"The shape is the problem" overreaches. Set flare-load-study beside bore-form-acceptance and the difference is
where the traps sat, not the domain or the deliverable:

| | flare-load-study, every round | bore-form, the layer that worked |
|---|---|---|
| where the fact lives | a cell of text in one record: "fixed relative density 0.780", "ranged for specific gravity 0.500", a condensate outlet column, a dated log line | in no document; only in nine records taken together |
| what the first reading sees | an odd cell, named | nothing |
| the obvious check on the wrong answer | fails (pre-overhaul rows miss the data sheet by 3.6 per cent) | passes (the plant's own report carries the same error) |
| the obvious diagnostic | finds it | pooled over two machine states, comes back clean |

"Unstated in the standard" was never the test. A model that reads every cell treats a stated oddity as a
signpost whichever file it is in. The test for a trap is:

1. no cell of text names it; it exists only in numbers, across records the documented method never combines;
2. the natural route is self-consistent, and the checks a careful solver runs on it (the plant's own report, a
   closure rule, a peer ratio, a step search) pass;
3. the first-order diagnostic that would expose it returns a clean bill, so a solver who looks is reassured;
4. it is still fair: derivable from the records together by a physical argument, with at most an oblique note
   that records a circumstance without naming the error or its size.

## A bare kind-A core, killed in an hour (shaft alignment, Nov 11)

First use of the rule "probe the bare core on the screen's model before building anything". The core is in
`cores/shaft-alignment-v0/` with its result. 36 trains, five laser visits, nine open items that five visits
cover only through two overlaps and one free derivation, three salient machines the records already settle;
4 of 376,992 bookings pass. Three opus low-effort probes made the same passing booking in about 80 seconds
each and aligned 36 of 36.

- **A zero-slack budget is not kind A by itself.** When the procedure states what voids a record and what
  carries from one unit to its class, the open items are a list and the booking is a count, however tight.
- **Overlaps and a free derivation add nothing.** All three runs found both overlaps and the twice-read train.
- **Salient decoys drew no visit.**
- What remains untested is the part of hvac this did not have: classes that no document declares.
- The cost was about an hour of building and four minutes of probes, against the five rounds flare took.

## The first core with an effort gradient on the screen's model (shaft alignment v2, Nov 11)

Three bare cores in one evening, each probed on `model: "opus"`: `cores/shaft-alignment-v0`, `-v1`, `-v2`,
each with a RESULT.md.

| core | what carries it | low | xhigh |
|---|---|---|---|
| v0 | zero-slack budget, classes and voiding rules stated in the procedure | 3 of 3 solved, 80 s | - |
| v1 | nothing declared; the budget exactly equals the needs a careful count finds | 1 of 3 | - |
| v2 | a careful count comes one short of the budget; the last need is a ratio in an old survey | 1 of 6 | 2 of 3 |

What the three together say:

- **Declared or not made no difference to finding the classes.** v1's runs saw the stale survey, found the
  fraction law and sorted the pumps without being told any of it.
- **A salient, settled machine draws a visit only when the run thinks it has one to spare.** v0: 9 needs for 5
  visits, no run looked at the compressors. v1: 2 of 3 bought one before counting. v2: 5 of 6 at low effort and
  1 of 3 at xhigh. The perceived budget has to look comfortable.
- **The spare has to be the one visit the task needs,** and what it is needed for must not show until the
  records are tested against themselves. Then a run that counts first is also caught, which v1 could not do.
- **The false confirmation matters.** The wasted visit returned the maker's figure exactly and matched the dial
  sheet to 0.001 mm; every run that bought it reported its method confirmed.
- Each bare round cost about twenty minutes to build and two to probe at low effort.

## Shaft alignment, six bare cores: what moved the low-effort rate, and what moved xhigh (Nov 11)

`cores/shaft-alignment-v6/RESULT.md` has the table. About four hours in all, 63 probes, nothing built out.

- **Low effort is beaten by a budget only when the run believes it has a visit to spare.** A count that comes
  out one short of the budget, with a salient settled machine to spend the spare on, caught 5 of 6 at low
  effort where a count that fills the budget caught 2 of 3.
- **The remaining low-effort passes were bought with information.** Ordering one visit at a time let a run
  see three reports before choosing the sixth train. One order for the whole programme removed every one of
  them: 3 of 12 became 0 of 6.
- **xhigh needs a label that raises the question, though not one that answers it.** Two model names listed
  alike made careful runs compare the models' old behaviour before ordering (3 of 6, then 1 of 3 with a single
  order). With one model name nobody asked, at any effort (0 of 15). Hide the answer in the numbers, and leave
  a reason to look at them.
- **A decoy must have no honest justification.** An unstated sign convention on the decoy's own record gave
  careful runs a real reason to check it. Stating it in the procedure with the word "put in the sense of" read
  as "converted, so suspect" and drew a visit; naming the direction in the column header did not.
- **A second decoy catches what the first misses.** The pump whose grout was repaired after its sheet drew
  three visits from runs that had declined the compressor.

## Shaft alignment v7: a sentence of reassurance was holding xhigh down (Nov 11)

`cores/shaft-alignment-v7/RESULT.md`. v7 is v6 less two sentences in the close-out that said the lagging and
the blanking were done the same way on every pump. Twelve probes on `model: "opus"`: low 1 of 6, xhigh 3 of 6,
against 1 of 12 and 1 of 6 on v6.

- **A sentence that answers the uniformity question is a lever on xhigh and hardly one on low.** With it, five
  of six xhigh runs took the classes as listed and spent the spare on a compressor. Without it, one of six did,
  and three compared the models' old ratios before ordering and passed. Low effort named a compressor four
  times in six either way.
- **Taking reassurance away spreads the spare; it does not aim it.** Three runs spent it on a second lagged
  pump, the class where the two models really are alike, and then had nothing for the jacketed one.
- **An unstated physical assumption is a trap nobody wrote.** Two runs took a drained jacket for a plain
  pedestal and visited no jacketed pump: ten trains out by 0.11 to 0.52 mm.
- **Six runs a side is a diagnostic, not a rate.** 3 of 6 against 1 of 6 is not separated by the count. The
  evidence is the change in where the sixth visit went. The low-effort rate of v7 needs six more runs before
  anything is built on it.

## shaft-alignment-moves, the bundle built on v7 (Nov 11)

`tasks/shaft-alignment-moves`, zip `shaft-alignment-moves-20261111c.zip`; `docs/design-note-shaft-alignment.md`.
The agent's records are byte for byte v7's and the statement is v7's brief, so the bare-core rates (low 1 of 6,
xhigh 3 of 6) are the only local estimate; the bundle itself was not probed.

What building it showed that the bare rounds had not:
- **150 of 1947792 programmes leave every train aligned**, the ones that measure all six unknowns. The best
  any other programme can do is 35 of 36, and no way of filling in an unmeasured group from the records
  rescues it (`visit_study.txt`).
- **Two things the core carried are not graded layers.** Taking the wrong kit moves the sag by at most
  0.03 mm on these sheets, and taking 25 C for every sheet's ambient leaves 0.0454 mm. Both are inside the
  acceptance. They are reported as absorbed, not claimed as difficulty.
- **The verifier applies the moves to the sealed unit** and measures what is left; there is no reference
  answer to compare with, so any sound method passes by construction (seven variations and a second
  solution, 21 seeds).
- Harness similarity after two rewrites, difflib ratio against the nearest bundle: agent image 0.386, verifier
  image 0.346, reward script 0.479, pytest entry 0.389, instruction 0.438.

## Journal bearing, four bare cores of a timed program on shifted hidden data (Nov 12)

`cores/journal-bearing-v0` to `-v3`, each with a RESULT.md. Built to the Nov 11 ask
(`docs/afterquery-asks-2026-11-11.md`): a program re-run on hidden cases under a per-run limit, hidden data
shifted on purpose. 24 probes on `model: "opus"`, 23 graded.

| core | what was meant to carry the difficulty | low | xhigh |
|---|---|---|---|
| v0 | regimes the examples do not show, all inside the standard's stated scope; 60 s for 600 points | 3 of 3 solved | 3 of 3 |
| v1 | plant records with sound examples, and one supply RTD stuck with nothing to witness it | 1 of 3 | 2 of 2 |
| v2 | v1 plus RTDs reading 4 to 5 K out, with a drain RTD as the only witness | 3 of 3 | 3 of 3 |
| v3 | v2 plus hourly records of 30 500 points under 30 s | 2 of 3 | 2 of 3 |

What each one settled:
- **A stated scope is a test plan (v0).** Each run generated 30 to 90 cases of its own across the scope,
  checked them against finer grids and timed them. A shifted regime the documents describe is not a shift.
- **Record semantics defined in a format document are implemented correctly with nothing to check against
  (v1 to v3, every run).** Diametral against radial, a grind before or after a fit, the other bearing's jobs,
  the oil charge by date: no run got one wrong. The weld-preheat pattern does not hold on this model.
- **A column with no stated use is a signpost (v2).** Giving the witness made the fault easier than leaving it
  to a guess.
- **A fault with no witness is a guess (v1).** One low run in three guessed "repeats while its partner moves".
  It separates runs by luck of first idea, which is neither wide nor fair.
- **A time limit the obvious method misses is an instruction to find the better method (v3).** All six found
  the tabulation; the two failures were interpolation slips in different places.

**The general point.** In this shape the solver writes the whole method and can test it on cases of its own
making for as long as it likes. Anything determinate from the documents and the visible data is found, at low
effort, in 20 to 90 minutes. What stopped low effort on the alignment task was different in kind: a decision
that cannot be tested before it is spent. A program task has no such decision unless the program itself has to
spend something on the hidden case.

## Timed programs on shifted hidden data: sprinkler-demand v0 and v1 (Nov 12)
Two bare cores on one subject (a wet-pipe sprinkler system's demand), both solved at low effort. Details in
`cores/sprinkler-demand-v0/RESULT.md` and `cores/sprinkler-demand-v1/RESULT.md`.
- **A decision made during the run is not difficulty.** v0 gave the program one field test to choose. Nine
  minutes in, all three low drafts were choosing it by Fisher information.
- **Unlabelled faults in a redundant record are not difficulty.** v1 hid five kinds in the readings (a wrong
  registered C, a valve off its seat, swapped port tags, a mis-entered flow, a gauge zero error), four of them
  moving no visible result. Low effort found all five in five to eight minutes and one run was accepted 8 of 8.
  Its method: static offsets, a robust fit of every parameter, tags reassigned by optimal assignment, misfit
  runs dropped.
- **Low effort tests the shift itself.** With a forward model in hand it corrupts the examples with every
  fault it has seen, at larger values. A hidden shift the agent's own simulator can produce is not a shift.
- **A size that decides must be visible.** Hidden systems three to four times the size of any example put one
  run over the time limit. That is a design fault under the Nov 12 tips, not difficulty.
- **The one thing that bit:** a fault sitting on the only readings that carry the information, so that it has
  to be undone and cannot be discarded. One hidden system of eight had it; two of three low runs handled it.


## Journal bearing v4: the program has to spend a budget, and the alignment mechanism holds (Nov 12)

`cores/journal-bearing-v4/RESULT.md`. A site package of 14 to 24 bearings on shared oil systems; the program
places one laboratory order while it runs; in five of six hidden sites one listed system is two charges, visible
only in earlier analyses, and the allowance is the listed count plus one. Six probes on `model: "opus"`:
low 0 of 3, xhigh 0 of 3, all six failing the same five sites by 112 to 482 points each.

- **What v0 to v3 lacked is a decision the solver cannot test.** Its own test packages carry its own reading of
  the register, so the wrong program passes everything it can run, including both examples.
- **A budget one above the legible count is not noticed as a question.** Four programs left the extra sample
  unused or spent it where it told them nothing.
- **Zero at xhigh is inside the Nov 11 ask (0 to 5 of 8) and outside the older one (1 to 7).** Three runs wrote a
  check for a machine registered on the wrong system, so the idea is in reach; none generalised it.


## Journal bearing v5: the v4 condition put into the visible data, not yet probed (Nov 12)

`cores/journal-bearing-v5/RESULT.md`, bundle `tasks/journal-bearing-survey`. v4 had no visible instance of
the console that is two charges, against the first Nov 12 tip, and every probe failed alike, which is the
tips' warning sign. v5 adds a third visible package without results that has such a console and an allowance
one above the register's count. The examples with results are unchanged.

- **v4's 0 of 6 does not carry over.** The instance changes what an attentive run can see.
- **A package without results is the only fair place for it in this format.** With results it would be a
  test the wrong program fails at once (v2: a witness with feedback is solved 3 of 3).
- **Check a core against the tips before probing it, not while building on it.** v4 was probed for six runs
  on a design the playbook already ruled out.


## Tank panel deflection v0: a model's validity limit is not a lever (Nov 13)

`cores/tank-panel-deflection-v0/RESULT.md`. A timed program on shifted hidden data: centre deflection and edge
stress of flat wall panels to a standard that states the physical situation and no method. Small-deflection
plate theory is right on both examples with results and wrong on the sheet walls of five of six hidden units
(deflection up to 4 thicknesses). The regime was in the visible data twice: a package without results, and a
drift of up to 0.5 per cent on the example results, inside the 1.5 per cent band. Three probes on
`model: "opus"` at low effort: **3 of 3 solved, in 13, 18 and 29 minutes**, worst error 0.01 to 0.08 of the band.

- **The solver did not hold the assumption the design counted on.** None of the three wrote the small-deflection
  program. Each chose the large-deflection model before running anything, from the standard's sentence that
  the edges do not move in the plane of the wall.
- **Fairness writes the giveaway.** The answer depends on the in-plane edge condition, so the standard has to
  state it; stated, it selects the model. This is the Nov 10 ceiling again, now for the choice of model and
  not only for a correction.
- **A package without results is read, at low effort, in the first minutes.** All three worked out the pending
  package's regime (a dimensionless load of 1,560 against 1.5 in the examples) before writing the solver. A
  visible instance that any physical quantity exposes is not a quiet one. journal-bearing v5's pending package
  was run by three low probes the same day and not read (0 of 3): its condition sits in a register's grouping,
  which no quantity the program computes exposes.
- **A model with nothing to check against in its own regime was implemented right three times in three.** The
  small-deflection limit and a refinement study were validation enough. All three wrote the reference's method.
- **Do not count on a canonical validity check being skipped.** Deflection against thickness, a cut-on
  frequency, a Biot number, a footprint against a width: the four other ideas proposed with this one lean on
  the same lever and were not built.
- v1 looked for a wrong answer that validates itself: a bowed panel whose symmetric equilibrium is unstable.
  The window is under 5 per cent of the load (`cores/tank-panel-deflection-v1/RESULT.md`); not built.
- Cost: about 50 minutes to build the core, 30 to probe it.

## Vent fan stall v0: a physical condition that marks a table, found by low effort in eleven minutes (Nov 13)

`cores/vent-fan-stall-v0/RESULT.md`. A timed program on shifted hidden data: airflow at every survey point of a
ventilation district with two axial fans in parallel. The catalogue characteristic has a stall dip, so over a
band of district resistance two states are stable and the log decides which one holds. Examples with results
sit clear of the band, the pending package and the hidden districts in it. No sentence says a district can
have two states. Three probes on `model: "opus"` at low effort: 3 of 3 accepted, 10.9 to 12.1 minutes, 14 to 23
tool calls. No xhigh probes were run.

- **Physics that leaves a mark in a table is read off the table.** All three named the stall dip, the two
  states and the history, and one sentence of circumstance (changes are gradual) was enough to settle how a
  state is carried. An unstated physical mechanism is not a lever on the screen's model when anything
  tabulated shows it.
- **A visible instance must cost a wrong program nothing to run.** The pending package made a plain solver
  fail to converge or return a fan on a rising limb. The journal bearing's pending console does neither. An
  instance that answers back is a test with feedback, whether or not it has results.
- **One stable state at each graded point is not enough for an example with results: it needs one root.** A
  root-finder found a stalled solution in an example whose every round has a single stable state, and the
  example's results told the run.
- **Following a log entry by entry is the default program.** When a state costs milliseconds every run
  solves all of them in order and warm, so a decider that is history is half given by the natural code.
- **A sealed truth can be checked by the probes themselves.** Three programs written three ways reproduced it
  at every point through ten changes of limb. Fair and determinate is not hard.
- The cost: about two and a half hours to a measured no, most of it the audit of the sealed record
  (16 minutes a district at 1 700 branches). Probe a core at a tenth of the size first; scale decides
  timing, not who sees the condition.

## Twin oil lines v0: a wrong equilibrium that validates itself is found too (Nov 13)

`cores/twin-oil-lines-v0/RESULT.md`. Built on what tank-panel-deflection v0 left: a trap the solver's own
checks cannot see. Two like pipes of heated fuel oil between common manifolds; the pressure drop of one pipe is
not monotonic in its flow, so the even division of the flow satisfies every balance and is, at cold sites on low
throughput, unstable. One pipe stalls, and stays stalled after the flow is raised again. The standard gives the
single pipe in full and says of the pair only that the oil divides and both pipes have the same pressure drop.
The even-division program is exact on both examples and is out on every stalled record of five of six hidden
sites (698 to 1003 a site, up to 18 K and 32 per cent). Three probes on `model: "opus"` at low effort:
**3 of 3 solved, in 7, 12 and 13.5 minutes**, with errors at the rounding of the examples.

- **A stated equation is a signpost to all of its solutions.** No probe took the even division on symmetry.
  Each solved the split, saw several roots on the package without results, and went on from there.
- **An unstated rule is supplied when it follows from the physics.** All three discarded unstable divisions,
  carried the pair's state from one hourly record to the next, and started a survey on the even division,
  each calling these its own reading that the examples do not test. Only an arbitrary rule is hidden from this
  solver, and an arbitrary rule is unfair.
- **Stability and hysteresis are not specialist knowledge to it.** The core needed both; seven minutes.
- **Two cores in one day say the same thing as the journal bearing cores:** in this shape, with every deciding
  condition somewhere in the visible data, what is determinate from the documents and the data is solved at
  low effort, whether it is a correction, the choice of model, or which of several equilibria is the real one.
  Neither core reached xhigh probes.
- **Three cores the same day fell the same way** (these two and vent-fan-stall v0, built by another session:
  a stall dip in a fan table, two stable states, the log deciding; 3 of 3 in eleven minutes). The one that
  held, journal-bearing v5 (low 0 of 3, pending package run and not read), differs in kind: its condition
  contradicts a register, and the natural program pools the evidence away and runs clean. What separates
  them is not how hard the physics is. A condition that follows from an equation or a table the solver
  works with is found; one that needs the solver to doubt a record it has no physical reason to doubt is not.
- **What has beaten this screen officially is information the solver does not have:** hvac-submittal-review
  0 of 3 and the vav and chill-bench 1 of 3 (a budget that has to cover classes nobody lists), and a fault
  absent from the visible data (turbine-tool-repair), which the Nov 12 tips now rule out.
- Cost: about 75 minutes to build, 15 to probe; the three probes used about 250k tokens.

## Rod pump v0: a contradicted record is found when the program's own fit is against the measurement that shows it (Nov 13)

`cores/rod-pump-v0/RESULT.md`. A timed program on shifted hidden data: plunger stroke, liquid and polished rod
loads of rod-pumped wells at every setting of a table, from two dynamometer cards a well, to a standard that
states the wave equation, the pump and the tubing in full. The decider was of journal-bearing v5's kind, a
record contradicted in numbers only: the well file gives an anchor depth, and in 19 hidden wells (two in the
package without results) the anchor does not hold, so the tubing stretches over its whole length and the stroke
is 6.5 to 26 per cent short. Three probes on `model: "opus"` at low effort: **1 of 3 accepted in 25 minutes, 2
of 3 right on every loose anchor** (the second lost one well to a fitted supply), the third trusted the file.
No xhigh probes were run.

- **A contradicted record holds only where nothing the program computes is compared with a measurement the
  contradiction moves.** The card is such a measurement, and fitting it is the natural way to the fluid load.
  Both runs that fitted or sloped the card found the anchors: "cards fit to 0.3 kN instead of 4 kN". In
  journal-bearing v5 the wrong program pools the analyses and never compares them with anything.
- **Audit the wrong program on the visible instance by every route, not only the reference's.** The reference
  here inverts the card and fits nothing, so its as-registered variant ran clean and looked quiet. A
  least-squares route does not. Before probing, run the wrong program the way a solver might write it and
  print what it would print: residuals by unit, convergence, bounds.
- **A sentence that has to say where a quantity ends lists the alternatives.** "The anchor where an anchor
  holds the tubing, the wellhead where none does" became two candidates a well in one program.
- **A subject whose diagnosis is a measured curve has no quiet place for a condition.** Whatever is downhole
  shows in the card; what the card cannot show, nothing else in a package shows.
- **Physics and limit were no obstacle, again.** String, pump with gas, card analysis and a batched solver in
  25 to 30 minutes at 13 to 21 s a field, against a reference of 10 to 20 s and a 45 s limit.
- **A probe that passes is a second solution for free.** Two probe programs written two ways agree with the
  sealed results within 0.62 of a band, so the sealed simulation, generator, reference and grader are sound
  and reusable.
- **Probes find gaps in the standard:** one reported that the gas law did not say absolute or gauge.
- Cost: about three and a half hours to build (sealed simulation, a reference on the string's modes after a
  kernel method failed to converge, nine fields at 40 minutes of generation), 25 to 54 minutes to probe.

## Vent fan stall v1 and v2: where a wrong program can ask, the condition is found by comparison (Nov 13)

`cores/vent-fan-stall-v1/RESULT.md`, `cores/vent-fan-stall-v2/RESULT.md`. v0's district with stall moved into
the examples, and two things the records do not say put in the pending and hidden districts: a stopping that
passes 10 to 13 m3/s against half a m3/s booked, legible only as the two gate-road quantities at its ends
failing to balance in every survey campaign; and a last bulkhead closure built between the stall point of the
district as it is and as its records have it, so only a reading of a fan says which way it went. One survey
order a run, the allowance one more a condition than the airways worked on. Small districts (121 to 165
branches), a 30 s limit against 1 to 3 s.

| core | low | xhigh |
|---|---|---|
| v1: the crew answers for the examples and the pending district | 0 of 3 | at least 2 of 3 in 41 min |
| v2: the crew answers for the examples only | 0 of 3 | 1 of 3 (28, 30 and 15 min) |

- **An oracle on the pending instance is a results table by another name.** In v1 both xhigh passes built the
  program that follows the records, ran it on the pending district and compared its end state with what the
  crew reads there now: a panel entry 10 m3/s out, a fan on the other limb. Remove the crew from the pending
  district and two of three xhigh probes stop at the same place the low probes do. The rule that a visible
  instance must offer a wrong program nothing to check against covers every channel, tools included.
- **Low effort does not ask what a spare allowance is for.** Six low probes over v1 and v2 saw that the pending
  district has two places more than it has altered airways. Three said so in their reports. None looked for a
  use. Two xhigh probes spent the spare places on a reading of the present state "as a check", found it agreed
  in the examples, and shipped a program that reads the disagreement in a hidden district and does nothing.
- **The pass came from a conservation law, unprompted.** The one xhigh pass of v2 balanced every campaign at
  the ends of every stopping before writing the solver. Nothing in the documents says a record can be wrong;
  VS-4 says what a resistance is and what a campaign measures. That is the fair route and it exists.
- **A legible need has to cost something in the examples.** Two low probes switched their survey order off and
  the examples still passed (0.71 of the band). Size the alteration so that a run without the order is out.
- **Check the reference at the shipping size before anything is frozen.** The reference's search for the
  change that turned the outcome looked back over ten large changes; ten times the log, it stopped short.

## ventilation-district-airflow, the bundle at shipping size: low 0 of 3, xhigh 1 of 3 (Nov 13)

`docs/design-note-ventilation-district.md`. Core v2 at seven times the size (806 to 955 branches, 1153 to
1322 log rows), the altered airways resized so that a run without the survey order is out of band on the
examples, a 35 s limit against a reference of 8.7 to 10.5 s.

| probe | effort | time | examples | six districts | order |
|---|---|---|---|---|---|
| A, B, C | low | 3 to 7 min | accepted | 5 of 6 out, as the `worked_on` variant | the airways worked on |
| D | xhigh | program done at 46 min | accepted | accepted, largest error 0.14 of the band | airways, the open stopping, FAN-B |
| E | xhigh | 25 min | accepted | 5 of 6 out | the airways worked on |
| F | xhigh | 33 min | accepted | 2 of 6 out (the closures that hold where the records stall) | airways, the open stopping, FAN-A as a check |

- **The core's rates carried over to the bundle unchanged**: 0 of 3 and 1 of 3 at both sizes. Size and the
  limit added nothing and took nothing away; three low-effort programs ran a district in 5 to 12 s.
- **Two of three xhigh probes balanced the campaigns at the stoppings' nodes** (one in v2), unprompted. The
  open stopping is the easier of the two conditions. The open closure is what holds: reading a fan is cheap,
  acting on a reading that contradicts the calculation is the step only the passes took.
- **A design that sits between records and truth invites a toss.** Averaging the campaigns moved F's district
  towards the real one and its four open closures split two and two.
- **A stall fold is not the peak.** With unequal blade settings a fan passes its peak against a load line
  steeper than its rising limb and sits there with no jump and no hysteresis; thirteen draws of thirteen were
  refused at one district before the cause was read off the fans' limbs at the closure. Print the state at
  the event before changing seeds.
- **Generate at the shipping size once, late, and from the bundle's own generator.** Three full generations
  were spent on changes (checksum module, alteration size, the edge test) that the small set would have shown.
- Cost: about five hours from the v2 result to a clean preflight, most of it generation (25 to 45 minutes a
  pass on two CPUs) and the regeneration check (23 minutes).

## Conveyor drive v0: a record that can wear, measured twice over in every survey, is found in two minutes (Nov 13)

`cores/conveyor-drive-v0/RESULT.md`. Multi-drive belt conveyors through a feed log; the drive register holds
each pulley's diameter as lagged, the lagging of eight hidden drives has worn 0.9 to 1.9 per cent, and with a
rated slip of 3 per cent that moves every share on the flight by 9 to 40 per cent of rated power. Built at a
tenth of shipping size. Three probes on `model: "opus"` at low effort: **3 of 3 accepted, 2.1 to 2.2 minutes,
6 to 8 tool calls**, each naming worn lagging.

- **Two conditions for a contradicted record to hold, both needed.** (1) Nothing in the documents gives the
  record a physical reason to drift: "measured when the pulley was lagged" is accurate, necessary, and was
  quoted back by all three. (2) The evidence is not joined to anything the program calibrates or computes by
  an equation the standard states. Here a survey gives belt speed, shaft speed and power, the calibration
  needs two of them, and BC-3 ties the third to them through the diameter.
- **A survey state is a full instance of the model, and low effort fits the model to it.** Two of three wrote
  one least-squares fit of the standard's equations to the campaigns, weighted by the stated accuracies, with
  the diameter free. Count the measurements in a survey against the unknowns it is for: any surplus is a test.
- **The audit named the route and I read it wrongly.** It showed the hand formulas quiet and the re-solved
  survey loud, and I took the loud route for an extra step that only xhigh takes, on the ventilation result.
  There a survey becomes a resistance by division; here it becomes a slip through the very relation the wear
  breaks. Ask what the calibration has to compute, not what the reference happens to compute.
- **Small first paid:** an hour to build, two minutes to a measured no.


## Engine indicating, five bare cores of a timed program on shifted hidden data (Nov 13)

`cores/engine-indicating-v0` to `-v4`, bundle `tasks/engine-indicating-analysis`,
`docs/design-note-engine-indicating.md`. A program reduces cylinder pressure records to an indicating
standard; in five of six hidden cells the encoder's index or the transducer's gain, or both, are not what
the package gives. Probes on `model: "opus"` (claude-opus-5-5):

| core | what changed | low | xhigh |
|---|---|---|---|
| v0 | index error; motored points in the table | 1 of 3 | |
| v1 | fired points only; an `encoder_index` entry in the package | 3 of 3 | |
| v2 | the entry removed; examples 0.02 degrees out | 1 of 3 | |
| v3 | examples exact; a second condition (gain) that passes for the first | 0 of 3 | 1 of 3 |
| v4 | v3 plus a polytropic exponent column | 0 of 6 | 3 of 6 |

- **An output row that can come out impossible is a signpost.** v0's motored rows gave positive work and a
  peak after top dead centre in the pending package. All three low runs read their own output and found it.
- **A field the calculation never uses is a signpost** (v1), as journal-bearing v2 found for a column.
- **A sound example must be exactly sound.** A tenth of a band of the condition in an example with results
  is a signature with feedback; one low run fitted it (v2).
- **With nothing pointing, low effort does not examine a package that has no results.** v3 and the finished
  bundle: 0 of 6, all "the standard as written", in 3 to 7 minutes.
- **Two conditions with one signature hold the careful runs too.** The first explanation (index) fits the
  gain cell at every point and cylinder and so confirms itself. One xhigh run in three separated them.
- **A diagnostic result column is a clean xhigh lever.** v4's exponent is constant on a sound cell and off on
  the pending ones. Low: three of six remarked on it, none got it right. xhigh: 1 of 3 became 3 of 6.
- **Runs question what "the result to the standard" means.** Three wrote that it might be the records as
  given. The standard has to say what its symbols are, in physical terms, without saying the records differ.
- **Round built-in values read as planted** (1.600 degrees, 1.0600). Use values that are not round.
- **Do not ask a probe why it checked something.** Two follow-up questions were stopped by the model's
  safeguards (`reasoning_extraction`). Read the report and the files it left.
- **An Agent call can run in the foreground whatever `run_in_background` says** and then blocks for the whole
  probe. Start probes last in a turn.
- **As in journal bearing, the time limit separated no run.** Every probe vectorised.

## Sprinkler demand v2: a record of the same kind as the program's own measurement is read at once (Nov 13)

`cores/sprinkler-demand-v2`. v0's program (it designs its one field flow test) with flow tests on file in every
package; in the pending package and six of eight hidden systems one group the register carries a C for has
aged, the tests on file show it, nothing lists it, and the examples with results have none. Low effort: 3 of
3 accepted on all eight hidden systems in 8 to 11 minutes. No xhigh probes.

- **The device of lube-oil-survey and ventilation-district-airflow is not enough by itself.** Same skeleton
  (a need the records show and do not list, one order during the run, the instance in a package without
  results), opposite result. All three probes named PN-1's feed main in their reports.
- **What differed:** the telling record here is a flow test in the format the program's own test comes back
  in, named in the package format. A program that must fit a flow test fits the ones on file as a matter of
  course, and the register's figure fails that fit by 3.6 psi in 10. Where the device held, the tell was a
  difference between quantities the program had no reason to put side by side (two machines' oil analyses,
  two gate roads' quantities).
- **Rule:** the visible instance has to be invisible to the program's routine use of the data. If reading the
  record is a step any correct program takes anyway, the condition is found at low effort.
- **A physical limit met while building:** one test with two gauges at 0.1 psi scatter cannot settle a main
  and the branch lines of a tree within 3 per cent. A core whose own reference passes on some seeds only is
  not fair; check the reference on several seeds before any probe.
- With v0 and v1 this closes sprinkler hydraulics as a subject: three cores, all found at low effort.

## Gear face load v0: a calibration with one unknown and two readings shows the condition on a package without results (Nov 13)

`cores/gear-face-load-v0`. A timed program for the load along a spur gear pair's face; the mounting
misalignment is the value that reproduces a contact pattern on file; on the pending pair and four of six
hidden pairs one gear's lead charts carry the flank names exchanged. Low effort: 2 of 3 accepted in 3.5 and
4 minutes; the third checked its fit on the examples only and failed the designed way.

- **Count the readings a calibration takes against its unknowns before building.** The pattern has two edges
  and the misalignment is one number. The misfit (3 mm against 0.25 mm on a sound pair) appears in a step
  every correct program takes, whether or not the package has results. This is the conveyor-drive lesson; I
  read it and discounted it because the instance sat in a package without results.
- **"Low effort does not examine a package without results" is true only of things the routine calculation
  does not report.** A fit reports its own misfit.
- **A condition with a short list of alternatives is repaired as soon as it is noticed.** Two gears, two
  flanks: three more fits. Prefer a condition whose repair needs a physical argument or a measurement.
- **Shapes reused across packages are a signpost.** Both solving probes noted that the pending pinion's L
  charts look like an example's R charts.
- **Check that every part of the model can decide a result.** A mesh cycle with two tooth pairs sharing load
  was built and dropped: the heaviest load is always in single pair contact.

## ventilation-district-airflow 20261113b: the fans' rule stated (Nov 13)
- After the quality rejection: three low probes, 0 of 3, each
  the `worked_on` miss on five of six districts, in 3 to 6 minutes. All three implemented the stated rule
  directly (a fan held on its falling part, crossing at the end of it) instead of finding stall in the results.
  Stating the mechanism that every probe found anyway costs nothing at the easiness gate.

## Hoist rope v0 and v1: a mirrored survey with two causes holds two careful runs in three (Nov 13)

`cores/hoist-rope-v0`, `cores/hoist-rope-v1`. A timed program for the bending damage along a crane's hoist
rope, from the movement log and the rope surveys, to a company standard. Probes on `model: "opus"`.

| core | conditions | low | xhigh |
|---|---|---|---|
| v0 | some ropes turned end for end at an unrecorded time; the next survey mirrors the one before | 0 of 3 | 3 of 3 |
| v1 | v0, and on other ropes the stations are counted from the dead end from one survey on: the same mirror, but the rope never moved | 0 of 3 | 1 of 3 |

- **One data-only condition, plain in the package without results, is found by every careful run.** v0: three
  xhigh runs of three found the mirrored survey and followed the element (27 to 43 minutes). A diameter that
  rises by half a millimetre between two surveys is seen by anyone who looks at the surveys at all.
- **Low effort does look, sometimes.** One v1 low run laid each interval's wear against its bendings as a first
  look, found both mirrors in four minutes and called both turns. On v0 it would have passed; v0's 0 of 3 was
  three draws, not a rate.
- **The second condition has to share the first one's signature and differ in its consequence, and the first
  explanation has to fit the signature exactly.** A turn and a change of the end a survey starts from give the
  same mirrored survey. The turn explains the mirror perfectly and is the textbook event, so two xhigh runs
  of three took it for both ropes and spent the rest of their time dating the turn and testing against
  synthetic packages that held turns only. This is the engine-indicating lesson (index and gain) again, in a
  different subject.
- **What separates them must be a physical argument, not a third fit.** Bendings fall where the reeving puts
  them, so after a turn the rope goes on thinning at the listed places and after a change of end at the
  mirrored ones. The one passing run and the reference both used it. The correct handling of the second
  condition is to do almost nothing, which no program arrives at by adding corrections.
- **A run validates against data it generates itself, and that data carries its own assumption.** Both failing
  xhigh runs reported hundreds of synthetic ropes within tolerance. Their generators could not contain the
  condition they had not thought of.
- **A survey must not be a function of the result.** v0's diameters were a fixed law of the damage, the same
  for every rope. All three xhigh runs fitted the law and dated the turn to a day; the last survey alone
  would have given the damage along a rope, turned or not. v1 gives every rope its own constants and every
  element its own gain.
- **Noise in the log is read as a clue.** v0's first build had movements slightly out of time order and
  sheaves stopping exactly on a station; two of three low reports dwelt on the 1 per cent this cost on the
  examples. A sound example must be exactly sound, down to the order of its rows.
- **A subagent survives an environment restart.** One xhigh probe reported 43 minutes in, after the session's
  container had restarted; its sandbox under /tmp was intact.
- As in every timed core so far, the limit separated no run.

## Twin oil lines v1 and v2: a register's bore against a surveyed division, low 0 of 6, xhigh 1 of 6 (Nov 13)

`cores/twin-oil-lines-v1`, `-v2`. v0's physics (heated fuel oil in single pipes and pairs, a pair's division
with its stall and history) with the stall moved into the examples, where v0 showed every solver finds it,
and the vent-fan-stall v2 mechanism put on top: coefficients from heat-loss surveys on file, one survey order
a run, re-covered pipes as the legible need, and two conditions the records hold in numbers only. One pipe of
a pair has lost bore to deposit (its pair's surveyed division does not fit equal pressure drop with the bores
as laid); one covering is declining (its coefficient rises campaign by campaign with no work logged).

| core | low | xhigh | what the xhigh misses were |
|---|---|---|---|
| v1: 5.1 "the bore and the length of a pipe are those of the lines register" | 0 of 3 | 0 of 3 | two runs found the narrowed pipe and kept the register bore, citing 5.1 |
| v2: 5.1 "the lines register records the bore and the length each pipe was laid with" | 0 of 3 | 1 of 3 | two runs ordered the pipe, re-derived a coefficient with the register bore |

- **The mechanism transfers.** A third subject with the same shape (a record wrong with no physical reason to
  doubt it, an in-run order that costs something in the examples, the pending instance silent) gives the same
  rates as the journal bearing and the ventilation district: low 0 of 3 with the designed miss, xhigh 1 of 3.
- **Say what a register records, never that a quantity "is" the register's.** One prescriptive sentence turned
  two correct findings into two misses in v1. That is the standard prescribing the wrong record, not difficulty,
  and it would have been read as unclear wording on review.
- **A consistency check on repeated measurements with a stated accuracy is made by every xhigh run and by no
  low run.** The declining covering: xhigh 6 of 6, low 0 of 6. Alone it separates the efforts and does not
  hold at xhigh.
- **What holds at xhigh is acting on a measurement against the register.** In v2 every xhigh run ordered the
  narrowing pipe, because a heat balance read with the wrong bore drifts too. Only the run that asked what D
  is, and solved the bore from the pair's division, was accepted. Finding the pipe is not the step; changing a
  quantity the register states is.
- **A scope defect hides in the generator's fallbacks.** v1 had 30 survey runs over Re 2000 and a generator
  that stalled on lines it could not draw laminar. v2 redraws a line until its survey rating and its records
  are in scope and asserts it.
- The limit does not bind (probe programs 1.4 to 9.6 s a site against 60). Cost: v1 low 308k and xhigh 778k
  tokens, v2 low 339k and xhigh 903k.

## Gear face load v1: a found condition the brief does not say to act on is unfair; saying so makes it found (Nov 13)

`cores/gear-face-load-v1`. v0 with the misalignment measured at assembly (no misfit anywhere) and the
exchanged flank names shown only physically: pits on the flank that carries load, the lead correction on the
working flank. As first briefed: low 0 of 3 and xhigh 0 of 3, but two xhigh runs found the condition and kept
the package's flank "as GF-4 and the package format require", asking the owner to confirm. With one sentence
added to the brief (results used unreviewed): low 1 of 3 solved in 2.5 minutes, a second noticed and deferred.

- **Read the failing runs' reports before counting a 0.** All three failing the same way meant here that the
  task never asked for the judgement it graded. The Nov 12 tip is right in this exact case.
- **A program task must say what the program does with contradictory records.** "Nobody reviews the results"
  is the neutral way, and it costs the difficulty: it is itself the prompt to examine the package.
- **Physical evidence in the visible package plus two alternatives is found at low effort as soon as the task
  says to act.** Prefer a deciding condition whose resolution is a quantity to estimate, not a choice to make.

## Engine indicating v6: stating the condition removes the difficulty (Nov 13 evening)

After the quality rejection of v5 for an unstated condition, IS-2 was given a section that names the index
and the gain, their ranges, and the compression-stroke criterion that settles them (method left open).
Low effort: 2 of 3 accepted on every hidden cell, the third out on one cell. Before stating it: 0 of 6.
`cores/engine-indicating-v6/RESULT.md`.
- **A stated identification problem with a stated criterion is not hard at low effort.** A few parameters
  fitted to a residual the documents define comes out right in ten minutes, noise included.
- **Taken with the rejection, the condition cannot be both unstated and fair.** For a task to meet the bar, the
  hard part has to remain once everything that decides a case is written down. Probe that version first.

## Header thermal fatigue v0: a measured quantity the model also predicts is a routine tell (Nov 13)

`cores/header-thermal-fatigue-v0`. A timed program for the fatigue of a steam header from its 1 s record;
on the pending header and four hidden headers the fluid thermocouple lags 28 to 110 s, and only the
outer-surface thermocouple shows it. Low effort: 3 of 3 accepted in 4 to 10 minutes.

- **Before building, list every measured quantity in the package that the program's own model also computes.**
  Each is a validation any careful program makes, and a condition that shows there is found at low effort.
  This failed twice today (sprinkler v2: flow tests on file; header v0: the outer-surface thermocouple).
- **Using the record for something else (here only the starting temperature) does not hide it.** The model
  produces the comparison whether or not the standard asks for it.
- **A one-parameter estimate with a clean signature is no barrier once the residual is seen**: one lag fitted
  all 24 events to the noise, and every probe ruled out the alternatives (thickness, diffusivity, a delay).
- The time limit separated nothing again: modal or closed-form solutions are the first thing low effort writes.

## Engine indicating v7: six stated layers, low 3 of 3 (Nov 13 night)

IS-2 issue 5 states six layers: converter-range spikes, a shared encoder index, a gain and a thermal-shock
coefficient per transducer (fitted together on a compression and an expansion stretch), misfires left out,
and the peak taken on a stated filter for knock. Each layer, left out, decides one to five hidden cells.
Low effort: 3 of 3 accepted in 10 to 21 minutes, every layer implemented as written. `cores/engine-indicating-v7/`.
- **Stated layers are not slips for this model.** "Official xhigh fails on rare coverage slips spread over
  many layers" (top of this file) was measured on older models and on layers that were partly data-only.
  When every layer is a written rule, low-effort Opus 5.5 implements all of them.
- **Stated ranges let the solver make its own answered cases.** All three built synthetic packages from the
  examples with known index, gains and shock, and tested their fits on them. A range in the standard is a
  test generator.
- **For a design to meet the bar with everything stated,** low effort must fail at something it was told
  exactly how to do. Neither v6 nor v7 found that. Subject closed by Alex, Nov 13.

## Carburizing case depth v0: an unused column plus a calibration date plus "nobody reviews" is a checklist (Nov 13)

`cores/carburizing-case-depth-v0`. A timed program for case depth over a furnace's record; the oxygen probe
drifts from an unrecorded date and only the enrichment gas shows it. Low effort: 1 of 3 accepted, a second one
load short, all three found the drift in 4 to 7 minutes.

- **Every field in a package is read, and every field the standard does not use is asked why it is there.** A
  calibration date names the instrument to doubt; a column described as the controller's response to that
  instrument is the test. Together with the brief's instruction to act, that is the whole diagnosis handed over.
- **The fairness sentence and an unused witness cannot be in the same task** without the condition being found
  at low effort: today's runs (gear v1b, header v0, carburizing v0) all read the pending package as soon as the
  brief said nobody reviews the results.
- What held elsewhere today (lube oil, ventilation, twin oil lines, hoist rope) puts the witness in data the
  program must use anyway, and the act in an order or a correction the program makes for its own reasons.

## rope-bending-damage, the bundle at shipping size: the core's wording matters as much as its data (Nov 13 night)

`tasks/rope-bending-damage`, `docs/design-note-rope-bending.md`, probe programs and reports in
`cores/hoist-rope-v1/bundle-probes`. hoist-rope v1 at shipping size: stations 1 m apart, about 90,000
movements a crane, a 4 s limit against a sweep reference of 1.2 to 1.4 s.

| documents | low | xhigh |
|---|---|---|
| the bundle's first wording | 0 of 3 | 3 of 3 |
| core v1's wording put back (shipped) | | 1 of 3 |

- **Wording added while building the bundle took xhigh from 1 of 3 to 3 of 3.** I had written the survey file
  up as "copied from the survey sheets", `station_m` as "the station as the survey sheet gives it", d as "the
  diameter of the element itself", and "An element is a piece of the rope, not a place on the crane". Every
  sentence was accurate, and each described a record as a copy or a definition as a correction. All three
  passing reports put MH-5 in those words: sheets "written from", "numbered from", "read from" the wrong end.
  With core v1's wording back, on the same data, 1 of 3.
- **Freeze the agent-visible text of a core that is at the bar.** Changing it for the bundle is a new core and
  needs probing again. A phrase that says a field is what a record "gives" invites the hypothesis that the
  record is wrong; describe what the field is meant to hold, as the core did.
- **A combination of two visible conditions held a run that had both of them right.** xhigh6 separated MH-1
  (turned) from MH-5 (surveyed from the dead end) and failed only DS-5, first surveyed from the dead end and
  later turned. The second mirror of such a rope puts the sheet back in its first order.
- **Low effort optimises unprompted.** With "within 4 seconds on 1 CPU" stated, all three low runs counted the
  bendings by running sums and a series in ln S in two to four minutes; nine probe programs ran in 0.7 to
  1.7 s. The limit stopped brute force over movements and stations (the cores' own method, 6.9 to 16.1 s) and
  separated no probe. As in every timed task so far, it is there because the ask requires it.
- **A fixed wear law is not needed to date a turn.** Even with each rope's own constants and each element's
  own gain, two xhigh runs dated MH-1's turn to within half a day by fitting wear to damage. The day decides no
  result (0.70 of a band at either edge of the gap), so this cost nothing.
- **Two verifier studies at once corrupt each other.** The bench counts the CPU time of, and kills, every
  process of nobody, which is right inside the verifier's container. Grading a probe while the seed screen ran
  killed a run (status -9) and added the other bench's CPU to it. Run one bench at a time on a machine.
- **Make the reference the fast method and keep brute force as evidence.** With the brute-force reference the
  limit was 25 times the fast second solution and the plain loops only 2 times over; with a sweep reference
  the limit is 2.9 times the reference, brute force 1.7 to 4.0 times over, plain loops 21 times.
- **Stated, it is solved at low effort.** After the design gate reached main, RS-4 got a section 6 naming both
  conditions and the criterion that tells them apart (where the rope goes on thinning). Low 3 of 3 in 4 to 8
  minutes: each applied the criterion as written and placed the turn within its gap. The difficulty was in
  not knowing the second cause, which the review rules out. Held; the subject has no hard part that survives
  being stated (the compute is met by every probe, and the physics is read in one pass).

## Torsional passage v0: a linear recursion is vectorised by lfilter (Nov 13 night)

`cores/torsional-passage-v0`. Genset shaft lines through speed sequences, a coupling that softens as it
heats, every condition stated; the design rested on direct time integration being too slow (millions of
steps a set). Low effort: 3 of 3 accepted in about two minutes each, every one by exact discretisation of the
line, frozen over short pieces, with the recursion run in C by `scipy.signal.lfilter`.
- **A time limit does not separate methods on linear dynamics.** Any linear system with known forcing steps
  at C speed through `lfilter` (or a matrix-exponential recursion on decoupled modes). Only a recursion that
  cannot be written as a linear filter, nonlinear at the fast time scale, keeps a Python loop in the way.
- **Fully stated designs, today, all went the same way:** engine indicating v6 (2 of 3), v7 (3 of 3), header
  thermal fatigue v0 (3 of 3), torsional passage v0 (3 of 3). Every core that held low effort at 0 of 3 left
  its deciding condition unstated, which review rejects. Whether the bar can be met with everything stated is
  an open question, worth putting to AfterQuery before more cores are built.

## fuel-transfer-lines, the bundle on twin oil lines v2: low 0 of 3, xhigh 1 of 3 (Nov 13)

`docs/design-note-fuel-transfer-lines.md`. Core v2's data byte for byte, with TS-2 4.2 and 4.3 stating how a
pair's division is carried from record to record and how a run opens (the ventilation-district-airflow
rejection), the pressure-drop band widened from 1.5 to 2.5 per cent, and a 40 s limit.

| probe | effort | time | six sites | what it did |
|---|---|---|---|---|
| BL1, BL3 | low | 10 min | 5 of 6 out, as `covering_jobs_only` | the re-covered pipes |
| BL2 | low | 10 min | 4 of 6 out (the narrowed line) | the re-covered pipes and both conditioned pipes as drifting coverings |
| BX2 | xhigh | 65 min | accepted, 0.28 of the band | solved the narrowed bore from the pair's division |
| BX1, BX3 | xhigh | 39, 76 min | 3 of 6 out (the narrowed line) | both conditioned pipes; the narrowed one re-derived with the register's bore |

- **Stating the pair's rule cost nothing.** Every probe, low and xhigh, implemented 4.2 directly and none
  spent time finding the history. Same result as ventilation 20261113b.
- **A low run looked at the campaigns for the first time on this data** (BL2): it ordered both conditioned
  pipes as drifting coverings. Low effort is 0 of 6 on v2 data, but the trend check is no longer xhigh-only.
- **Over six xhigh runs the miss is one step**, from a pipe found to a quantity of the register changed: every
  run ordered both pipes, two of six solved the bore. Read the failing runs' reports before calling it fair:
  BX1 and BX3 did not argue for the register's bore, they never asked what D was.
- **Check the band against the condition's own measurement, not the sound lines.** dp goes as D^-4, so a bore
  solved from one reading carries the reading's error four times over: both independent solutions were 1 per
  cent off on one narrowed line, 0.66 of a 1.5 per cent band. The sound lines had said 0.3.
- **A reading the inside film controls cannot be inverted.** One small site had a covering whose coefficient
  moved the outlet temperature 0.007 K for a factor of 1.21; the reference ran to its bracket. Generate with
  an identifiability check (here: at least 0.15 K for that factor), and state it as a design rule.
- **The machine is the clock.** With two generators and three probes on two CPUs a 14.5 s CPU run took 41.7 s
  on the clock, over a 40 s limit held on both. Run the timed studies one at a time against at most the
  regeneration.

## ventilation-district-airflow 20261113b: approved, official 3 of 8 (Nov 13)

The official difficulty run (model `openai/kimi-k3.1-pro`, 8 runs, 28800 s each) solved 3 of 8. Local
prediction on `model: "opus"` was xhigh 1 of 3, low 0 of 3. Every check of the trial review passed on all
eight (specification, discoverability, verifier, boundary, no exploit, meaningful difficulty).

| run | time | result | what it did |
|---|---|---|---|
| DAYuKjH | 46 min | solved, worst 0.141 of the band | node balances at the stoppings, fan reading, the turn found |
| M7g6bZc | 71 min | solved, 0.141 | the same, with a 1,236-line solver and synthetic regression tests |
| PiHCffY | 69 min | solved, 0.141 | the same, the turn found by sensitivity and close-call replay |
| Csv8yE5 | 69 min | 3 of 6 out | fan reading and the turn, stoppings as booked |
| EAVnXHv | 33 min | 3 of 6 out | the same; called the spare allowance "plain slack" |
| MFG9Lcy | 32 min | 4 of 6 out | spare places on repeat airway surveys; no fan, no stopping |
| MWJ2S7t | 29 min | 5 of 6 out | the airways worked on only, the `worked_on` variant to the point |
| vsUzwWi | 43 min | 5 of 6 out | the same |

- **Three failure modes, not one.** The five failures split by which condition they missed: the stopping
  alone (2), both (3, one of them spending the spare places on repeat airway surveys). The two conditions
  being independent is what made the failures diverse; the review's "meaningful difficulty" passed on each.
- **The passes were long and thorough; the failures stopped early.** Passes took 46 to 71 minutes, the four
  pure failures 29 to 43. Every run stopped voluntarily with more than seven hours left.
- **Both conditions were stated as public evidence, not as words.** The review accepted that: "the two
  hidden-data mechanisms are not stated outright, but they are identifiable from public evidence rather than
  author-only conventions" (a residual of 9.8 to 10.1 m3/s against a 0.3 per cent reading, and an allowance two
  above the work log). What it would not accept, in 20261113, was a rule that decided the truth unstated (the
  fans' opening state and state selection).
- **The time limit decided nothing.** Official runs took 0.8 to 6.3 s against 35. The fast second solution was
  what the reviewer needed, not a limit that binds.
- **Development orders on the examples were allowed.** Five runs dumped crew readings for every branch of the
  two examples by repeated shell orders; the review judged it permitted because `lab.py` says each shell order
  is a run of its own and the examples have neither condition.
- **Local opus xhigh 1 of 3 came true as 3 of 8** on another model.

## Torsional passage v1: a fast-scale nonlinearity is split off and iterated (Nov 14)

`cores/torsional-passage-v1`. v0 with a coupling that stiffens with twist, so the recursion is no longer a
linear filter. Low effort: 3 of 3 accepted in 15 to 19 minutes, all more accurate than the reference: exact
propagation of the linear line with the nonlinear torque iterated in windows, or carried on a coarse step and
fed back through the modes. Each probe also wrote a brute-force simulator and checked against it.
- **Compute is not a lever on this model when the physics is stated.** Every structure tried tonight (a
  linear recursion, a nonlinear one, a sequence that cannot be batched) was met inside the limit by the first
  program a low-effort run wrote. Subject closed for the night.
