# hvac-submittal-review

An owner's reviewing engineer checks a design-build contractor's cooling load calculations and packaged
rooftop unit selections for the renovation of a 2004 college building. The documents are the owner's design
standard, the architect's room schedule and envelope areas, the addenda, the contractor's submittal, the
manufacturer's extended performance data and the facilities office's records. A field-verification service
answers at most eight requests. The deliverable is `/app/review.json`: per unit the verdict (accept, reject
undersized, reject oversized, undetermined) with the outdoor air intake flow, the coil entering wet bulb, the
design block loads and the net capacities, and the submittal decision.

## Difficulty

In practice this is the work of an owner's reviewing mechanical engineer, or on larger projects the
commissioning authority's HVAC reviewer, checking a design-build submittal before the units are bought. The
college, the building, its records and the submittal are synthetic (written by `authoring/provenance`) but
realistic in their numbers: design conditions close to Chicago's 0.4 percent values at its 98.9 kPa station
pressure, the outdoor air rates of ASHRAE 62.1-2019 Table 6-1, and extended performance tables with the form
and trends of published packaged-unit data. The load tables are the owner's simplified CLTD/SCL/CLF set.

The owner's standard names the methods and gives the design data; it does not spell the methods out. Outdoor
air follows ASHRAE 62.1-2019 for multiple-zone recirculating systems (Appendix A, where the zone with the
highest primary outdoor air fraction sets the system ventilation efficiency), the coil entering condition is
the adiabatic mixture of outdoor and return air at the station pressure, and the selected unit's capacity is
read from the manufacturer's extended tables at that entering wet bulb, the scheduled airflow and the design
outdoor temperature, with the manufacturer's corrections for entering dry bulb (bypass factor), dry coil and
indoor fan heat on a draw-through unit. Acceptance tests net total, net sensible and net latent capacity
separately, so a unit can fail on sensible or latent capacity while its total looks right.

The contractor's sheet is correct arithmetic with the usual shortcuts: the zone outdoor airflows summed with
no ventilation efficiency, and AHRI-rated gross capacity at 19.4 C entering wet bulb. On that basis all seven
selections are acceptable. Against the method, the coil entering wet bulb is 17.67 to 19.07 C, the entering
dry bulb is below the 26.7 C rating point, fan heat takes 2.6 to 7.4 percent of gross total capacity, and
RTU-4, the addition, fails on sensible capacity with no question about the building.

The documents also describe the building as drawn in 2004. The facilities records show, without numbers,
that a 2019 reorganisation refurnished seventeen rooms with higher headcounts following the furniture
planner's room-size rules, that the teaching lab gained instruments of unstated draw, and that the server
room has had its own split system since 2019. The standard reviews the building as it exists and the
facilities office verifies at most eight of thirty-seven items. The refurnished rooms fall into five classes
by use and size (the 14 m2 offices, the 16 m2 offices, the mid-size offices, the open offices and the
conference rooms), each changed differently, and the two lab rooms changed on their own: one verification of
each, seven in all, lets every other room be inferred, and leaving any one unverified misstates some unit's
outdoor air or loads beyond what the review accepts. The server room is settled by three concordant records.
Removing it makes RTU-1 oversized; the refurnished conference room and offices make RTU-7 undersized; the
shortfalls of RTU-3 and RTU-6 deepen. RTU-2 is the one acceptable unit and RTU-5 serves a shell space,
undetermined under section 3.2.

## Reference solution

`solution/solve.py` reads the standard's design data and tables from the docx, the schedule and envelope from
the xlsx, the zoning, scheduled airflows and selections from the submittal and the extended tables from the
catalogue pdf. It mines the facilities records for the refurnished set (the RO-2019 furniture work orders),
the lab rooms and the server room's split system; verifies the two lab rooms and the largest member of each
refurnished class (rooms 160, 161, 112, 220, 223, 110 and 144: seven verifications); applies verified values
to identical rooms and verified ratios to the others; and reviews each unit with the method above.

On the shipped instance it reproduces the District's review: RTU-1 oversized, RTU-2 acceptable, RTU-3, RTU-4,
RTU-6 and RTU-7 undersized, RTU-5 undetermined (tenant fit-out loads), submittal returned for revision. Its
largest deviation is 0.44 percent on RTU-2's block sensible load, 0.15 of that tolerance
(`authoring/evidence/reference.txt`). It reads only the shipped files and the service's reports, imports
nothing from the sealed definition or the verifier and shares no code with them, so its agreement with the
District's review is an independent check of the verifier's truth.

## Verification

`tests/grade.py` computes the District's review from the sealed as-built definition (`tests/project.py`,
`tests/project_base.py` and `tests/method.py`, the same modules that drive the verification service) and
reads `/app/review.json` strictly: a regular file, not a symlink; one JSON object without duplicate keys;
exactly the keys `units` and `submittal`; `units` holding exactly RTU-1 to RTU-7; an undetermined unit holding
exactly `verdict` and `missing`, any other unit exactly `verdict` and the eight quantities, each a finite
number (NaN, infinities, booleans, strings and nulls fail). A file that breaks any of this fails as a whole:
the 19 malformed cases in `authoring/evidence/verifier_checks.txt` all fail and the District's own review
passes.

Then, per unit: verdict exact; for determined units outdoor air and total and sensible block loads within 3
percent, latent block load within 5 percent, net total and sensible capacity within 2 percent, net latent
capacity within 5 percent, coil entering wet bulb within 0.3 K; for the undetermined unit its
missing-information code; and the submittal decision. No unit may be wrong. These thresholds are not in the
instruction, which asks for the values the standard's method gives. The record goes to
`/logs/verifier/metrics.json` and never gates. `tests/test.sh` writes reward 0 first and 1 only when pytest
exits 0 and its ctrf report holds exactly one test, passed; it locks `/logs/verifier` to root before grading
and again before the reward. The verifier runs no submitted code, so nothing of the agent's can outlive it.

The tolerances come from the spread of correct methods (`authoring/evidence/method_spread.txt`). Station
pressure taken as 101.325 kPa, the Magnus correlation, mixing by volume, 1.20/3000 air constants and
altitude-corrected constants leave outdoor air unchanged and move the coil entering wet bulb by at most 0.050
K, the total and sensible block loads by at most 0.927 and 0.472 percent, the latent block load by at most
3.357 percent, the net total and sensible capacities by at most 0.180 and 0.466 percent and the net latent
capacity by at most 1.765 percent. Every known shortcut falls outside:

| shortcut | largest miss (percent) | verdict flipped |
|---|---|---|
| AHRI-rated capacity | net total 10.063, sensible 16.010, latent 14.319 | RTU-4 |
| capacity at 19.4 C EWB, 26.7 C EDB | 6.783, 14.161, 18.039 | RTU-4 |
| no entering-dry-bulb correction | sensible 20.280, latent 68.235 | RTU-2 |
| gross capacity (no fan heat) | total 7.951, sensible 10.315 | RTU-4 |
| Ev = 1 (summed zone outdoor air) | outdoor air 20.160 (RTU-1) | none |
| simplified-procedure Ev of 0.75 | outdoor air 32.807 (RTU-4) | RTU-2 |

The 3 percent on loads and outdoor air also covers the inference of unverified rooms
(`authoring/evidence/campaign_study.txt`). The reference campaign uses at most 0.37 of any tolerance under
nine draws (seeds 0 to 8) of the plug-load drift in rooms that were not refurnished. Campaigns that leave a
deciding room unverified fail on the shipped instance, by the worst field's multiple of its tolerance:

| campaign | worst miss |
|---|---|
| no verification (record values only) | 8.4 x, RTU-3 outdoor air; RTU-7 verdict wrong |
| lab rooms unverified | 5.4 x, RTU-6 block sensible load |
| 112 unverified (14 m2 offices) | 1.6 x, RTU-7 block sensible load |
| 220 unverified (16 m2 offices) | 6.3 x, RTU-3 outdoor air |
| 223 unverified (mid-size offices) | 3.0 x, RTU-7 block sensible load |
| 144 unverified (conference rooms) | 5.8 x, RTU-7 outdoor air |
| 110 unverified (open offices) | 1.8 x, RTU-1 block total load |
| largest rooms only (110, 160, 223, 144) | 6.3 x, RTU-3 outdoor air |

Constant reviews fail (`authoring/evidence/constant_null.txt`): the contractor's figures with every unit
accepted, undersized or oversized get all seven units wrong; every unit undetermined gets six wrong; the
District's verdicts with the contractor's figures get six wrong.

## Layout

- `environment/`: one image. Documents in `/app/data`; the field-verification service in
  `environment/verify/` (installed to `/opt/verify`, owned by the `facilities` user, mode 700, budget state
  in `/var/lib/verify`, also 700); `start-verification` starts it through one sudo rule. The agent runs as
  `agent` (`[agent] user`), which cannot read the service's files or state, signal it, or reset its budget.
- `tests/`: verifier (separate, no network).
- `solution/`: reference.
- `authoring/provenance/`: the generator that wrote every document (`write_files.py`) and the sealed
  definition it reads (`project.py`, `project_base.py`, `method.py`).
- `authoring/evidence/`: `reference.py` (reference against the District's review), `method_spread.py`,
  `campaign_study.py`, `constant_null.py` and `verifier_checks.py`, each with its `.txt` output;
  `preflight.py` (bundle) and `check_instruction.py` (instruction.md).

The college, the building, the contractor, the architect, the manufacturer and every person named in the
records are fictional; the data are synthetic.
