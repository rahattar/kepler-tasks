# Design note: rope-bending-damage (Nov 13)

**Status: held, not delivered.** Unstated, the conditions met the probe bar (low 0 of 3, xhigh 1 of 3) and fail
the design gate; stated in RS-4 section 6, low effort solves it 3 of 3. See the end of this note.

A timed program on shifted hidden data, to the Nov 11 ask. Built from bare cores `cores/hoist-rope-v0` and
`cores/hoist-rope-v1` (their RESULT.md files, and the hoist rope section of `docs/difficulty-calibration.md`).
The bundle is v1's design at shipping size, with the reference made fast and the limit tightened to match.

**Mechanism.** A rope's history is not in its records, and two different histories leave the same trace.

- RS-4 sums damage for a piece of rope, not for a place on the crane, and reports it for the rope as it lies
  at the end of the log (sections 4 and 5 say so in physical terms).
- **Turned.** A rope turned end for end between two surveys: the piece now x from the drum lay L - x from it
  before, and was bent there.
- **From the dead end.** A survey taken from the dead end and written down as if from the drum: the rope never
  moved, only the sheet's order is reversed.
- Both show only as a survey that mirrors the one before. The turn explains the mirror perfectly and is the
  textbook event, so it confirms itself.
- They are told apart by where the rope goes on thinning afterwards: bendings fall where the reeving puts them,
  so after a turn the loss follows the bendings as written and after a change of end it follows them mirrored.
- Both examples are exactly sound. The pending works (no results) has one rope of each (MH-1 turned, MH-5 from
  the dead end). Five of six hidden works have them in other numbers; DS-5 has both, in sequence; coil_yard is
  sound.

**The timed half.** Limit 4 s a run on one CPU, held on the clock and on CPU time of the process tree. The
reference counts bendings by a sweep (sorted meeting heights, bisection, difference arrays, a five-term series
in ln S for the per-station exponent): 1.2 to 1.4 s, 2.9 times under the limit. Brute force over movements and
stations in numpy, the core's own method, takes 6.9 to 16.1 s; plain loops 85 to 90 s. Stations are 1 m apart
(2.5 m and 5 m in the cores) so that brute force is clearly out.

**What must not be changed without re-probing.**
- The examples are sound to the last digit, down to the order of the log's rows (core v0's first build had
  overlapping cycles and sheaves stopping on a station; two low reports dwelt on the 1 per cent it cost).
- The pending works has no results. With results a wrong program fails a visible test.
- A survey is not a function of the result: each rope has its own wear constants and each element its own gain
  (`rope.Wear`). Core v0's fixed law let three xhigh runs date the turn to a day, and would have let a program
  read the damage off the last survey.
- The documents keep core v1's wording (section 6 aside): `station_m` is the "distance of the station from the drum anchorage,
  along the rope", the standard's d is "the diameter of the element as measured at the last survey", and the
  damage is the sum "over every bending it has had since the rope was put on". The bundle's first documents
  said the survey was "copied from the survey sheets", `station_m` "the station as the survey sheet gives it",
  d "the diameter of the element itself", and "An element is a piece of the rope, not a place on the crane":
  xhigh 3 of 3, every passing report in the words of a sheet written from the wrong end. Reverted: 1 of 3.
- No field names a turn, a reversal or the end a survey started from.
- The day of a turn does not decide: at either edge of its gap no station moves more than 0.70 of the band.

**Probes** (`cores/hoist-rope-v1/bundle-probes/RESULT.md`, programs kept there).

| documents | low | xhigh |
|---|---|---|
| first (more revealing) | 0 of 3: two RS-4 as written, one every mirror a turn | 3 of 3 |
| core v1's wording | not rerun | 1 of 3: one accepted, one every mirror a turn, one missed DS-5 alone |
| core v1's wording and RS-4 section 6 stating both conditions and their criterion (as committed) | 3 of 3, in 4 to 8 min | not run |

Every one of the nine probe programs ran in 0.7 to 1.7 s, low effort included: the 4 s limit is met by any run
that reads it, and it is there because the ask requires it. Brute force, the cores' own method, is what it stops.
