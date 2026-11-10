# shrink-fit-hubs

Specify the mean diametral interference (whole micrometres) and the oven temperature (whole degrees C) for each of
twelve hubs shrink-fitted back onto their shafts after an overhaul, so that every joint meets plant standard ST-9 for
torque, hub stress and assembly at rest and in steady running, using a joint laboratory with a booking of 8 tests
(friction of shrink-fitted or pressed specimens at a chosen contact pressure; mean expansion to a chosen temperature),
the joint records, the thermography and the maintenance log. The deliverable is one JSON file, graded against a sealed
definition of the joints.

## Difficulty

A maintenance or machine design engineer does this whenever keyless hubs come off their shafts for an overhaul: for each joint a mean interference is chosen for the shaft and bore to be machined to, and an oven temperature for fitting, so that the joint carries its peak torque by friction with the plant's margin, the hub bore stays below its allowable stress and the hub goes on without exceeding its heating limit. DIN 7190 sets out the calculation and plant standards like ST-9 adopt it. Its research analogue is the mechanics of interference fits: Lame thick-cylinder contact, the smoothing of surface roughness on fitting, the change of interference with running temperatures and speed, and the friction of shrink-fitted joints, which depends on the hub material, the surface preparation and the assembly method and falls as contact pressure rises. Here it has to be done with a small laboratory booking: 8 tests must establish what the documents leave open, well enough to place each of twelve interferences inside a window of 8 to 35 whole micrometres. The joints, records and laboratory are synthetic, written by authoring/provenance from a sealed definition. They are realistic, and so is the level of challenge they present:
- Twelve joints from 45 to 220 mm shaft diameter: steel, ductile iron, tin bronze and aluminium hubs, dry, oiled or with MoS2 paste, on solid and hollow steel shafts, at 25 to 5900 rpm. Contact pressures at the least interference run from 22 to 131 MPa, and peak torques from 220 to 87 450 N m.
- Friction falls with contact pressure as (p / 50 MPa)^-0.25, from 0.18 to 0.055 at the joints' own pressures. A slip test reads with 1.2 % scatter and a dilatometer reading with 0.8 %.
- Steel's mean expansion coefficient from 20 C is 11.90 um/m K to 100 C (the table's value), 12.45 to 270 C and 12.48 to 280 C.
- In steady running J01 and J12 gain 22.8 and 16.1 um of interference, because their shafts run hotter than their hubs. J02, J03 and J05 lose 47.8, 36.3 and 40.7 um.
- Every window is one contiguous run of whole micrometres.

The core difficulty is that none of this is written down. The documents give:
- standard ST-9: the three requirements, at rest and in steady running; the smoothing rule; the IT5/IT6 table;
- the joint register, hub certificates, assembly sheets, duty list and thermography, all written before the maintenance log's later entries;
- the maintenance log, the materials table (expansion to 100 C only) and the laboratory's two commands with its booking.

What decides the result has to be found in them and in 8 tests:
- The top of each window is exact once the right physics is in place, and placing the interference there makes the uncertain friction harmless. The physics that sets the top is what the general approach gets wrong.
- J01 and J12 gain interference in running. Their hub stress is greatest in running, not at rest, and their windows sit 23 and 16 um below where an at-rest stress check puts them. With the stress checked at rest only, or the thermal change taken as a loss, J01 and J12 fail.
- J04, J06 and J09 are limited by clearance at heating limits of 270 to 280 C. Steel's expansion to 100 C understates its mean expansion to those temperatures by 4.6 to 4.9 %; with the table value J06 has no feasible interference, and J04, J06 and J09 fail. A handbook figure of 12.8 or 13.0 overstates it, and J04 and J09 (with J06 at 13.0) fail on clearance. The steel expansion has to be measured. The single reading carries the dilatometer's scatter, so an interference placed exactly at the clearance limit can fail on it.
- The booking holds one slip test of each of the seven hub material and preparation pairs in use plus that one dilatometer test, and nothing more. A second slip test, to see how friction moves with pressure, has to be paid for by leaving a pair or the expansion unmeasured.
- For an interference placed inside the window rather than at its top, the friction must be right at the joint's own pressure. With every pair tested at 80 MPa and the middle of the window, J09 fails. With each pair tested at the pressure of its lowest-pressure joint, J04, J06, J09 and J11 fail. With handbook friction, 8 of 12 are right.
- The maintenance log changes three joints. J10's shaft is now hollow (40 mm bore), which lowers the contact pressure: missed, J10 slips, whatever the friction. J07 is now on MoS2 paste and J11's motor went from 55 to 75 kW: missed, they fail for an interference placed by the friction rather than at the top.

Each of these defeats an assumption the general approach makes on first reading: that running only loosens a joint, that a 20-100 C expansion coefficient serves at oven temperature, that one friction coefficient per surface serves at every pressure, and that the register is current. The gate is all 12 joints.

## Reference solution

solution/solve.py is the reference; solution/solve.sh runs it in the agent's environment. It uses only the documents in /app/data and the `slip` and `cte` commands.

1. The joints as they are now: the records with the maintenance log applied. J10's shaft is hollow with a 40 mm bore, J11's peak torque is scaled by 75/55, and J07 is fitted with MoS2 paste.
2. The model:
   - Lame contact pressure for the hub on its solid or hollow shaft.
   - The acting interference is the geometric one less ST-9's smoothing, 0.8 (Rz bore + Rz shaft). In steady running it changes by the free thermal growth of bore and shaft at the thermography temperatures, with either sign, and by the centrifugal growth of hub and shaft.
   - The spinning hub adds hoop stress at the bore.
   - Torque is checked at the least interference and stress at the greatest, each at rest and in running.
3. Test 1 is `cte steel 275`. Steel's mean expansion is then taken as linear in T between the table's 20-100 C value and the measurement. The other hubs use the table value, which errs low.
4. Each mean interference is the top of its range, from stress and from clearance at the heating limit. It is placed 1 um below the top where stress sets it, and 2 % of the oven expansion below where clearance does, to allow for the scatter of the one reading. That is where the friction torque is greatest.
5. The oven temperature is the lowest that gives the clearance, plus 20 C, and at most the heating limit.
6. Tests 2-8 measure the friction of each pair in use, shrink-fitted, at the contact pressure of the pair's lowest-pressure joint, and report each joint's torque margin with it.

On the shipped scenario the reference measures 12.58 um/m K for steel to 275 C. Its results (authoring/evidence/reference_run.txt):
- interferences of J01 60, J02 190, J03 141, J04 289, J05 131, J06 118, J07 140, J08 216, J09 461, J10 155, J11 261 and J12 43 um;
- every joint right;
- smallest margins +0.0378 on torque (J06), +0.0046 on stress and +0.0122 on clearance (J09).

authoring/evidence/independent.py is a second solution, written separately, and it also gets all 12 right, on the shipped seed and on all 20 laboratory seeds 7101-7120.
- Its tests: steel's expansion to 270 C; steel/dry at two pressures, giving a fitted friction exponent of 0.268; one test of each other pair except ductile iron with paste, taken by the dry ductile-iron/steel ratio.
- Its rule: the middle of the window its own model computes.
- Its smallest margins are +0.0287 on torque, +0.0037 on stress and +0.0118 on clearance.

## Verification

The deliverable is one JSON file, /app/output/fits.json, with a mean interference and an oven temperature for each of the 12 joints. The verifier (tests/grade_fits.py, run by tests/test_fits.py under pytest) grades it against the sealed definition in tests/sealed:
- torque at the least interference, at rest and in steady running, at least 1.5 times the peak torque, with friction at the joint's own contact pressure;
- hub von Mises stress at the bore at the greatest interference, at rest and in steady running (with the spinning hub's hoop stress), at most the yield strength divided by 1.2;
- clearance of 0.001 d at the greatest interference at the oven temperature, which must not exceed the hub's heating limit.

The answer is accepted only when all 12 joints are right. One pytest test carries the reward; test.sh writes 0 first, and writes 1 only when pytest exits 0 and the ctrf report shows exactly 1 test, 1 passed.

The truth comes from the sealed definition authoring/provenance/sfsim.py, never from running the reference, and the agent never sees it. authoring/provenance/tune.py recomputes its peak torques and yield strengths from the design rules it states.

The seed (7101) drives only the laboratory's scatter. authoring/provenance/seed_screen.py chose it as the first seed from 7101 on which nine sound plans all get 12 of 12 with at least 0.3 % to spare and no reading they draw is more than 2.5 standard deviations from its mean (smallest margin +0.0036, largest offset 1.63 sigma; authoring/evidence/seed_screen.txt).

In the agent's container the sealed definition and the laboratory's records live under /opt/lab, in directories owned by the user lab with mode 700. The agent reaches the laboratory only through `slip` and `cte`, sudo wrappers for /opt/lab/lab.py. The program:
- validates its arguments;
- creates one exclusive record file per test;
- refuses any test beyond the booking of 8;
- refuses to run at all if its directories are not as installed.

The verifier runs in a separate container without network.

Why the gate is all 12, measured on the shipped scenario. Every number below is copied from the named file in authoring/evidence.

Every joint's window is one contiguous run of 8 to 35 whole micrometres (windows.txt).

Correct methods (method_spread.txt, independent.txt): the reference and its variations all get 12 of 12 on the shipped seed:
- the dilatometer test last, or steel measured to 260, 270, 280 or 300 C instead of 275;
- the friction tested at each pair's highest or median pressure, or at 80 MPa;
- every hub heated to its limit;
- an allowance of 1.5 % or 3 % of the oven expansion;
- the middle of the window, with friction from each pair's highest or median pressure;
- no slip test at all.

They do so with at least +0.0101 to spare on torque, +0.0036 on stress and +0.0053 on clearance, and on 15 to 20 of the 20 laboratory seeds (the 3 % allowance on 15 of 20, steel to 280 C on 19 of 20). The independent solution gets 12 of 12 on all 20 seeds.

Defective routes (route_study.txt; the last column counts the scatter seeds 7101 to 7120 on which the route gets all 12):
| Route | Right of 12 | Worst joint | Seeds with 12 |
|---|---|---|---|
| J10 log missed (solid shaft) | 11 | J10 torque -0.049 | 0 of 20 |
| J07 log missed, friction at each pair's highest pressure, mid-window | 11 | J07 torque -0.086 | 0 of 20 |
| J11 log missed, friction at each pair's highest pressure, mid-window | 11 | J11 torque -0.040 | 0 of 20 |
| hub stress at rest only | 10 | J01 stress -0.183 | 0 of 20 |
| thermal change in running as a loss only | 10 | J01 stress -0.183 | 0 of 20 |
| steady running ignored | 10 | J01 stress -0.183 | 0 of 20 |
| smoothing not deducted, mid-window pick | 11 | J07 torque -0.006 | 10 of 20 |
| steel expansion from the 20-100 C table | 9 | J06 torque -0.056 | 0 of 20 |
| steel expansion assumed 12.8 / 13.0 | 10 / 9 | J09 clearance -0.006 / -0.021 | 0 / 0 of 20 |
| friction at 80 MPa, mid-window / least + 3 um | 11 / 8 | J09 torque -0.002 / -0.077 | 3 / 0 of 20 |
| friction at each pair's lowest pressure, mid-window | 8 | J09 torque -0.068 | 0 of 20 |
| handbook friction, mid-window / least + 3 um | 8 / 3 | J09 torque -0.077 / -0.237 | 0 / 0 of 20 |

The J07 and J11 log facts, and the smoothing, decide the result only for an interference placed by the friction. With the top of the range they pass (route_study.txt).

No hedge across joints can pass, because the gate is all 12 (hedge_study.txt). Within a joint, a common interference right under both answers to a choice exists for most choices, at the edge of the window. It does not exist for J06 with the table expansion, or for J10 with a solid shaft.

Null answers (null_baselines.txt). Each joint is graded on its own, so an answer made without the laboratory can be right on individual joints, and null_baselines.txt lists every such free pass joint by joint:
| Null answer | Right of 12 |
|---|---|
| 1.0 um per mm of diameter | 1 |
| the best single um per mm, chosen with the truth | 2 |
| the top of the range with the table expansion and no tests | 9 |
| handbook friction with the table expansion, mid-window | 7 |
| the same with the log not applied | 5 |

None gets J04 or J06.

Malformed results are rejected as a whole (verifier_checks.txt). This covers a result that:
- is a symlink, empty or absent;
- is not JSON, or not one object with the single key fits;
- has duplicate, missing, extra or misspelt joint keys;
- has an entry that is not an object of exactly interference_um and heating_C;
- has a value that is NaN, infinite, not a whole number, a boolean, a string, an array, an object or null, or is out of range (1 to 2000 um, 20 to 1000 C).

35 cases were run and none crashed the grader. The reference result is accepted with integers or integral floats; an oven above the heating limit is graded wrong for that joint.

The agent works as a separate user that can write only to /app/output. /app/data is read-only, and the laboratory's sealed definition and records are unreadable to the agent. The verifier runs separately without network, and /logs/verifier is root-only.

## Layout (for maintainers)

- `instruction.md`: the task as the agent reads it (the author's own prose).
- `environment/`: the agent's image. `data/` is installed read-only at /app/data (standard ST-9, laboratory rules,
  joint register, hub certificates, assembly sheets, duty list, thermography, materials, maintenance log).
  `rig/lab.py` is the laboratory program; `rig/sealed/` (sfsim.py, seed.json) is installed under /opt/lab for the
  user `lab` with mode 700. The Dockerfile creates the users `agent` and `lab`, the sudo rule and the `slip` and
  `cte` wrappers.
- `tests/`: the verifier image. `grade_fits.py` grades the result against `sealed/`; `test_fits.py` is the one
  pytest test; `test.sh` writes the reward; `app_data/` is a copy of the agent's documents.
- `solution/`: `solve.py` (the reference tests, model and pick rule) and `solve.sh`.
- `authoring/provenance/`: the sealed definition (`sfsim.py`), `tune.py` (the design rules for its peak torques and
  yield strengths, checked against them), the generator (`gen.py`), `build.py`, the seed (`seed.json`) and
  `seed_screen.py`, which chose it (7101; output in `authoring/evidence/seed_screen.txt`).
- `authoring/evidence/`: `route_study.py` (wrong side), `method_spread.py` and `independent.py` (right side),
  `null_baselines.py`, `hedge_study.py`, `windows.py` (every joint's window and what bounds it), `verifier_checks.py`,
  `reference_run.py`, `preflight.py`, and their `.txt` outputs; `common.py` emulates the laboratory, including its
  deterministic scatter, so the numbers are those of the shipped scenario.

## Regenerating

    python3 authoring/provenance/tune.py             # checks the sealed peak torques and yield strengths
    python3 authoring/provenance/build.py            # environment/data, environment/rig/sealed, tests/sealed, tests/app_data
    python3 authoring/evidence/reference_run.py      # each evidence script prints its .txt (redirect it beside the script)
    python3 authoring/evidence/windows.py
    python3 authoring/evidence/route_study.py
    python3 authoring/evidence/method_spread.py
    python3 authoring/evidence/independent.py
    python3 authoring/evidence/null_baselines.py
    python3 authoring/evidence/hedge_study.py
    python3 authoring/evidence/verifier_checks.py
    python3 authoring/provenance/seed_screen.py      # only after a change to the scenario
    python3 authoring/evidence/preflight.py          # offline structural checks

`reference_run.txt` is solution/solve.py run against environment/rig/lab.py itself with the shipped seed, graded by
tests/grade_fits.py. `common.py` gives exactly the readings lab.py gives for the same tests in the same order.

Packages: numpy 2.1.3, scipy 1.14.1, pandas 2.2.3 (environment and verifier), pytest 8.4.1 and pytest-json-ctrf
0.3.5 (verifier).

## Changing the task

- The materials (`MAT`), the friction law (`MU50`, `KF`, `PRESS_FACTOR`), the IT grades, the joints (`JOINTS`) and
  the laboratory's booking and scatter (`BUDGET`, `NOISE_MU`, `NOISE_CTE`) live in
  `authoring/provenance/sfsim.py`; the documents' text, the stale register, assembly sheet and duty list, and the
  maintenance log in `gen.py`. After a change to the geometry, materials or limits, rerun `tune.py` and copy the
  values it prints into `JOINTS`; then run `build.py`, regenerate the evidence, and check that `route_study.txt`
  still fails the defective routes while `method_spread.txt` and `independent.txt` get 12 of 12.
- Keep J04, J06 and J09 clearance-limited at their heating limits with steel's mean expansion to those temperatures
  at least about 4 % above the table's 20-100 C value and below the usual handbook 12.8-13.0, and keep J01 and J12's
  running gain larger than their windows (`windows.txt`).
- The seed drives only the laboratory's scatter. After any change to the scenario, rerun `seed_screen.py` and ship the
  seed it chooses.
- Keep the documents free of any statement of the effects: that friction depends on contact pressure, that the
  expansion coefficient rises with temperature, that a hotter shaft raises the hub stress in running, that the
  register, sheets or duty list are out of date. ST-9 does say that the requirements apply at rest and in steady
  running and gives the smoothing rule; the materials table does say its expansion is the 20-100 C mean.
- Modelling note: plane-stress Lame cylinders of the hub's full length, the smoothing of DIN 7190, the free thermal
  growth of bore and shaft at the steady-running temperatures, centrifugal growth and hoop stress of a free disc,
  friction as a power law of contact pressure. Edge effects at the hub ends, temperature gradients in the hub, yield
  strength at temperature and the cooling of the hub during fitting are not modelled.
