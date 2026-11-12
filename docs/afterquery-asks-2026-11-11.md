# AfterQuery asks, 11 November 2026: timed re-runs on shifted hidden data

Two messages received on 11 November 2026: the team announcement and an email to Alex. Both ask for Science tasks
that meet two requirements together, and these are now the top priority for new tasks. The verbatim texts are at
the end; the checklist below is the working form.

## Checklist for a new task of this kind

1. **The tests re-run the agent's program on hidden inputs, under a per-run time limit.**
   - The tests run the program; they do not read a file the agent produced earlier.
   - The limit is enforced in `tests/` (e.g. `subprocess.run(..., timeout=N)`), and instruction.md states the
     same N: "Each run of <program> must finish within N seconds on 1 CPU." The two must match; preflight checks it.
   - N is about 2-3x the reference's runtime. A correct but unoptimised version (plain loops, brute force,
     recomputing instead of caching) must time out; if it still passes, make the hidden workload bigger. Ship
     that naive version in the evidence and show it timing out.
   - A timeout fails the whole task. Never catch and ignore `TimeoutExpired`, never grade output written before
     the kill, and no pass-share gate may let a timed-out case through.
   - Threads are pinned in the run environment (`OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`) so timings
     repeat.
   - The hidden workload needs real compute: a reference that finishes in under a second leaves nothing to
     optimise.
2. **The hidden data is deliberately different from the visible data.**
   - Use one or more of: a new condition or regime; injected faults or corrupted readings; values outside the
     visible range; unseen categories (sites, species, materials, devices); edge cases.
   - A reseed of the same generator does not count. No visible case may appear in the hidden set.
   - A solution that overfits the visible data must fail the hidden set.
   - The submission notes say what the shift is and point to where it is built (generator config, manifest,
     data files).
3. **As always:** 0-5 of 8 on the difficulty probe, a binary reward, the usual structure checks.

Quick self-check before submitting (from the announcement):
- The tests run my program and don't just read a file.
- The per-run limit is in tests/ and stated in instruction.md, and both match.
- A naive but correct version of my solution times out.
- A timeout fails the whole task.
- The hidden data is deliberately shifted (not a reseed), and my notes say how.

Note for this repo: requirement 2 is mechanism B of `docs/trap-analysis-2026-11-11.md` (a fault only in unseen
inputs). It sits against the Nov 5 design rule in `docs/playbook.md` ("No more variants of 'a program scored on
~8 hidden cases'"). A timed re-run on deliberately shifted hidden data is a different verification shape from the
untimed program tasks in the catalogue, but how the two rules fit together is Alex's call.

## Further guidance (team channel, 11 Nov 11:38 PM and 12 Nov 1:23 AM)

Two later announcements, verbatim below. As working rules:
- **Every deciding fault or condition shows at least once in the visible data.** A hidden case may combine,
  move or scale them, but a kind of fault or condition that decides a result must have a visible instance. This
  bounds requirement 2 above: the shift is in regime, combination, location or range, never a kind of thing the
  agent has never seen.
- **Docs and labels accurate and unambiguous.** Every column and every term means one thing and says what it is.
- **A correct standard method passes.** No unwritten rules, no matching the reference's exact formula; the
  tolerance comes from an independent solution (here: twice the widest sound deviation, floored at the seed
  screen, as preflight checks).
- **Every probe failing the same check with the same wrong answer is a warning** that something is hidden or
  unclear, not a success. Read such a run's reasoning before calling the trap fair.
- **0 of 8 is accepted but not a pass by itself.** It is reviewed on the same rubric; the difficulty has to come
  from the science, not from tricky setup, unclear wording or arbitrary constraints.

> **11:38 PM.** A few tips for strong tasks:
>
> Any fault or condition that decides the result should appear at least once in the visible data.
> Keep docs and labels accurate and unambiguous.
> A correct standard method should pass. Don't make it about guessing unwritten rules or matching your exact
> formula.
> Check your tolerance with an independent solution.
> If every probe attempt fails the same check with the same wrong answer, something is likely hidden or unclear.

> **1:23 AM.** Hi everyone, a quick FYI! Tasks that score 0/8 in the difficulty probe are still accepted, but
> they're reviewed against the same rubric as every other task in the difficulty band. A 0/8 result doesn't mean
> a task passes automatically. Difficulty needs to come from the science itself, so tasks made hard through tricky
> setup, unclear wording or arbitrary constraints won't meet the standard we're looking for. Keep building those
> challenging, science-driven tasks!

## The announcement (team channel, Anwes MisTeam, 11 Nov 2026, 4:34 PM)

> We're looking for more Science tasks like this
>
> Hi all, we're looking for more Science tasks that meet both of the requirements below. Tasks that fit both are
> our top priority right now.
>
> 1. Your program is re-run under a tight time limit
>
> * The tests run the agent's program on hidden inputs, instead of grading an output file the agent produced
>   earlier.
> * Each run has a per-run time limit, enforced in tests/ (for example subprocess.run(..., timeout=N)), and the
>   same limit is stated in instruction.md: "Each run of <program> must finish within N seconds on 1 CPU."
> * The limit is about 2-3x your reference solution's runtime, so a correct but unoptimised solution (plain
>   loops, brute force, recomputing instead of caching) times out. If it still passes, make the hidden workload
>   bigger.
> * A timeout fails the task. It isn't caught and ignored, output written before the kill isn't graded, and no
>   pass-share gate lets a timed-out case through.
> * Threads are pinned in the run environment (OMP_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1) so timings are
>   reproducible.
> * The hidden workload needs real compute. A reference that finishes in under a second leaves nothing to
>   optimise.
>
> 2. Hidden test data is deliberately different from the visible data
>
> * Hidden cases differ on purpose, using one or more of:
>   * a new condition or regime
>   * injected faults or corrupted readings
>   * values outside the visible range
>   * unseen categories (new sites, species, materials, devices)
>   * edge cases
> * The same generator with a new seed doesn't count.
> * No visible case appears in the hidden set.
> * Your submission notes say what the shift is and point to where it's built (generator config, manifest, data
>   files).
> * A solution that overfits the visible data fails the hidden set.
>
> Also needed: 0-5 out of 8 passes on the difficulty probe, a binary reward, and the usual structure checks.
> Quick self-check before submitting:
>
> * The tests run my program and don't just read a file
> * The per-run limit is in tests/ and stated in instruction.md, and both match
> * A naive but correct version of my solution times out
> * A timeout fails the whole task
> * The hidden data is deliberately shifted (not a reseed), and my notes say how
>
> Thanks!

## The email (Muktahal Birring, Growth Associate, AfterQuery, to Alex)

> Hello Alireza,
>
> Thank you for your work on Kepler. Some of your Science tasks match exactly what we're looking for right now,
> and we'd love more like them.
>
> What makes them stand out:
>
> 1. They re-run your program under a tight time limit. The tests run the agent's program on hidden inputs with
> a per-run limit that's stated in the instructions, so a correct but slow solution times out and the model has
> to optimise.
> 2. Their hidden data is deliberately different. The held-out cases use new conditions, injected faults,
> out-of-range values, unseen categories or edge cases, not just the same generator with a new seed. A solution
> that overfits the visible data fails.
>
> If you can build more tasks that meet both requirements, a few things help:
>
> - Set the limit at about 2-3x your reference runtime, and check that a naive but correct version of your
> solution times out.
> - Make sure a timeout fails the whole task. Don't swallow TimeoutExpired, and don't grade output written before
> the kill.
> - State the limit in instruction.md, and keep it matched to the value in tests/.
> - In your submission notes, say what the shift in the hidden data is and where it's built (generator config,
> manifest, data files).
> - Keep difficulty at 0-5 passes out of 8.
>
> If you'd like more details, please reach out to the project staff on the channel.
>
> Thanks again for setting the bar with these. We're looking forward to your next tasks.
>
> Best,
> Muktahal Birring
> Growth Associate
> AfterQuery
