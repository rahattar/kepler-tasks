# vent-fan-stall bare core v0 (Nov 13): low effort solves it, 3 of 3 in eleven to twelve minutes

The premise failed. A timed program on shifted hidden data whose deciding condition is a physical one that no
sentence states: parallel axial fans with a stall dip, so a district has two stable states over a band of
resistance and the one it is in follows from its log. All three low-effort probes (opus) saw the dip in the
catalogue table, said in their own words that the state depends on history, followed every log entry and were
accepted. No xhigh probes were run: the screen allows 0 low solves.

## The core

- `airflow.py PACKAGE_DIR OUT_CSV`: the airflow at every survey point of a ventilation district, to VS-4
  (`core/environment/data/docs`). A package is the network (1 562 to 1 855 branches), the fans and their
  catalogue sheet, and a log of 1 264 to 1 364 regulator and door settings; 42 survey rounds of 85 to 94
  stations, 3 570 to 3 948 points. Limit 30 s a run on one CPU, each flow within 1 per cent or 0.02 m3/s.
- Two main fans stand in parallel at one fan house, the second behind 25 to 40 per cent more ducting
  resistance. The catalogue characteristics dip by 35 to 42 per cent of peak pressure in stall.
- Scaling every resistance of a district up, the weaker fan stalls at one value; scaling down again it
  recovers at a value 1.45 to 1.52 times lower (old_shaft, west_reef). Between the two both states are
  stable. A bulkhead door shut for an hour or three takes a district in that band over the top and leaves a
  fan stalled when it reopens; the airlock held open brings it back. Every such excursion lies between two
  survey rounds and is never surveyed.
- Examples with results (north_field, east_decline): fans sized so the district sits at 0.70 of the band's
  lower edge; no fan ever leaves the healthy limb. Pending without results (west_reef) and five of six
  hidden districts: in the middle of the band. Only old_shaft of the hidden six was built before the probes
  came back.
- VS-4 gives the equations, the straight-line characteristic and one circumstance: regulators and doors are
  moved by hand over a minute or more, the air follows in seconds, so the flow is steady at every moment.
  Nothing says a district can have two states.
- Truth (`vnet.py`, `truth.py`): mesh flows, each change taken in 12 steps of the resistance with the flow
  settling after each by implicit Euler on the inertial equations, so a state that ceases to exist goes where
  the air takes it. `truth.audit` refuses a record whose result changes with 40 steps, another path of the
  resistance, another inertia in every branch or every resistance 3 per cent up or down. A change made at
  once instead of gradually does give another record (the airlock slammed shut stalls a fan), which is why
  VS-4 carries the sentence about gradual changes.

## What was measured

| program | examples | west_reef (pending, sealed result) | old_shaft (hidden) |
|---|---|---|---|
| reference `ref_airflow.py` (nodal, sparse; one Newton solve a change, 12 steps where a fan changes limb) | 0 out | 0 of 3948 out, 16 s | 0 of 3570 out, 22 s |
| `ladder.py free`: every round by itself from a healthy start | 0 out | 1974 out in 21 rounds | 1190 out in 14 rounds |
| `ladder.py free_low`: the same from a stalled start | 0 out | 1974 out in 21 rounds | 2380 out in 28 rounds |
| `ladder.py survey_warm`: every round from the round before | 0 out | 1974 out in 21 rounds | 1190 out in 14 rounds |
| `ladder.py event_newton`: every log entry, one Newton solve each | 0 out | 282 out in 3 rounds | 1020 out in 12 rounds |
| `ladder.py event_flow`: every log entry, the change made at once | 0 out | 376 out in 4 rounds | 510 out in 6 rounds |

The reference and the sealed truth are separate formulations (nodal and mesh) and agree to 2.5e-5 relative.
A stalled round has every one of its points out, by up to 82 times the band.

## Probes (opus, low effort, sandboxes from tools/mkprobe.sh)

| probe | time | tool calls | west_reef | old_shaft | method |
|---|---|---|---|---|---|
| low 1 | 12.1 min | 23 | accepted, 14 s | accepted, 12 s | Newton on flows and pressures from the state before; a change on which a fan changes limb re-run in small steps; unstable solutions pushed off |
| low 2 | 11.2 min | 14 | accepted, 9 s | accepted, 12 s | the district reduced to one resistance at the fan house (every branch is square-law), the two fans solved against it; each change eased in, the fans left to settle when their state ends |
| low 3 | 10.9 min | 22 | accepted, 8 s | accepted, 7 s | the same reduction; every fan operating point enumerated, the unstable ones dropped, the branch the fans were on kept until it ends |

What each run reported, unprompted:
- "The catalogue curves have a stall dip, so a fan can stall" (low 3); "the same settings can give more than
  one steady flow. Which one is right depends on how the district got there, and section 5 says the air
  follows each slow change" (low 1); "I take the physical answer to be the stable state the district reaches
  by following its history" (low 2).
- All three solve every log entry in order, not the survey rounds. At 5 ms a state there was no reason not
  to, and low 2's first program already did.
- Low 2's first program, a plain Newton solver, matched both examples and then failed to converge on many of
  west_reef's log states. Low 1's first program landed both fans in stall at three rounds of north_field and
  was told so by the example's results. Low 3 went from the table.
- Each named what it had assumed where VS-4 is silent: the state when a record opens with two possible, and
  the inertia that decides where a fan goes when its state ends.

## Reading

- **A physical condition that leaves a mark in a table is found at once.** The dip is 21 rows of a catalogue
  sheet with the pressure falling, rising and falling. No sentence names it and the screen's model needs
  none. This is the trap analysis's "physics insight: recognised in the first minute or never", and on this
  model it is the first minute.
- **The pending package answered back.** A program that is wrong about the condition did not run cleanly on
  the package that carries it: no convergence, or a fan on a rising limb. The journal bearing's pending
  console costs a wrong program nothing to run; that difference is the whole design.
- **An example with results must not have a second root anywhere a cold solve can reach.** north_field has
  one stable state at every round, which is what the audit checked, and still a root-finder found a stalled
  solution of the equations there. A visible test that a wrong program fails teaches.
- **Following the log is the default, not an insight.** With states this cheap every run solved all of them
  in order and warm. A decider that is history is half given away by the natural program.
- **The truth is sound.** Three programs written three ways and the reference reproduce the sealed result at
  every point, including ten changes of limb. Nothing here was unfair or unclear; it was not hard.
- This closes "a state the solver has to carry, cued by physics the documents leave out" for the timed
  program shape. What the calibration notes already say stopped this model is a decision that cannot be
  tested before it is spent (journal bearing v4, shaft alignment v6 and v7).

## Files

- `vnet.py`, `truth.py`: sealed physics, the record carried through a log, the audit of the design rules
- `gen.py`: the nine districts and their shift (`SITES`); `hidden/_facts_*.json` what the audit found
- `ref_airflow.py` reference; `ladder.py` programs that stop short; `grade.py` runs a program at the limit
- `core/environment/data`: what a probe sees; `hidden/old_shaft` and the pending district's sealed result
- `brief.txt` probe brief; `probes/low1.py` to `low3.py` the three programs as delivered
