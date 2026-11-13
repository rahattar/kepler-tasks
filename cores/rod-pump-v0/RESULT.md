# rod-pump bare core v0 (Nov 13): low effort finds the loose anchors, 1 of 3 accepted, 2 of 3 right on the condition

Idea 1 of this session's ideation, picked by Alex: rod-pumped wells, a timed program on shifted hidden data.
The program reads a field package (well file, rod strings, two dynamometer cards a well, a setting table of
100 settings a well) and gives, for every setting, the plunger stroke, the liquid lifted and the peak and
minimum polished rod load to a standard, RL-2, that states the physics in full: the damped wave equation in a
tapered string, a two-valve pump with gas in the barrel, tubing that stretches under the load it carries.

**What was meant to decide a hidden case.** The tubing is free to stretch below the point where it is held. The
well file gives the depth at which an anchor was set. In 19 wells of five of the six hidden fields, and in two
wells of the visible package without results, that anchor does not hold: the tubing is free from the wellhead
and the plunger's stroke in the barrel is 6.5 to 26 per cent shorter than the well file gives. No cell says so.
The card does: the pump load is picked up over a rise of the rod foot equal to the stretch of the whole
tubing string. Free tubing with results is in both examples (wells with no anchor, and anchors set high).

## What was measured

| what was run through `grade.py` (45 s a run, bands 3 per cent) | hidden settings out, of 14,100 | run time a field |
|---|---|---|
| reference (`ref_rodlift.py`: string in the frequency domain and on its modes, pump in time, tubing from the card) | 0; worst 0.52 of a band | 10 to 20 s |
| the same with the tubing as the well file has it (`as_registered.py`) | 1,900: every setting of the 19 wells, by 9 to 20 bands; both examples accepted | 14 to 20 s |
| naive (`naive_rodlift.py`: every setting stepped through time on its own) | right on 12 settings (0.02 of a band) at 3 s a setting; over the limit on the first field | about 2 h a field |
| low 1 (opus) | **0: accepted**; worst 0.62 of a band | 14 to 21 s |
| low 2 (opus) | 1,911: every setting of the 19 wells, and 11 settings of four other wells on the minimum load | 16 to 21 s |
| low 3 (opus) | 100: one well, HF-05, liquid supply 6.6 per cent out; every loose well right | 16 to 20 s |

## The probes (model "opus", effort low, sandboxes from tools/mkprobe.sh)

| probe | minutes | tool calls | the anchors | how |
|---|---|---|---|---|
| low 1 | 25 | 55 | found: MB-03 and MB-04 named in its report | fits a simulated card to the cards on record for fluid load and supply, tries both free lengths (anchor, wellhead) and keeps the better fit |
| low 2 | 54 | 118 | not found: free length from the well file; its report does not mention the tubing | pump card from the surface card for fluid load and gas column, no fit of the card to the file's model; the time went on its solver's stability |
| low 3 | 29 | 52 | found: MB-03 and MB-04 named | free length from the slope of the load pick-up on the pump card, checked against the file; "cards fit to 0.3 kN instead of 4 kN" |

- **Both runs that compared a model with the cards found the condition, in under half an hour.** The card is a
  measurement the condition moves, and a fit of the card is the natural way to get the fluid load. The wrong
  program does not run clean on the visible instance: its fit is 4 kN out where the others are 0.3.
- **The standard's own sentence listed the alternatives.** RL-2 section 5 has to say where free tubing ends:
  "the anchor where an anchor holds the tubing to the casing, the wellhead where none does". Low 1 turned that
  into two candidates a well.
- **The one failure of low 3 is a slip, not the task:** a fitted liquid supply on one fibreglass well.
- **The physics and the limit were no obstacle.** Each wrote the string, the pump, the card analysis and a
  batched solver inside 25 to 30 minutes, 13 to 21 s a field.
- **Low 2 found a gap in RL-2:** it does not say whether the gas law's pressures are absolute. The sealed
  definition takes every pressure as given; the examples told the run which. A v1 would have to say it.
- The 11 minimum loads low 2 lost are its own solver's: the sealed simulation gives the same cycle at eight
  settling times on the settings it named (minimum load within 0.01 per cent of the peak).
- No xhigh probes were run: a low-effort acceptance settles it.

## Reading

Not at the bar (easiness 0 of 3). The core confirms the day's other cores and adds one thing to
journal-bearing v5's result. There a register is contradicted and the natural program pools the evidence
away and runs clean, and three low probes ran the pending package without reading it. Here a register is
contradicted too, but the program has to compare its model with the very measurement that shows it. A
contradicted record holds only where nothing the program computes is compared with a measurement the
contradiction moves.

On this subject that leaves little room: every downhole condition shows in the card, and what the card cannot
show (plunger size, pumping speed) nothing else in a package shows either.

What is sound and could be reused: the sealed simulation, the generator, the reference and the grader. Two
programs written by probes, one in the time domain and one with a frequency-domain card analysis, agree with
the sealed results within 0.62 of a band on every hidden setting they got right, so the truth is determinate
and the bands are wide enough for a correct method.

## Files

- `rodsim.py` sealed physics; `gen.py` the nine fields and the shift (`FIELDS`: `loose` is the number of
  anchors that do not hold); `core/sealed/*.json` each field as built
- `core/environment/data` what a probe sees: `docs/` (RL-2, the package format), `examples/` (two fields with
  results), `pending/` (one without); `core/hidden`, `core/truth` the six fields the program is run on
- `ref_rodlift.py`, `as_registered.py`, `naive_rodlift.py`; `grade.py`; `compare.py`, `diagcheck.py`
- `brief.txt`, `mk.sh` the probe brief and the sandbox (a wrapper round `tools/mkprobe.sh`)
- `probes/` the three programs as graded; `logs/` every grading run above
