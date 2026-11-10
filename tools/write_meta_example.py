import os
B = "/home/claude/bundle42/impeller-shrink-fits"

DIFF = """A rotating-equipment or machine design engineer does this whenever a compressor rotor is rebuilt with spare impellers: each part's bore is finish-honed to a specified diameter for the actual reground seat, and an oven temperature is chosen for shrinking it on. The aim is that the fit stays tight at overspeed, the bore stays below its allowable stress, and the part goes on without exceeding its heating limit. API 617 and the OEM practices behind plant standards like RS-3 set this out. Its research analogue is the mechanics of interference fits on high-speed rotors and the thermophysics behind them: Lame contact, centrifugal growth and hoop stress scaling with speed squared, the change of interference with running temperatures, dimensional metrology (instrument error, measurement at a temperature other than the 20 C reference), and the temperature dependence of the mean expansion coefficient. Here it has to be done with a small laboratory booking: 3 dilatometer tests must establish what the documents leave open, well enough to place each of eight bores inside a window of 7 to 12 whole micrometres. The rotor, records and laboratory are synthetic, written by authoring/provenance from a sealed definition. They are realistic, and so is the level of challenge they present:
- **The rotor:**
  - six FV520B and Ti-6Al-4V impellers, a balance drum and a thrust collar of 42CrMo4, on 95 to 125 mm seats of a 26NiCrMoV14-5 rotor, at 11200 rpm MCS;
  - seats running at 50 to 190 C;
  - heating limits of 190 to 400 C.
- **Mean expansion from 20 C (um/m K):**
  - FV520B: 10.60 to 100 C (the table's value), 11.36 to 260 C and 11.68 to 375 C, rising more slowly as the temperature rises;
  - Ti-6Al-4V: 8.60 to 100 C and 8.97 to 285 C;
  - 42CrMo4: 11.90 to 100 C, 12.30 to 220 C and 12.40 to 250 C;
  - the rotor steel: 11.40 to 100 C and 12.12 to 190 C.
  - A dilatometer reading has a repeatability of 0.3 % (one standard deviation), as the laboratory document states.
- **The seats:** they were read in the overhaul bay at 28.5 C, and the 100-125 mm micrometer reads 4 um low.
- **The windows:** every part's window is one contiguous run of whole micrometres. Hub stress at trip speed sets the top for S1, S3 and S4; clearance at the heating limit sets it for S2, S5, S6, BD and TC.

The core difficulty is that none of this is written down as a conclusion. The documents give:
- standard RS-3: the three requirements at rest and at trip speed in running, the smoothing rule, the IT5 table, friction, and that dimensions are at 20 C;
- the parts register, certificates, inspection report and readings, thermal survey, materials table (expansion to 100 C only) and the maintenance log;
- the OEM rotor data and the laboratory's one command with its booking.

What decides the result has to be found in them and in 3 tests:
- **Four materials for three tests.** Every material is needed above the table's 100 C:
  - FV520B to S6's 375 C and Ti-6Al-4V to S5's 285 C for the clearance;
  - 42CrMo4 to BD's 220 C;
  - the rotor steel at its hot seats (S3 at 190 C, BD at 180 C, S6 at 165 C).
  The rotor steel is easy to overlook: its seats look moderate next to the oven temperatures, but its expansion rises steeply. Taken from the table, it moves S3's stress-limited window about 16 um, clear of the true one, and leaves S6 and BD without a window. The way out is a line in the balance drum's certificate: the forging's mill value of 42CrMo4 expansion to 250 C. With it, 42CrMo4 needs no test. Testing 42CrMo4 instead of the rotor fails S3. Not using the mill value leaves 42CrMo4 or Ti-6Al-4V unmeasured and fails BD or S5.
- **FV520B once, at its highest limit.** A plan that tests FV520B at S2's 240 C and carries it to S6 by a straight line overstates S6's expansion, because the curve levels off, and S6 fails. Using the 375 C value flat at 240 C fails S2.
- **The seats as they are.** The bore sheet is at 20 C, but the seats were read at 28.5 C with a micrometer that reads 4 um low.
  - Taken as read at 20 C, S1, S3 and S4 fail.
  - Without the micrometer's correction, five parts fail.
  - The assembly clearance is against the seat as it stands in the bay; checked against the seat at 20 C, five parts fail.
- **The records that changed:**
  - The maintenance log resets the trip from the OEM sheet's 105 % to 110 %; at 105 %, S1, S3 and S4 exceed their stress at trip.
  - The parts register still shows S5 as FV520B; its certificate and the log show the titanium replacement.
  - S2's spare was recoated after it was certified. The log limits it to 240 C, against the certificate's 260 C.
- **The OEM spin data.** S4 was spun at 10500 rpm, not at MCS, which shows only in the table's speed column. Scaled as if at MCS, S4 exceeds its stress at trip.
- **The rest:**
  - the seat's own growth at speed has to be credited, or S3 and S4 fail for a bore placed in the middle of its window;
  - a bore placed only one standard deviation of the stated repeatability inside its clearance limit fails S5.

Each of these defeats an assumption the general approach makes on first reading:
- that the materials that matter are those of the hot parts;
- that a measured coefficient can be carried to any temperature;
- that readings are true sizes at the reference temperature;
- that the OEM sheet, the register and the certificates are current.

The gate is all 8 parts."""

SOL = """solution/solve.py is the reference; solution/solve.sh runs it in the agent's environment. It uses only the documents in /app/data and the `cte` command.

1. **The rotor as it is now:**
   - each part's material and heating limit are the certificate's, so S5 is Ti-6Al-4V (the register predates it), except S2's limit, which the maintenance log gives as 240 C after the spare was recoated;
   - the trip is 110 % of MCS, from the maintenance log (the OEM data sheet still says 105 %);
   - the OEM spin-test values are scaled to MCS from the speed each impeller was spun at (S4 at 10500 rpm).
2. **The seats.** Each reading is corrected by its micrometer's calibration error (the inspection report: M-114, for the 100-125 mm seats, reads 4 um low). The seats were read in the overhaul bay at 28.5 C, so each is referred back to 20 C with the rotor steel's expansion. The assembly clearance is checked against the corrected seat in the bay, since the rotor stands there.
3. **The model:**
   - Lame contact pressure for the part's hub ring on the solid rotor;
   - the acting interference is the geometric one less RS-3's smoothing, 0.8 (Rz bore + Rz seat);
   - at trip speed in running, the interference changes by the free thermal growth of bore and seat at the survey temperatures (either sign) and by the bore's centrifugal growth less the seat's. The bore growth is the OEM's spin-test value times (trip speed / spin-test speed)^2, or the free-ring value for the drum and collar;
   - the hoop stress of rotation at the bore is scaled the same way;
   - retention is checked at the least interference and stress at the greatest, at rest and at trip.
4. **The tests.** Every material is needed above the table's 100 C:
   - the material of each clearance-limited part (found with the table's values) at its heating limit;
   - each hub material at its running temperature;
   - the rotor steel at its hottest seat (S3, 190 C).
   That is four materials for three tests. The balance drum's certificate gives the 42CrMo4 forging's mill value to 250 C, above every 42CrMo4 temperature, so 42CrMo4 needs no test. Each other material is measured once, at the highest temperature it is needed at. Every other temperature is reached on the straight line through the table's value at 100 C and the measurement (or the mill value), never beyond a measurement. This gives the rotor steel to 190 C, FV520B to 375 C and Ti-6Al-4V to 285 C.
5. **The bores and ovens:**
   - each bore gives the top of its range less 2 um (stress-limited) or less 0.6 % of the oven expansion (clearance-limited: twice the laboratory's stated repeatability);
   - the oven is the lowest temperature that gives the clearance, plus 20 C, at most the heating limit.

**On the shipped scenario** (authoring/evidence/reference_run.txt), the reference measures 12.15 for the rotor steel, 11.70 for FV520B and 8.93 um/m K for Ti-6Al-4V, and takes 12.40 for 42CrMo4 from the certificate. All 8 parts are right, with smallest margins of +0.0841 on retention, +0.0034 on stress and +0.0191 on clearance.

**authoring/evidence/independent.py** is a second solution, written separately, with its own code and tests:
- the rotor steel to 200 C, FV520B to 400 C and Ti-6Al-4V to 290 C, with the certificate's mill value for 42CrMo4;
- the middle of the window its own model computes.

It also gets all 8 right, on the shipped seed and on all 20 laboratory seeds 5301-5320. Its smallest margins are +0.0438 on retention, +0.0055 on stress and +0.0282 on clearance."""

VER = """The deliverable is one CSV file, /app/output/bore_sheet.csv, with a bore diameter and an oven temperature for each of the 8 parts. The verifier (tests/grade_bores.py, run by tests/test_bores.py under pytest) grades it against the sealed definition in tests/sealed:
- retention at the least interference, at rest and at trip speed in running: at least 15 MPa contact pressure, and twice the stage torque with RS-3's friction;
- hub von Mises stress at the bore at the greatest interference, at rest and at trip (with the hoop stress of rotation): at most the yield strength / 1.2;
- clearance of 0.001 d against the seat as it stands in the overhaul bay, at the oven temperature, which must not exceed the part's heating limit.

The sheet is accepted only when all 8 parts are right. One pytest test carries the reward. test.sh writes 0 first, and writes 1 only when pytest exits 0 and the ctrf report shows exactly 1 test, 1 passed.

The truth comes from the sealed definition authoring/provenance/isim.py, never from running the reference, and the agent never sees it. authoring/provenance/tune.py recomputes its OEM hoop stresses and window widths from the design rules it states.

The seed (5437) drives only the laboratory's scatter. authoring/provenance/seed_screen.py chose it as the first seed from 5301 that meets three conditions (largest offset 2.46 sigma, smallest retention or clearance margin of a sound plan +0.0068; authoring/evidence/seed_screen.txt):
- no reading a plausible plan could draw is more than 2.5 standard deviations from its mean;
- the sound plans of method_spread.py all get 8 of 8;
- every defective route of route_study.py fails. Two routes can be rescued by scatter on other seeds: FV520B tested at S2's 240 C limit and extrapolated to S6 (8 of 8 on 0 to 3 of the 20 laboratory seeds), and the right tests in part order with each clearance-limited bore only one standard deviation of the stated repeatability inside its limit (17 of 20).

In the agent's container the sealed definition and the laboratory's records live under /opt/lab, in directories owned by the user lab with mode 700. The agent reaches the laboratory only through `cte`, a sudo wrapper for /opt/lab/lab.py. The program:
- validates its arguments;
- creates one exclusive record file per test;
- refuses any test beyond the booking of 3;
- refuses to run at all if its directories are not as installed.

The verifier runs in a separate container without network.

Why the gate is all 8, measured on the shipped scenario. Every number below is copied from the named file in authoring/evidence.

Every part's window is one contiguous run of 7 to 12 whole micrometres (windows.txt).

Correct methods (method_spread.txt, independent.txt). The reference and these variations all get 8 of 8 on the shipped seed:
- the tests in another order, or in part order;
- the rotor steel tested to 200 or 250 C;
- FV520B tested to 400 C;
- Ti-6Al-4V tested to 300 C;
- every part heated to its limit;
- an allowance of 1 % of the oven expansion;
- the middle of the window;
- the least of the window plus 2 um.

Their smallest margins are +0.0073 on retention, +0.0034 on stress and +0.0068 on clearance. Most pass on all 20 laboratory seeds; FV520B to 400 C passes on 16, the 1 % allowance and the least of the window plus 2 um on 17. A 2 % allowance is too large for the 7 um windows: it gets 5 of 8 and fails on every seed. The independent solution gets 8 of 8 on all 20 seeds.

Defective routes (route_study.txt; the last column counts the laboratory seeds 5301 to 5320 on which the route gets all 8):
| Route | Right of 8 | Worst part | Seeds with 8 |
|---|---|---|---|
| FV520B tested at S2's 240 C limit, extrapolated to S6 | 7 | S6 clearance -0.050 | 0 of 20 |
| the same, mid-window pick | 7 | S6 clearance -0.006 | 3 of 20 |
| the same, FV520B tested second, mid-window pick | 7 | S6 clearance -0.006 | 3 of 20 |
| the same, FV520B tested last, mid-window pick | 7 | S6 clearance -0.006 | 1 of 20 |
| 42CrMo4 tested at 220 C, the rotor steel from the table | 7 | S3 stress -0.021 | 0 of 20 |
| the same, mid-window pick | 6 | S3 stress -0.015 | 0 of 20 |
| the same, the rotor steel at the slope of 42CrMo4 | 7 | S3 stress -0.010 | 0 of 20 |
| the mill value not used: 42CrMo4 from the table | 7 | BD retention -0.240 | 0 of 20 |
| the mill value not used: a handbook 12.6 for 42CrMo4 | 6 | BD clearance -0.036 | 0 of 20 |
| the rotor steel and 42CrMo4 tested; Ti-6Al-4V from the table | 7 | S5 retention -0.131 | 0 of 20 |
| the same with a handbook 9.2 for Ti-6Al-4V | 7 | S5 clearance -0.043 | 0 of 20 |
| the 375 C FV520B reading used flat | 6 | S2 clearance -0.071 | 0 of 20 |
| no tests (the table for every material) | 2 | S6 retention -1.000 | 0 of 20 |
| seats taken as at 20 C | 5 | S4 retention -0.171 | 0 of 20 |
| clearance against the seat at 20 C | 3 | BD clearance -0.072 | 0 of 20 |
| trip at 105 % | 5 | S4 stress -0.054 | 0 of 20 |
| maintenance log not applied | 3 | S2 heating limit -1.000 | 0 of 20 |
| the micrometer's calibration error not applied | 3 | BD clearance -0.017 | 0 of 20 |
| S4's spin test taken as at MCS | 7 | S4 stress -0.071 | 0 of 20 |
| S2's heating limit from its certificate (260 C) | 7 | S2 heating limit -1.000 | 0 of 20 |
| bore 1 sd of the stated repeatability inside the clearance limit | 7 | S5 clearance -0.002 | 17 of 20 |
| seat growth not credited, mid-window pick | 6 | S4 retention -0.042 | 0 of 20 |

Every part is failed by at least 3 of the 22 routes.

No hedge across parts can pass, because the gate is all 8 (hedge_study.txt). Within a part, a bore right under both answers to a choice exists for most choices, at the edge of the window. It does not exist in these cases:
- S1, S3 and S4 with the seats taken as at 20 C;
- S2, S5, S6 and BD with the table's expansion for every material;
- S3, S6 and BD with the rotor steel from the table;
- BD with 42CrMo4 from the table, and S5 with Ti-6Al-4V from the table;
- S3 and S6 with the 375 C FV520B value used flat.

Null answers (null_baselines.txt). Each part is graded on its own, so a sheet made without the laboratory can be right on individual parts, and null_baselines.txt lists every such free pass part by part:
| Null answer | Right of 8 |
|---|---|
| 1.0 or 1.5 um of interference per mm on the seat as read | 0 |
| the best single um per mm, chosen with the truth (S2, BD) | 2 |
| the reference model with no tests, the mill value for 42CrMo4 (S1, S4, BD, TC) | 4 |
| the reference model with the table for every material (S1, S4) | 2 |
| no tests, the log not applied and the seats taken as at 20 C | 0 |

Malformed sheets are rejected as a whole (verifier_checks.txt). This covers a sheet that:
- is a symlink, empty or absent;
- has a missing, misspelt or extended header;
- has a missing, repeated or unknown part, or a part in lower case;
- has a row of the wrong length, or non-ASCII text;
- has a bore that has four decimals, is NaN, infinite, empty, text, negative, or out of range (50 to 200 mm);
- has an oven temperature that is not a whole number or is out of range (20 to 1000 C).

34 cases were run and none crashed the grader. The reference sheet is accepted with CRLF line ends, blank lines, spaces and rows in any order; an oven above the heating limit is graded wrong for that part.

The agent works as a separate user that can write only to /app/output. /app/data is read-only, and the laboratory's sealed definition and records are unreadable to the agent. The verifier runs separately without network, and /logs/verifier is root-only."""

REL = """I am a control scientist and mechanical engineer with a PhD in mechanical engineering. Rotating machinery, shrink fits of rotor components, the stress analysis of rotating rings and thick cylinders, thermal behaviour of materials, planning the few tests a job allows, and reading plant records for what has changed since the data sheets were issued are part of my work on industrial equipment and of my teaching. The rotor, materials and records are synthetic."""

COI = """I am employed by MEMC (GlobalWafers), a silicon wafer manufacturer; this task has no connection to my employer's products, processes or data. It uses only textbook machine design (shrink fits of rotor parts, Lame cylinders, rotating rings, surface smoothing, thermal and centrifugal effects on fits, dilatometry and dimensional metrology) on synthetic parts, materials and records. I also author evaluation tasks for other AI benchmark programs; this task shares no data, code or scenario with them."""

DESC = "Specify the honed bore diameter and the oven temperature for each of eight spare parts (six impellers, a balance drum and a thrust collar) shrink-fitted onto the reground seats of a centrifugal compressor rotor, so that every part meets the plant's standard for retention and hub stress at rest and at trip speed and for assembly, using a dilatometer with a booking of 3 tests, the inspection report, the thermal survey, the OEM rotor data and the maintenance log."

def tq(s):
    assert '"""' not in s
    return '"""' + s + '"""'

toml = '''schema_version = "1.4"

artifacts = ["/app/output/bore_sheet.csv"]

[task]
name = "afterquery/impeller-shrink-fits"
description = "%s"
authors = [{ name = "Alireza Bafandeh", email = "rahattar@gmail.com" }]
keywords = [
    "shrink-fit",
    "rotating-machinery",
    "centrifugal-compressor",
    "thermal-expansion",
    "test-planning",
    "metrology",
]

[metadata]
author_name = "Alireza Bafandeh"
author_email = "rahattar@gmail.com"
author_organization = "MEMC"
author_profile = "https://www.linkedin.com/in/alireza-bafandeh"
research_advisor = ""
referred_by = ""
conflicts_of_interest = "%s"
domain = "engineering-sciences"
field = "mechanical-engineering"
subfield = "rotating machinery: shrink fits"
category = "Science"
subcategory = "Mechanical & Aerospace Engineering"
tags = [
    "shrink-fit",
    "rotating-machinery",
    "centrifugal-compressor",
    "thermal-expansion",
    "test-planning",
    "metrology",
]
expert_time_estimate_hours = 5
relevant_experience = %s
difficulty_explanation = %s
solution_explanation = %s
verification_explanation = %s

[verifier]
timeout_sec = 600.0
environment_mode = "separate"

[verifier.environment]
network_mode = "no-network"

[agent]
timeout_sec = 28800.0
user = "agent"

[environment]
build_timeout_sec = 900.0
cpus = 2
memory_mb = 4096
storage_mb = 4096
gpus = 0
network_mode = "public"
''' % (DESC, COI, tq(REL), tq(DIFF), tq(SOL), tq(VER))
open(os.path.join(B, "task.toml"), "w").write(toml)

readme = """# impeller-shrink-fits

Specify the honed bore diameter (mm to 0.001 at 20 C) and the oven temperature (whole degrees C) for each of eight
spare parts of a centrifugal compressor rotor (six impellers, a balance drum and a thrust collar) shrink-fitted onto
the rotor's reground seats, so that every part meets plant standard RS-3 for retention and hub stress at rest and at
trip speed and for assembly, using a dilatometer with a booking of 3 tests (the mean expansion of a material from 20 C
to a chosen temperature), the inspection report, the thermal survey, the OEM rotor data and the maintenance log. The
deliverable is one CSV bore sheet, graded against a sealed definition of the rotor.

## Difficulty

%s

## Reference solution

%s

## Verification

%s

## Layout (for maintainers)

- `instruction.md`: the task as the agent reads it (the author's own prose).
- `environment/`: the agent's image. `data/` is installed read-only at /app/data (standard RS-3, laboratory rules,
  inspection report, OEM rotor data, parts register, certificates, seat readings, thermal survey, materials,
  maintenance log). `rig/lab.py` is the laboratory program; `rig/sealed/` (isim.py, seed.json) is installed under
  /opt/lab for the user `lab` with mode 700. The Dockerfile creates the users `agent` and `lab`, the sudo rule and the
  `cte` wrapper.
- `tests/`: the verifier image. `grade_bores.py` grades the sheet against `sealed/`; `test_bores.py` is the one pytest
  test; `test.sh` writes the reward; `app_data/` is a copy of the agent's documents.
- `solution/`: `solve.py` (the reference tests, model and pick rule) and `solve.sh`.
- `authoring/provenance/`: the sealed definition (`isim.py`), `tune.py` (the design rules for its heating limits and
  OEM hoop stresses, checked against them), the generator (`gen.py`), `build.py`, the seed (`seed.json`) and
  `seed_screen.py`, which chose it (5437; output in `authoring/evidence/seed_screen.txt`).
- `authoring/evidence/`: `route_study.py` (wrong side), `method_spread.py` and `independent.py` (right side),
  `null_baselines.py`, `hedge_study.py`, `windows.py` (every part's window and what bounds it), `verifier_checks.py`,
  `reference_run.py`, `preflight.py`, and their `.txt` outputs; `common.py` emulates the laboratory, including its
  deterministic scatter, so the numbers are those of the shipped scenario.

## Regenerating

    python3 authoring/provenance/tune.py             # checks the sealed limits and hoop stresses
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
tests/grade_bores.py. `common.py` gives exactly the readings lab.py gives for the same tests in the same order.

Packages: numpy 2.1.3, scipy 1.14.1, pandas 2.2.3 (environment and verifier), pytest 8.4.1 and pytest-json-ctrf
0.3.5 (verifier).

## Changing the task

- The materials and their expansion curves (`MAT`), the friction and retention pressure (`MU`, `P_MIN`), the bay
  temperature, speeds and trip (`T_BAY`, `MCS`, `TRIP`), the IT grades, the micrometer error (`MIC_ERR`), the parts
  (`PARTS`, with S4's spin-test speed) and the laboratory's booking and scatter (`BUDGET`, `NOISE_CTE`) live in
  `authoring/provenance/isim.py`; the documents' text, the stale register, OEM trip and S2 certificate limit, the mill
  value and the maintenance log in `gen.py`. After a change to geometry, materials or limits, rerun
  `tune.py` and copy the values it prints into `PARTS`; then run `build.py`, regenerate the evidence, and check that
  `route_study.txt` still fails the defective routes while `method_spread.txt` and `independent.txt` get 8 of 8.
- Keep FV520B's mean expansion concave, so that a straight line from 100 C through its value at S2's limit overstates
  it at S6's limit by more than S6's window, and keep the windows of S5, BD and TC narrower than the error of the
  20-100 C value and of usual handbook values at their limits (`windows.txt`). Keep the rotor steel's expansion
  rising steeply enough, and S3's seat hot enough, that the 20-100 C value moves S3's window clear of the true one,
  and keep the 42CrMo4 mill value in the balance drum's certificate. That is what makes the booking hold exactly the
  plan that measures the rotor steel, FV520B at its highest limit and Ti-6Al-4V.
- The seed drives only the laboratory's scatter. After any change to the scenario, rerun `seed_screen.py` and ship the
  seed it chooses.
- Keep the documents free of any statement of the effects: that the expansion coefficient rises and levels off, that
  the seat readings must be referred to 20 C or corrected for the micrometer, that the OEM trip or S2's certificate
  is out of date, that the rotor steel needs a test. RS-3 does say that dimensions are at 20 C and that clearance is
  against the seat as it stands in the overhaul bay; the inspection report gives the bay temperature and the
  micrometers' calibration; the OEM table gives each spin-test speed; the materials table says its expansion is the
  20-100 C mean.
- Modelling note: plane-stress Lame rings of the hub's outside diameter on a solid rotor, the smoothing of DIN 7190,
  the free thermal growth of bore and seat at the survey temperatures, the OEM's free bore growth and hoop stress
  scaled with speed squared from the spin-test speed (free-ring values for the drum and collar), the seat's centrifugal growth as a solid
  shaft. Hub geometry beyond the ring, temperature gradients, yield strength at temperature and the cooling of the
  part during fitting are not modelled.
""" % (DIFF, SOL, VER)
open(os.path.join(B, "README.md"), "w").write(readme)
print("written")
