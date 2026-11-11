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
