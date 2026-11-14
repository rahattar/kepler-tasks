# Review: the five cores of Nov 13 evening, and what went wrong

Cores: `sprinkler-demand-v2`, `gear-face-load-v0`, `gear-face-load-v1`, `header-thermal-fatigue-v0`,
`carburizing-case-depth-v0`. Written from the cores' own briefs, standards and generators, the 21 probe reports
(18 low, 3 xhigh) and `docs/rejection-patterns.md`, not from the RESULT summaries.

## Verdict

All five were built in one paradigm: a timed program whose hidden cases are decided by a fault in the records
that no agent-visible text states, with a physical clue left in the package for a careful solver to find. That
paradigm cannot produce an acceptable task. AfterQuery's quality review rejects an unstated deciding condition,
and the bundle-level rejection that says so names `gear-face-load` (engine-indicating, Nov 13). Once the condition
is stated, it is solved at low effort (engine-indicating v6: 2 of 3). So the probes were measuring a lever that is
not available: a 0 of 3 from any of these cores would still have failed review. Underneath the trap, none of the
five had a hard part. Every probe solved the science and the computation in minutes, and the time limit never
came near any program.

## The five at a glance

| core | deciding condition | stated in the documents? | low effort | time to find | probe CPU against the limit |
|---|---|---|---|---|---|
| sprinkler-demand-v2 | a registered pipe C aged since; flow tests on file show it | partly (FP-7 says the register's C is as installed) | 3 of 3 solved | 8 to 11 min | up to 12.5 s of 20 |
| gear-face-load-v0 | one gear's chart flank names exchanged; the pattern's second edge shows it | no | 2 of 3 solved | 3.5 to 4 min | up to 21 s of 40 |
| gear-face-load-v1 | the same; only pitting shows it | no | 0 of 3, then 1 of 3 after "nobody reviews" | 1.5 to 2.5 min (re-run) | up to 3.0 s of 10 |
| header-thermal-fatigue-v0 | fluid thermocouple lag; the outer-surface thermocouple shows it | no | 3 of 3 solved | 4 to 10 min | up to 1.7 s of 6 |
| carburizing-case-depth-v0 | oxygen probe drift; the enrichment gas shows it | no | 1 of 3 solved, 3 of 3 found it | 4.5 to 7 min | up to 6.4 s of 15 |

The "stated?" column is a search of every agent-visible file for the condition and its criterion. Only the
sprinkler core said anything, and it was the one solved fastest and most completely.

## What went wrong

### 1. The deciding condition was kept out of the words, which the rubric rejects

- **The rule was in the repo before any of these cores.** The design rules of Oct 18 say every source the solver
  might trust and the grader does not must be signalled as unreliable in the documents. Each core broke it: the
  probe reading, the fluid thermocouple, the chart flank names and the register C were all trusted sources that
  the grader did not trust, and none was signalled.
- **The team lead's list of common rejections covers all five.** Item 3: unstated conventions decide the score
  (the chart naming convention). Item 4: shipped data wrong without a warning (all five). Item 6: results that
  do not separate good attempts from bad (every failing run lands on the same wrong answer). Item 7: recovering
  planted constants from a synthetic record (the header's lag, the carburizing drift curve).
- **The review applies it to program tasks with hidden cases.** Engine-indicating 20261113 failed "well
  specified" and "test instruction alignment" because "an expert could reasonably implement the documented ...
  calculation and still fail five of six cells". The entry names gear-face-load among the cores that will fail
  the same way. Ventilation 20261113 failed "well specified" for the same reason: a rule decided the truth and
  the documents did not state it.
- **When the documents state it, the difficulty goes.** Engine-indicating v6, stated with its criterion: low
  2 of 3. Sprinkler v2, the only one of these with the condition partly stated: low 3 of 3. The others were found
  at low effort anyway: gear v0 through its own fit's misfit, and gear v1, the header and carburizing as soon as
  the brief said to act on the evidence.

### 2. There was no hard part apart from the trap

- **The science was implemented first time.** Low-effort runs wrote a contact solver on the active set, modal or
  closed-form solutions of radial conduction, batched nonlinear diffusion with Tibbetts' diffusivity, and ASTM
  rainflow, all checked against the examples and for grid convergence, in 1.5 to 11 minutes. That is the standard
  read and implemented, which is the shape `difficulty-calibration.md` already calls read in one pass.
- **The time limit added nothing.** Every probe program in every core ran inside its limit, most at or below the
  reference's time; the nearest any came was 62 per cent of it (sprinkler v2, 12.5 s of 20). The limits were set
  at 2 to 3 times our reference and checked against our own plain-loop strawman, never against what a competent
  solver writes. AfterQuery asks for a limit that a correct but unoptimised solution misses. Ours were met with
  room to spare by the first program each probe wrote.
- **So every bit of difficulty sat on the trap.** That is a single point of failure: found, and the task is easy;
  not found, and the task is unfair.

### 3. A single trap makes every failure the same failure

- **Each core had one deciding condition.** A run either sees it and passes, or misses it and fails in the one
  designed way. That is exactly the pattern of the Nov 12 tip: "If every probe attempt fails the same check with
  the same wrong answer, something is likely hidden or unclear."
- **We read the warning and did not change course.** At gear v1 all three low runs, and then all three xhigh runs,
  failed the same check. Two xhigh runs had found the condition and deferred to the package. The tip was right:
  the condition was unclear. The fix applied ("nobody reviews the results") nudged the solver to act, but still
  did not state what may differ or how it is settled.
- **The accepted task is built the other way.** base-pressure-diagnosis states its five causes in the standard and
  makes naming the cause the deliverable. Its difficulty is separating confounded mechanisms (a leak against
  permeation, a trapped volume against wall gas, a gauge correction that depends on the answer) across fifteen
  layers. Its 18 unsound routes between them miss every chamber, each chamber by at least three routes, so the
  failures are diverse.

### 4. The estimates were planted constants, and the generator's model form decided the score

- The header lag and the carburizing drift were constants and curves the generator chose and the solver had to
  recover from a synthetic record (item 7).
- **In carburizing the model form itself was unstated.** The generator's carbon balance was linear in the
  carbon potential and the uptake. CD-2 says nothing about the gas, so each run had to invent a balance. C3 added
  a temperature term and passed; C2 used per-load intercepts and came out about a fifth low, failing by about four
  bands. A reviewer would read that as a domain expert modelling the balance differently and failing: not well
  specified, and a tolerance inside the spread of reasonable methods (item 1).

### 5. Process

- **I did not read what the other sessions recorded.** I pulled main before every commit but read none of the
  new entries. The engine-indicating rejection reached main at 21:08 and the v6 lesson at 21:30. The v6 lesson
  says the condition cannot be both unstated and fair, and that the hard part has to remain once everything
  that decides a case is written down. I built the header core at 21:40 and the carburizing core at 22:19, both
  with unstated conditions.
- **Rules already in the repo were broken.** Surplus measurement in a calibration (the conveyor lesson, before
  gear v0); a record of the kind the program computes (my own sprinkler v2 lesson, before header v0); a column
  with no stated use is a signpost (journal bearing, Nov 12; engine indicating, recorded 17:05 Nov 13, before
  carburizing). I quoted that rule myself while ranking ideas, then built carburizing on an unused column and a
  calibration date.
- **Each failure was recorded as a patch, not a verdict on the method.** Five cores in four subjects: the
  witness moved each time (a flow test, a second pattern edge, pits, a thermocouple, a gas flow), and the
  paradigm never changed.
- **The probe became the objective.** The designs were tuned to what low-effort runs tend not to look at:
  examples before the pending package, used columns before unused ones. That is concealment. It fails as soon
  as the brief says to act, and the quality review rejects it whether or not the probe misses.
- **No pre-mortem.** Each core took about an hour to build and then went straight to probes. Asking "what does a
  careful engineer with these documents do in the first ten minutes?" would have predicted four of the five
  results.
- **One template for everything.** The four later briefs share 71 to 95 per cent of their text, names and
  numbers masked, and every core has the same anatomy: a works standard at a revision, two examples, one pending
  package, six hidden cases. The similarity gate rejected ventilation-district-airflow today on archetype alone
  (against impeller-shrink-fits), with text overlap no higher than 0.42.

## What was sound

- The physics in each core was real, converged (checked by halving), and given an independent reference.
- Tolerances were checked against the truth's own resolution (gear v1: 240 stations within 0.27 per cent of 960).
- Grading was mechanical, under the stated CPU limit, in a clean directory; every number reported came from it.
- Each failure was written up honestly and pushed.

## What this implies for the next design

1. **Write down everything that decides a hidden case first**: what may differ from what the package gives, and
   the criterion that settles it. Then ask whether a careful engineer holding those documents would still get it
   wrong. If not, do not build. Probe that stated version first (the v6 lesson).
2. **Put the difficulty where stating it does not remove it.**
   - **Confounded identification under a budget** (base-pressure, chill-bench): stated unknowns that trade off
     against each other, evidence that separates them only through the right physical argument or the right
     test, and several such layers.
   - **A plant or simulator that answers back** (the controller tasks).
   - **Numerics that are genuinely hard to get right** across a documented envelope: stiffness, regime changes,
     ill-conditioning, shown by independent solutions.
   - **Compute that binds against what competent solvers actually write**, not against a strawman.
3. **Calibrate the time limit against the probe programs.** If the first program a low-effort run writes is
   inside the limit, the limit is not a source of difficulty, whatever the strawman does.
4. **Before each build, read every entry added to `rejection-patterns.md` and `difficulty-calibration.md` since
   the last read.**
5. **Write each task's brief and documents fresh.**
