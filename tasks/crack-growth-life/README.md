# crack-growth-life

Set a re-inspection interval for each of sixteen weld-toe fatigue cracks in the booms and towers of two grab ship
unloaders, between 40 and 50 percent of the crack's remaining life, using five test slots in a materials laboratory
(a Paris test takes one, a threshold test three), the plant's records and BS 7910. The deliverable is one JSON file of
intervals, graded against a sealed definition of the cracks, the steels and the loading.

## Difficulty

A structural integrity engineer does this when fatigue cracks found at welded details of a crane, a bridge or an offshore structure are left in service under monitoring: each crack's remaining life is estimated by fracture-mechanics crack growth to BS 7910, and its re-inspection interval is set as a fraction of that life until the repair can be made. Its research analogue is the characterisation of a steel's fatigue crack growth for life prediction: ASTM E647 testing across load ratios and heats to identify crack closure, the threshold and heat-to-heat scatter (Elber; Newman; the NASGRO equation), combined with weld-toe stress intensity solutions (Maddox; the PD 6493 and BS 7910 Mk factors) to predict the lives of welded joints. Here it has to be done as a small design of experiments: five laboratory slots and two field records must identify a growth law whose dependence on load ratio and on the plate's heat decides most of the sixteen lives, well enough to predict each within about 11 percent. The cracks, loading, records and laboratory are synthetic, written by authoring/provenance from a sealed definition. They are realistic, and so is the level of challenge they present:
- The flanges are S355J2 plate (heats H1, H2) and S460NL plate (H3, H4), 16 to 50 mm thick, with certificate yields from 372 to 501 MPa and Kmat from 110 to 150 MPa sqrt(m). The cracks are 1.5 to 7 mm deep at the toes of stiffeners, lugs, brackets, cleats and diaphragms, and their remaining lives run from 2 to 26 months.
- Heat H1 grows at 8e-12 (U dK)^3.1 (1 - dKth/dK)^0.5 (m/cycle, MPa sqrt(m)), below BS 7910's mean + 2 SD simplified law (1.65e-11 dK^3), as a mean curve should be. Crack closure is linear in R, U = 0.65 + 0.875 R, and ends at R 0.40, below the R 0.5 at which BS 7910 splits its curves: a crack at R 0.1 grows 0.39 times as fast as a closure-free one, within what ASTM E647 testing of structural steels shows. The threshold follows BS 7910's recommended line 5.38 - 6.77 R at low R and levels off at 2.4 MPa sqrt(m), above BS 7910's floor of 2.0.
- The other heats grow faster at the same U dK: H2, the same grade as H1, 1.25 times; the S460NL heats 1.35 times. Differences between heats and grades of this size are common, and they lie inside the scatter that BS 7910's single upper-bound law for ferritic steels covers.
- Weld-toe residual stress is BS 7910's: yield as welded; 20 percent of yield transverse to the weld after furnace PWHT (its value parallel to the weld is 30 percent); no credit for vibratory stress relief; and as welded for an attachment welded on site after the member's PWHT. Stress cycles rise from the dead load, so the as-welded cracks sit at R 0.65 to 0.95, closure-free, and the furnace-PWHT cracks on the tower legs, under compressive dead load, at R 0.19 to 0.65.
- The loading is a 35-day strain-gauge survey with the usual complications: unloader 1 was out of service for 7 of the days, and unloader 2 later received a heavier grab (loaded weight x1.25), so its ranges rise and, at the berth conveyor's fixed throughput, its grab cycles fall to 0.8.
- The laboratory reports rates with 8 percent log-normal scatter and tests any of the four heats. It keeps Kmax below 75 MPa sqrt(m), so a Paris test at high R covers only low dK (4 to 15 MPa sqrt(m) at R 0.8) and one at R 0.9 reaches the near-threshold region. It allows 5 slots, and a threshold test takes 3.

The core difficulty is that none of this is written down. The documents give:
- procedure FA-3, which says to follow BS 7910, that R counts the weld-toe residual stress at BS 7910's level, and how repairs are ground;
- the register, certificates, TOFD depths, survey counts and the maintenance log;
- a handbook with BS 7910's simplified law and recommended threshold and the Tada edge-crack factor, but no Mk;
- the laboratory's rules;
- the records of two earlier cracks, both as welded: E01 on heat H1 and E02 on heat H2.

What decides the lives has to be inferred from them and from five tests:
- BS 7910 uses one law for all ferritic steels, and the laboratory's default specimen is heat H1. Four cracks are in S460NL plate (C04, C07, C10, C13). Testing H1 alone, however well, leaves them 34 to 37 percent too long-lived and 12 of 16 right. One test on S460NL plate at a closure-free R measures the difference.
- The two records check the closure-free law, Mk and the count arithmetic. E01 agrees with a correct H1 model within 1 percent, and E02 needs 1.24 times its rate; heat H2 grows faster, and six cracks are on H2. Taking H2 as H1 leaves 12 right. One factor fitted to both records leaves 10, and putting E02's misfit down to Mk (E02 is the one record with L/T above 2) leaves 10.
- Both records' depth at repair is the depth of the repair groove, which FA-3 grinds 1 mm past the crack. Read as the crack depth, the records ask for 1.28 times the true rate, and a model scaled to them gets no crack right.
- Where closure ends is a property of the steel. A second H1 test at BS 7910's R 0.5 split finds the steel closure-free there and leaves open where it became so. A line through the tests then puts the end at 0.5 and makes the stress-relieved cracks' lives up to 21 percent too long (11 of 16). Plans with one H1 test below the end and one above fail the same way (9 to 14), and so does interpolating the rate between the tested R without a closure law (8 to 11). Two H1 tests inside the closure band are needed.
- A threshold test takes 3 of the 5 slots and matters little here: the cracks' larger ranges are well above the threshold, and a Paris test at R 0.9 gives the near-threshold shape. A plan that spends 3 slots on it cannot resolve both closure and the heats (9 to 12).
- After PWHT, BS 7910's residual stress transverse to the weld is 0.2 yield. Its value parallel to the weld (0.3 yield), or none at all, loses 5 cracks (11). The yield it scales is the certificate's: the grades' specified minimum yields lower the PWHT cracks' residual stress by up to 8 MPa (heat H2) and lose 2 (14).
- The log's site welds after PWHT, its VSR entries, the survey outage and the grab change are each needed: missing any one leaves 7 to 14.
- BS 7910's Mk is not in the handbook. Without it, held constant, or with L as the attachment thickness alone, 2 to 5 cracks are right, and a rate factor fitted to the records does not repair it (1 to 5).

Each of these defeats an assumption that an assessor's general approach takes for granted on first reading: one law for the steel, the default specimen, a threshold test, BS 7910's R split, the records as a calibration. The gate is all 16: with one miss allowed, an assessment that never resolves an untested heat could split its two cracks between the two candidate rates and pass.

## Reference solution

solution/solve.py is the reference; solution/solve.sh runs it in the agent's environment. It uses only the documents in /app/data and the `fcgr` command.

1. Tests (all 5 slots, all Paris tests):
   - Two on heat H1 inside the stress-relieved cracks' closure band, at R 0.20 and 0.35.
   - One at R 0.45 for the closure-free Paris curve.
   - One at R 0.90, which the Kmax limit holds to dK 2 to 7.5, for the near-threshold shape.
   - One on S460NL plate (heat H4, R 0.70, closure-free). Heat H3, of the same grade, is taken to grow like H4.
   - No threshold test: it would take three slots, and the cracks' larger ranges are well above the threshold.
2. One fit to all five reports (scipy least squares on log rates): da/dN = G C (U(R) dK)^m (1 - dKth(R)/dK)^p.
   - Closure is linear in R, U = min(1, U0 + k R) (Elber's form).
   - The closure-free threshold is fitted to the R 0.90 data, and BS 7910's line 5.38 - 6.77 R is used where that is higher.
   - G is a factor for the S460NL plate.
3. Heat H2 was not tested, so its rate comes from E02, the earlier crack on H2. Both records are read as FA-3 describes the repair: crack depth at repair = excavation depth less 1 mm. The fitted law reproduces E01 (H1) within 1 percent (x0.993) and needs 1.242 times its rate for E02. The heat factors are H2 1.242 and H3/H4 1.335, and the fit gives m 3.089, p 0.632, a closure-free threshold of 2.29, U0 0.643, and closure-free from R 0.403 (authoring/evidence/reference_run.txt).
4. For each crack:
   - K = Mk Y S sqrt(pi a), with BS 7910's 2D Mk for a transverse attachment (L = attachment thickness + 2 fillet legs, held at its L/T = 2 value beyond 2, Mk >= 1).
   - Residual stress follows BS 7910: yield as welded; 0.2 yield after furnace PWHT, transverse to the weld; no credit for vibratory stress relief; as welded where the log shows an attachment welded on site after the PWHT.
   - R is taken per stress range from the dead load and the residual stress.
   - Unloader 2's ranges are raised by the ratio of the loaded grab weights.
   - Growth, at the heat's factor, is integrated from the inspected depth to the critical depth: where the dead-load stress plus the largest range reaches Kmat, or half the flange thickness.
5. Cycles per month are the survey's counts over the days each unloader actually operated during it (unloader 1 was out of service for 7 of the 35), times 25 operating days. Unloader 2's are also scaled by old payload / new payload, since the berth conveyor fixes the throughput.
6. The interval is 0.447 (the geometric middle of 0.40 and 0.50) times the remaining life.

On the shipped scenario the reference gets all 16 cracks right, with intervals from 0.4454 to 0.4579 of the true life (authoring/evidence/reference_run.txt).

authoring/evidence/independent.py is a second solution with its own campaign and its own fit, and it also gets 16 of 16, with intervals at 0.432 to 0.460 of the true life.
- Its campaign is heat H1 at R 0.10, 0.25 and 0.90, heat H2 at R 0.50 (measured rather than read from E02), and heat H4 at R 0.90.
- Its fit is a closure law with its end fitted, a threshold that rises with the same closure at low R, and a factor for each tested heat.

## Verification

The deliverable is one JSON file, /app/output/intervals.json, with a re-inspection interval in months for each of the 16 cracks. The verifier (tests/grade_intervals.py, run by tests/test_intervals.py under pytest) grades it against the sealed definition in tests/sealed.
- For each crack it integrates the sealed growth law, at the crack's heat, from the inspected depth to the critical depth under the future loading, giving the true remaining life in months.
- It calls the interval right when it lies between 0.40 and 0.50 of that life, inclusive.
- The assessment is accepted only when all 16 are right.
- One pytest test carries the reward. test.sh writes 0 first, and writes 1 only when pytest exits 0 and the ctrf report shows exactly 1 test, 1 passed.

The truth comes from the sealed definition authoring/provenance/fcgsim.py, which gen.py writes out, never from running the reference, and the agent never sees it. The seed (9704) drives only the laboratory's scatter. authoring/provenance/seed_screen.py chose it from 9101-10100 so that no test on the R grid, in any slot and on any heat, is a scatter outlier (largest offset 2.58 sigma; 9101 had an S460NL test 3.46 sigma high), and so that five sound solutions all get 16 of 16 (authoring/evidence/seed_screen.txt). In the agent's container the sealed definition and the laboratory's slot records live under /opt/lab, in directories owned by the user lab with mode 700. The agent reaches the laboratory only through `fcgr`, a sudo wrapper for /opt/lab/fcgr.py. The wrapper:
- validates its arguments, including the heat;
- creates one exclusive record file for each slot used (a threshold test uses three);
- refuses any test that would exceed 5 slots;
- refuses to run at all if its directories are not as installed.

The verifier runs in a separate container without network.

Why a window of 0.40 to 0.50 and a gate of 16, measured on the shipped scenario. Every number below is copied from the named file in authoring/evidence.

Correct methods (method_spread.txt, independent.txt):
| Method | Right of 16 | Interval / true life | File |
|---|---|---|---|
| reference, interval 0.447 x life | 16 | 0.446-0.457 | method_spread.txt |
| reference, interval 0.430 or 0.460 x life | 16 | 0.429-0.471 | method_spread.txt |
| reference, reversed test order (other scatter draws) | 16 | 0.439-0.473 | method_spread.txt |
| reference tests, threshold scaled by the Paris closure, or one threshold for every R | 16 | 0.442-0.457 | method_spread.txt |
| other campaigns with one or two S460NL tests and H2 from E02 (four plans, one of four slots) | 16 | 0.429-0.478 | method_spread.txt |
| H2 tested in the laboratory instead of read from E02 | 16 | 0.441-0.465 | method_spread.txt |
| independent solution (other campaign, other fit, H2 measured) | 16 | 0.432-0.460 | independent.txt |

Defective methods (route_study.txt):
| Route | Right of 16 |
|---|---|
| H1 only (threshold .85 and Paris .10 .30, or five Paris tests), S460NL taken as H1 | 12 |
| reference tests, H2 taken as H1 (E02 only a check) | 12 |
| reference tests, H2 as H1, one rate factor fitted to both records | 10 |
| reference tests, H2 as H1, E02's misfit put down to Mk past L/T = 2 | 10 |
| reference tests, one law for every heat | 9 |
| threshold test plus one H1 and one S460NL Paris test | 9 / 11 |
| second H1 test at BS 7910's R 0.5 split | 11 |
| one H1 test well below and one above the end of closure (R .05 and .60) | 9 |
| both S460NL heats tested, but one H1 test in the closure band | 14 |
| R effect interpolated between the tested R, no closure law (two campaigns) | 8 / 11 |
| Walker R-correction / Newman closure function | 9 / 13 |
| PWHT residual stress 0.3 yield, or none | 11 / 11 |
| residual stress from the grades' specified minimum yields | 14 |
| survey counts over all 35 days | 7 |
| unloader 2's cycles kept, or no grab change | 9 / 9 |
| grab change on unloader 2's boom only | 11 |
| site welds after PWHT missed / VSR credited | 14 / 14 |
| no Mk / Mk held constant / L = attachment thickness / Mk uncapped | 2 / 2 / 5 / 13 |
| no Mk / Mk held constant, rate factor fitted to the records | 5 / 1 |
| the records read with the excavation depth as the crack depth | 0 |
| handbook law, no tests (as is / scaled to the records) | 0 / 6 |

- Correct methods land at 0.429 to 0.478 of the true life on every crack, inside the window. This holds whether the closure law comes from two or three tests below its end, whether the threshold at low R comes from BS 7910's line or from the Paris closure, whether the S460NL factor comes from one heat or both, and whether H2 is read from E02 or measured.
- The window of 0.40 to 0.50 is the band a re-inspection interval is set in, and it admits about 11 percent error in life either way.
- The gate is all 16, because one allowed miss would pay for a hedge (hedge_study.txt). An assessment that leaves a choice unresolved can split the cracks the choice affects between its two answers, so that whichever is true only one crack is wrong. At a gate of 15 that passes for an untested heat (taken as its grade-mate or as H1), for BS 7910's two PWHT levels, for the VSR credit and for the site welds. At 16 every such split fails, at 15 of 16.
- The one choice a hedge survives at 16 is the yield the residual stress scales, certificate or specified minimum. On the cracks it affects its two lives differ by only 1.04 to 1.11, so one interval fits both without splitting any crack, and the hedge still needs every other part of the model right.
- Every correct method in the table gets all 16, with every interval at least 2 percent of the life inside the window's edges. Every route that misses a heat's rate, the end of closure, the PWHT residual level, a record of the log or the weld-toe Mk loses at least two cracks.

Null answers and per-crack discrimination (null_baselines.txt, route_study.txt). Each crack has its own window, so a trial-free answer can land on individual cracks, and null_baselines.txt lists every such free pass crack by crack. The trial-free answers tried are:
- the handbook law, as is or scaled to the records (at face value or read as FA-3 describes), with or without Mk or residual stress;
- one interval for every crack.

They get at most 7 of 16 as given. Even with the single multiplier on their lives chosen with the truth in hand, none gets more than 8 of 16, against the 16 required. Among the 34 defective routes, every crack is failed by at least 9, and they fail on different cracks (route_study.txt prints the full matrix), so no crack is a free pass for a wrong method.

Malformed results are rejected as a whole (verifier_checks.txt). This covers a result that:
- is a symlink;
- is not JSON, or not one object with the single key intervals_months;
- has duplicate, missing or extra crack keys;
- has an interval that is NaN, infinite, zero, negative, a boolean, a string, an array or null.

18 such cases were run and none crashed the grader. The reference result is accepted at 16 of 16.

The agent works as a separate user that can write only to /app/output. /app/data is read-only, and the laboratory's sealed definition and records are unreadable to the agent. The verifier runs separately without network, and /logs/verifier is root-only.

## Layout (for maintainers)

- `instruction.md`: the task as the agent reads it (the author's own prose).
- `environment/`: the agent's image. `data/` is installed read-only at /app/data (procedure FA-3, laboratory rules,
  register, certificates, inspection, survey, maintenance log, handbook, two example records). `rig/fcgr.py` is the
  laboratory program; `rig/sealed/` (fcgsim.py, seed.json) is installed under /opt/lab for the user `lab` with mode
  700. The Dockerfile creates the users `agent` and `lab`, the sudo rule and the `fcgr` wrapper.
- `tests/`: the verifier image. `grade_intervals.py` grades the result against `sealed/`; `test_intervals.py` is the
  one pytest test; `test.sh` writes the reward; `app_data/` is a copy of the agent's documents.
- `solution/`: `solve.py` (the reference campaign, fit and crack model) and `solve.sh`.
- `authoring/provenance/`: the sealed definition (`fcgsim.py`), the generator (`gen.py`), `build.py`, and
  `seed_screen.py`, which chose the laboratory's scatter seed (9126; output in `authoring/evidence/seed_screen.txt`).
- `authoring/evidence/`: `route_study.py` (wrong side), `method_spread.py` and `independent.py` (right side),
  `null_baselines.py`, `verifier_checks.py`, `hedge_study.py`, `preflight.py`, and their `.txt` outputs; `seed_screen.txt` and
  `reference_run.txt`; `common.py` emulates the laboratory, including its deterministic scatter, so the numbers are
  those of the shipped scenario.

## Regenerating

    python3 authoring/provenance/build.py                 # environment/data, environment/rig/sealed, tests/sealed, tests/app_data
    cd authoring/evidence
    python3 route_study.py     > route_study.txt
    python3 method_spread.py   > method_spread.txt
    python3 independent.py     > independent.txt
    python3 null_baselines.py  > null_baselines.txt
    python3 verifier_checks.py > verifier_checks.txt
    python3 hedge_study.py > hedge_study.txt
    python3 ../provenance/seed_screen.py > seed_screen.txt # about an hour; only after a change to the scenario
    python3 preflight.py                                   # offline structural checks

`reference_run.txt` is solution/solve.sh's output in the agent's environment, graded by tests/grade_intervals.py.

Packages: numpy 2.1.3, scipy 1.14.1, pandas 2.2.3 (environment and verifier), pytest 8.4.1 and pytest-json-ctrf
0.3.5 (verifier).

## Changing the task

- Cracks, steels, the growth law (C, M, P, the closure U0 and RCL, the threshold line and DKTH_EFF), the heat factors
  HEAT_RATE, the residual stress levels, the loading changes, the laboratory's Kmax limit and scatter, the repair
  margin, the window and the gate live in `authoring/provenance/fcgsim.py`; the seed and the documents' text in
  `gen.py`. After any change run `build.py`, regenerate the evidence, and check that `route_study.txt` still rejects
  every defective route while `method_spread.txt` and `independent.txt` pass.
- The test budget and costs are `BUDGET` and `COST` in `environment/rig/fcgr.py` (and the laboratory text in `gen.py`).
- The seed drives only the laboratory's scatter. After any change to the scenario, rerun `seed_screen.py` and ship the
  seed it chooses: a heat's rate factor is often read from one test, and a 3.5 sigma draw on a natural test can fail a
  sound campaign. The screen keeps seeds whose tests all lie within 2.75 sigma and whose five sound solutions all get
  16 of 16, and takes the one whose worst interval / life is nearest the middle of the window.
- The furnace-PWHT cracks keep the dead load plus the PWHT residual stress at 44 to 56 MPa. Much smaller values make
  their R, and so their lives, hypersensitive to the residual stress level (a knife-edge on 0.18 versus 0.20 yield).
  As it is, the residual stress must be taken from the certificate yields: the grades' specified minimum yields lower
  it by up to 8 MPa on heat H2 and move C09 and C14 out of the window (`route_study.txt`).
- Keep the documents free of any statement of the effects: the end of closure, the heats' differences, the Mk factor,
  BS 7910's residual stress values, what VSR does, how the grab change moves the cycles. The task is that they must
  be found. Procedure FA-3 does say that R counts the weld-toe residual stress at BS 7910's level, since BS 7910's
  fatigue clause leaves that open for stress-relieved joints. It also says how repairs are ground, which is how the
  example records are read.
- Modelling note: the truth applies the closure law and the threshold to each rainflow bin at that bin's own R, as
  BS 7910 practice does. Load-sequence effects in variable-amplitude loading (closure set by the largest cycles) are
  not modelled.
