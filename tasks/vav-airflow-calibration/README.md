# vav-airflow-calibration

Level 3 of an office and laboratory building is served by one air handler through 40 pressure-independent VAV
boxes. The east wing was re-ducted in 2025, and before the floor is handed back every box must be
flow-calibrated: a K-factor and a velocity-pressure offset per box, so that with those values loaded the airflow
each box delivers is within 10 percent of its setpoint at design minimum and at design maximum. The records are
the box schedule, the inlet survey, a 2024 TAB report, two weeks of 15-minute BAS trends per box and seven
documents (application note, controller manual, hood manual, owner's air-balance standard, duct specification,
renovation close-out, notes to the 2024 report). The TAB contractor makes at most five capture-hood visits, each
at design minimum, a midpoint and design maximum. The deliverable is `/app/output/calibration.csv`.

## Difficulty

This is a test-and-balance engineer's or commissioning agent's job. Two effects set each box. The averaging
cross's amplification depends on the inlet: the factory K assumes a straight inlet of three diameters, a hard
elbow near the inlet shifts it by an amount that decays with the straight run and whose sign depends on the
turn's orientation relative to the cross, and a flex connector that is bent or sagging at the inlet is the worst
case. The transducer's zero drifts; firmware 3.x removes it hourly, firmware 2.4 does not, and a 3.x box whose
auto-zero valve has failed carries it unalarmed. As shipped (factory K, offset 0), 18 boxes miss, by up to 69
percent.

The records settle most of the floor. Straight inlets need nothing. The west wing's ductwork is unchanged since
the 2024 report, which measured half its boxes at design maximum, and its horizontal elbows follow a decay with
the straight run (-1 to -18 percent). Every box that closes at night shows its zero error in the trends: the six
office boxes on firmware 2.4 (0.018 to 0.030 in. w.c.) and VAV-3-04, a firmware 3.1 box whose night readings
sit at 0.026 in. w.c. where a working auto-zero reads about zero.

The 2025 east wing is not settled by the records. The 2024 readings there predate the re-ducting. The
renovation dropped the branch ducts into the east boxes from above, and those vertical-drop elbows read the
opposite way to the west wing's horizontal turns (+18 to +21 percent). The close-out punch list names three
connectors crushed into tight bends (+32 to +39 percent). The commissioning walk-down says connectors longer
than the 5 ft limit were hung without supports and sag into the inlet, which the survey's lengths identify
(+16 to +20 percent). The three laboratory boxes on firmware 2.4 hold their minimum day and night, so their zero
errors (0.040, 0.008 and 0.038 in. w.c., one per transducer) never show in the trends. Five visits cover
exactly the three laboratory boxes (VAV-3-38 is also a crushed connector), one vertical drop and one sagging
connector; each class then carries to its unvisited members within the band. A plan that confirms an already
measured class, guesses a laboratory zero or carries one class to another misses by 14 percent or more.

The floor, its records, trends and hood readings are synthetic, written by the disclosed generator in
`authoring/provenance/` from the sealed definition.

## Reference solution

`solution/solve.py` (run by `solution/solve.sh`) reads the factory K table from the application note and the
schedule, survey, 2024 report and trends from `/app/data`. Offsets: each closing box's median velocity pressure
with the setpoint at zero; firmware 2.4 boxes take it, a firmware 3.x box takes it when it is above 0.005 in.
w.c. It groups the boxes into inlet classes (straight, horizontal elbow, vertical-drop elbow, flex within
specification, the punch list's crushed connectors, connectors over 5 ft) and visits every box the records
cannot settle: VAV-3-36, 37 and 38 (laboratory, firmware 2.4, never closed), the vertical drop with the shortest
straight run (VAV-3-28) and the longest sagging connector (VAV-3-31). Each visit gives K and offset from a
least-squares fit of flow squared against velocity pressure through the three hood totals, weighted toward low
flows. West boxes in the 2024 report take their own multiplier (a 2.4 box's 2024 zero taken as half of
today's); horizontal elbows take a two-parameter decay fitted to the five reported elbows; flex boxes within
specification and vertical drops take the same decay length with the amplitude fitted to their measured members;
crushed and sagging connectors take their visited member; straight inlets take the factory K. On the shipped
floor every box is within 5.8 percent. It never reads the sealed definition or the verifier.

## Verification

`tests/grade_vav.py` loads each submitted K and offset into the sealed definition (`tests/vav.py`, the module
that also drives the hood service) and computes the airflow the box delivers when the controller holds design
minimum and design maximum. Every box must be within 10 percent of the setpoint at both points; the file must
carry the columns `tag`, `k_factor`, `vp_offset_inwc`, one row for each of the 40 boxes and no other tags,
finite values and K above zero. The record goes to `/logs/verifier/metrics.json`.

The 10 percent is the owner's acceptance band from the documents. Against it (all figures are worst-box
delivered-airflow errors):

- `authoring/evidence/method_spread.txt`: 3240 sound calibrations (every complete plan, eight visit orders;
  weighted, unweighted or two-point visit fits; class transfer by decay amplitude, class mean or a free decay
  fit; the 2024 zero of a 2.4 box taken as none, half or all of today's). All pass; the worst is 6.1 percent.
- `authoring/evidence/route_study.txt`: every shortcut and incomplete plan misses, the nearest by 15.6 percent
  (a long-connector class left unvisited and taken as ordinary flex), the others by 15.8 to 100 percent: offsets
  on firmware 2.4 only, the stale 2024 readings in the east wing, one elbow model for both orientations, the
  crushed connectors at their surveyed straight run, a laboratory zero guessed from the fleet, no vertical-drop
  or no long-connector visit. It also shows the one lucky case: an unvisited VAV-3-37 given offset 0, which no
  record supports, passes because that transducer's zero is small.
- `authoring/evidence/campaign_study.txt`: of the 4368 five-box campaigns from a sixteen-box pool covering every
  class, the six that pass are exactly those visiting the three laboratory boxes, a vertical drop and a
  sagging connector; the others miss by at least 13.6 percent, whichever defensible fallback a campaign uses
  for a class it left unvisited.

`methods.py` is the shared engine of the three studies; it emulates visits with the service's own function and
seeds, and uses the sealed definition only for that and for grading.

## Layout

- `environment/`: one image. Records in `/app/data`; the hood service in `environment/hood/` (installed to
  `/opt/hood`, owned by the `tab` user, mode 700; visit count in `/var/lib/hood`, also 700); `start-hood`
  starts it through one sudo rule; visit reports are written to `/app/visits`. The agent runs as `agent`
  (`[agent] user`), which cannot read the service's files or state, signal it or reset its count.
- `tests/`: verifier (separate container, no network).
- `solution/`: reference.
- `authoring/provenance/`: the generator (`gen.py`) and the sealed definition it reads (`vav.py`); the documents
  in `environment/data/docs` are written by hand. `authoring/evidence/`: the three studies, `preflight.py`
  (bundle) and `check_instruction.py` (instruction.md); `authoring/instruction-fact-sheet.md`: what
  instruction.md must state.

The building, the contractor, the manufacturer and the instrument are fictional; the data are synthetic.
