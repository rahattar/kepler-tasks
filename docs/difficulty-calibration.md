# Difficulty calibration lessons (from Alex's Kepler tasks, Oct-Nov 2026)

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
