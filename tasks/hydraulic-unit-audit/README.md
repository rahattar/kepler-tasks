# hydraulic-unit-audit

Notes for reviewers and maintainers. The task statement is in instruction.md. The three sections below are the
task's explanation of its difficulty, its reference solution and its verification. task.toml's metadata carries the
same text. The rest of this file covers how the bundle is put together and how to check or change it.

## Difficulty

A plant's utilities or maintenance engineer does this when the plant studies whether to replace the fixed-displacement pumps of its press hydraulic power units by variable-speed drives: each unit is logged through a run of press cycles (system pressure, pump outlet pressure and motor input power) and the log is reduced to the oil the press takes per cycle, its peak demand flow, the hydraulic energy delivered, the electrical energy used and the unit's efficiency. The program is reused for every press, so it has to be right for units nobody has looked at. The presses, units and logs are synthetic, written by authoring/provenance from a sealed definition. They are realistic, and so is the level of challenge they present:
- The units are typical of small and medium presses: axial piston pumps of 14 to 45 cm3/rev on 15 to 30 kW four-pole motors, bladder accumulators of 16 to 32 L with precharges of 75 to 110 bar, unloading valves set between 135 and 250 bar, press cycles of 10 to 14 s taking 1.9 to 6.1 L of oil with approach flows of 40 to 95 L/min (the site definitions in authoring/provenance/gen.py).
- The logs are what a plant logger produces: 20 samples per second of the two pressures and the power over about ten cycles, with transmitter noise, and the unit's physics behind them: pump flow that falls with pressure through the volumetric efficiency, motor speed that drops with load through the slip, the accumulator's gas compressing and expanding adiabatically about its mean state, the unloading valve's hysteresis.
- The two faults are the ones a plant meets: a logger whose pressure channels are scaled wrong (both channels of the unit, since they share the logger's configuration), and a bladder accumulator that has lost precharge since the figure in the unit's record was taken. In both, the log looks normal and nothing in the files says anything is wrong.

The core difficulty is that the results depend on quantities the log does not carry. The oil the press takes is the pump's delivery less what the accumulator absorbs, and the accumulator's share comes from the gas law on the system pressure; the energy delivered is the integral of pressure times that demand. So:
- A pressure channel scaled wrong leaves the oil per cycle untouched (over a cycle the accumulator returns to its state) but puts the hydraulic energy and the efficiency 19 to 23 percent off and the peak flow 19 to 26 percent off. The only evidence is physical: while the pump is loaded, the motor's input power must equal the pump's hydraulic power over the pump's and the motor's efficiencies, and with the logged pressure it does not.
- A lost precharge leaves the energy untouched but puts the peak flow 54 to 60 percent high, because the gas volume behind every bar of pressure swing is what the precharge sets. The only evidence is physical: while the pump charges the accumulator with the press at rest, every litre the pump delivers must appear as a gas volume change, and with the recorded precharge it does not; more generally, the press's demand can never be negative, which bounds the precharge from above.
Both checks need the pump's efficiency table and the motor data that the ordinary calculation uses anyway; neither is part of the procedure, and the procedure applied as written is wrong on 5 of the 8 hidden presses. The example press has no fault.

The hidden presses have, by design: three with scaled pressure channels (factors 0.8, 1.25 and 1.25), three with lost precharge (65, 63 and 64 percent of the recorded figure), one of them with both, and three clean. Leaving out the pressure check misses 3 presses, the precharge check 3, both 5 (authoring/evidence/route_study.txt), against an allowance of 1.

## Reference solution

solution/hpu.py is the reference program; solution/solve.sh installs it as /app/output/hpu.py and runs it on the example package. For one package it does the following.

Checks before the procedure:
- Pressure scale. Over the loaded samples (pump outlet pressure above 20 bar, motor power well above the unloaded power) it computes the pressure the power balance implies, P_el eta_motor eta_hm / Q_th, with the theoretical pump flow from the displacement and the slip-corrected speed and the hydromechanical efficiency from the pump's table, and takes the median ratio of the logged pump pressure to it, iterating three times because the table is read at the corrected pressure. A ratio more than 5 percent off 1 is a scaled logger: both pressure channels are divided by it.
- Precharge. Over every 1 s window of loaded operation it computes the ratio of the pump's oil delivered in the window to the gas volume change per bar of precharge from the procedure's gas law. The press's demand is the pump flow less what the accumulator absorbs and cannot be negative, so the precharge is at most that ratio in every window, with equality where the press rests while the pump finishes charging. The 5th percentile of the ratios over the windows is the precharge; the record's figure is kept when it is within 5 percent of it.

Procedure HP-2 as written: pump flow from the displacement, the slip-corrected speed and the volumetric efficiency at the pump outlet pressure while loaded; gas volume from the mean-state gas law with the precharge found; demand from the pump flow and the central difference of the gas volume; cycles from one reload to the next; the oil, the highest 1 s mean of the demand, the pressure-weighted integral and the power integral per cycle, averaged over the complete cycles; efficiency as their ratio.

On the 8 hidden presses its largest errors are 0.06 percent (oil), 0.89 percent (hydraulic energy), 0.01 percent (electrical energy), 1.83 percent (peak flow) and 0.0062 (efficiency) (authoring/evidence/reference.txt).

## Verification

tests/grade_hpu.py runs the submitted /app/output/hpu.py on each of eight hidden press packages (tests/hidden; the agent's image does not contain them).

The verifier image has the agent's /app/data at the same path and read-only (tests/app_data, a copy that authoring/provenance/build.py writes). A program that reads the documents or the example at run time therefore behaves as it did in development.

How each package is run and judged:
- hpu.py alone and the package are copied to a scratch directory.
- It runs as the unprivileged user nobody, with only PATH and HOME set, as `python3 -I hpu.py PACKAGE OUT.json`, within 60 seconds, in its own process group. When the run ends or times out, its process group and every process of nobody are killed before the output is read, so nothing it starts in the background outlives the run. The eight runs are sequential, so the worst case (480 s) fits the 900 s verifier timeout. The instruction states these run conditions, including that hpu.py must be self-contained.
- The sealed results (tests/hidden/truth.json) are procedure HP-2 applied to the true log: the true pressures, without noise, with the accumulator's actual precharge. They stay in /tests, which only root can read.
- A press is right when the oil delivered, the hydraulic energy and the electrical energy are within 3 percent of the true values, the peak flow within 5 percent, and the efficiency within 0.03 (absolute).

The single pytest test passes when at most 1 of the 8 presses is wrong. test.sh writes reward 1 only when pytest exits 0 and the ctrf report holds exactly one test, passed, with none failed, skipped, pending or other; otherwise 0. Per-press results go to /logs/verifier/metrics.json and do not affect the reward.

Why these tolerances and at most 1 wrong (measured on the 8 hidden presses; every number below is copied from the named file in authoring/evidence):

Correct implementations:
| Program | Worst error: oil | hydraulic energy | electrical energy | peak flow | efficiency | Presses wrong | File |
|---|---|---|---|---|---|---|---|
| solution/hpu.py (reference) | 0.06 % | 0.89 % | 0.01 % | 1.83 % | 0.0062 | 0 | reference.txt |
| independent_hpu.py | 0.06 % | 0.87 % | 0.02 % | 1.81 % | 0.0061 | 0 | independent.txt |
| reference with other sound settings (7 variants) | 0.06 % | 1.48 % | 0.01 % | 2.64 % | 0.01 | 0 each | method_spread.txt |

- independent_hpu.py is a second program that shares no code with the reference. It uses pandas and rolling windows, finds the pressure scale by least squares against the power balance, and the precharge from the smallest window ratios with a noise allowance.
- The 7 variants are: precharge always from the fit; the 10th percentile instead of the 5th; 0.5 s windows; the mean ratio instead of the median for the scale; the scale applied from 2 percent; a loaded threshold of 15 bar; and gauge pressure in the gas law.
- Correct implementations stay within half the tolerance on every result.

Defective implementations (route_study.txt), against the allowance of 1 wrong:
| Step left out | Presses wrong | Errors on the missed presses |
|---|---|---|
| pressure scale check against the power balance | 3 | hydraulic energy -19.0 to +22.9 %, efficiency -0.132 to +0.172 |
| precharge check against the charging | 3 | peak flow +53.7 to +60.0 % |
| both (the procedure as written) | 5 | as above, and peak flow -19.1 to +27.2 % on the scaled presses |
| volumetric efficiency taken as 1 | 8 | oil and hydraulic energy +5.7 to +8.4 % |
| gas law from the precharge state (mean state left out) | 8 | peak flow +21.4 to +40.2 % |
| motor slip left out | 0 | within tolerance (speed moves the flow by under 1 %) |

- The tolerances sit between the two groups: every defective method misses 3 to 8 presses, and its misses are by several times the tolerance; the closest miss of a defective route is the scaled presses' hydraulic energy at 19 percent against a 3 percent tolerance.
- Leaving out the motor slip is accepted: its effect is under 1 percent, and that is a sound simplification, not a defect.
- One wrong press is allowed so that a sound program with a single marginal press is not failed. No defective route gets down to one.

Constant answers: no constant answer passes. A program that always writes the example's results misses all 8 presses, and one that writes typical figures scaled by the pump displacement misses all 8 (constant_null.txt).

Malformed results (verifier_checks.txt): a result that is not a regular file (a symlink), not a JSON object (for example an empty array), has duplicate, missing or extra keys, or has a NaN, infinite, boolean, string or array value counts as a wrong press. It does not crash the verifier. A program that leaves a background process running has it killed when its run ends.

The agent works as a separate user that can only write to /app/output; /app/data is read-only. The verifier runs separately without network, and /logs/verifier is root-only.

## Layout

| Path | What it is |
|---|---|
| `instruction.md` | The task as the solver sees it. |
| `environment/Dockerfile`, `environment/data/` | The solver's image. `/app/data` holds `docs/hp2_procedure.md`, `docs/unit_records.md` and the example package `examples/p-01/` with `results.json`. |
| `solution/hpu.py`, `solution/solve.sh` | The reference program, and the script that installs it at `/app/output/hpu.py`. |
| `tests/` | The verifier: `test.sh` (writes the reward), `test_hpu.py` (the single pytest test), `grade_hpu.py` (runs and judges the program), `hidden/` (eight packages and `truth.json`), `app_data/` (a copy of `environment/data`, installed read-only at `/app/data` in the verifier image), `Dockerfile`. |
| `authoring/provenance/` | `gen.py` is the sealed definition of all nine presses; `hpusim.py` simulates a unit through its cycles; `build.py` writes `environment/data`, `tests/hidden` and `tests/app_data` from them; `docs/` holds the source of the two documents. |
| `authoring/evidence/` | The scripts behind the tolerance and the allowance of 1 wrong, with their saved outputs (`*.txt`), and `simulated.json` (the simulated per-cycle means, for `reference.py`). |

## Hidden presses

| Press | Pump (cm3/rev) | Motor (kW) | Accumulator (L) | Recorded precharge (bar) | Faults |
|---|---|---|---|---|---|
| p-11 | 32 | 22 | 25 | 100 | none |
| p-12 | 28 | 18.5 | 20 | 85 | pressure channels scaled by 0.80 |
| p-13 | 45 | 30 | 32 | 110 | none |
| p-14 | 14 | 15 | 16 | 80 | precharge actually 52 bar |
| p-15 | 32 | 22 | 25 | 95 | pressure channels scaled by 1.25 |
| p-16 | 28 | 18.5 | 20 | 90 | none |
| p-17 | 32 | 30 | 32 | 105 | pressure channels scaled by 1.25; precharge actually 66 bar |
| p-18 | 14 | 15 | 16 | 75 | precharge actually 48 bar |

The example press p-01 (28 cm3/rev, 18.5 kW, 20 L, 90 bar) has no fault.

## Regenerating and checking

Python 3.11 with numpy 2.1.3, scipy 1.14.1 and pandas 2.2.3, as in the images. Add pytest 8.4.1 and
pytest-json-ctrf 0.3.5 to run the verifier outside Docker.

```
python3 authoring/provenance/build.py                 # rewrites environment/data, tests/hidden, tests/app_data
python3 tests/grade_hpu.py solution/hpu.py            # per-press errors of a program on the hidden presses
python3 authoring/evidence/reference.py               # reference errors, and truth against the simulated means
python3 authoring/evidence/route_study.py             # reference with one check or step left out at a time
python3 authoring/evidence/method_spread.py           # reference with other sound settings
python3 authoring/evidence/independent.py             # the independent second program
python3 authoring/evidence/constant_null.py           # programs that do not reduce the log
python3 authoring/evidence/verifier_checks.py         # malformed results and background processes
python3 authoring/evidence/preflight.py               # offline structural checks
```

The generator is deterministic: each press's random stream is seeded from its number, so `build.py` reproduces the
committed data byte for byte. The preflight checks this.

## Changing the task

- Change presses in `gen.py`'s `PRESSES` and rerun `build.py`. Then rerun the evidence scripts. The reference should
  stay at 0 wrong, and each left-out check should still miss more than one press. Keep a rest period of at least 2 s
  between the end of the press cycle and the pump unloading on every press (the precharge check needs it).
- `MAX_WRONG`, `TOL` and `TIME_LIMIT_S` in `tests/grade_hpu.py` come from instruction.md, so change them together.
  Eight runs at the time limit must fit within `[verifier] timeout_sec`.
- The documents must not name the faults. `unit_records.md` describes the unit, the logger and the package;
  `hp2_procedure.md` defines the results and the gas law's mean state. Nothing says what a wrong channel scale or
  a lost precharge would look like.
