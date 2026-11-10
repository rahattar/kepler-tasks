# Facts instruction.md must carry (vav-airflow-calibration)

instruction.md is the author's own prose. This sheet lists what it has to state, so the task is fully
specified, and what it must not state. Write the contract, not the tour: no role ("you are a TAB engineer"),
no file-by-file narration, no tools sentence, no grading words.

## Must state

- Situation: Level 3 of Building C is served by AHU-3 through 40 pressure-independent VAV boxes, VAV-3-01 to
  VAV-3-40. The east wing was re-ducted and fitted out in 2025, and the floor has to be flow-calibrated before
  it is handed back.
- What a calibration is: each box controller reports airflow as K x sqrt(VP - offset) and controls that
  reported airflow to its setpoint; calibrating a box means choosing its K (cfm per sqrt(in. w.c.)) and its
  offset (in. w.c.).
- Requirement, for every box: with the values loaded, the airflow the box actually delivers is within 10
  percent of its design maximum when it controls to design maximum, and within 10 percent of its design minimum
  when it controls to design minimum.
- Where the facts are: `/app/data` (box schedule, inlet survey, 2024 TAB report, two weeks of BAS trends, the
  documents).
- Hood visits: the TAB contractor can make five capture-hood visits. The service is started with `start-hood`
  and listens at `http://127.0.0.1:8000`; `GET /status` shows the visits left; `POST /visit?box=VAV-3-07`
  requests one. Each request uses one visit. On a visit the contractor drives the box to its design minimum, a
  midpoint and its design maximum and reports the hood reading at each diffuser with the box's trended values
  during the readings. Reports are also written to `/app/visits/`.
- Deliverable: `/app/output/calibration.csv` with the header `tag,k_factor,vp_offset_inwc` and one row per box.
- Closing line, after a blank line, exactly:
  `You have 10800 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.`

## Must not state

- Grader, verifier, scoring, test, reward or tolerance-as-grading words; state the 10 percent as a requirement.
- Any mechanism or the boxes that matter: zero drift or auto-zero, which boxes never close, laboratories running
  day and night, elbows or their orientation, bent, crushed or sagging connectors, that the 2024 report is stale
  for the east wing, which boxes to visit, or that one box per class suffices.

## Numbers that must match the bundle

40 boxes; VAV-3-01 to VAV-3-40; 2025; 10 percent; five visits; port 8000; 2024; two weeks; 10800 seconds.
