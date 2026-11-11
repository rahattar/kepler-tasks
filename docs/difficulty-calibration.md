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
