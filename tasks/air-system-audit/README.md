# air-system-audit

Notes for reviewers and maintainers. The task statement is in instruction.md. The three sections below are the
task's explanation of its difficulty, its reference solution and its verification. task.toml's metadata carries the
same text. The rest of this file covers how the bundle is put together and how to check or change it.

## Difficulty

An energy engineer or the utilities engineer of a plant does this when the plant audits its compressed air systems site by site and wants every audit reduced the same way: a few days of power logs on each compressor and a pressure log on the receiver, turned into the demand the plant really draws, its leak load and the system's specific power. The program is reused for every site, so it has to be right for sites nobody has looked at. The sites, compressors and logs are synthetic, written by authoring/provenance from a sealed definition. They are realistic, and so is the level of challenge they present:
- The plants are typical: two or three rotary screw compressors of 12 to 30 m3/min and 75 to 165 kW, 5.5 to 6.3 kW per m3/min at 7 bar g in their performance tables, as in CAGI data sheets. Load/unload bands sit between 6.2 and 7.5 bar g, and receivers hold 7.5 to 14 m3 (the site definitions in authoring/provenance/gen.py).
- The logs are what a real audit produces. They are 10-second power averages from clamp-on analysers, with measurement noise, and a receiver pressure log. Each site is simulated second by second, including blow-down and motor stops.
- Demand follows a production shift and has short surges. Leaks are 35.2 to 43.4 percent of the average demand: high, but common in plants that have not managed leaks. With unloaded running included, the system specific power comes to 6.30 to 7.43 kW per m3/min (authoring/evidence/reference.txt).
- The two logger faults are the ones auditors meet in practice: an analyser connected with one current transformer, and a pressure logger whose clock was never set to the plant's. As in the field, the data look normal and nothing in the files flags either fault.

The core difficulty is that none of the results is logged. Each has to be reconstructed from the physics of the machines and the system, and the logs have to be checked against that physics before they are trusted:
- Supply from power. A load/unload compressor delivers its full free air delivery only while loaded, and its unloaded power (60 falling to 25 percent of full load while the separator blows down) and its starts from stopped fall inside the 10-second averages. Counting an interval as loaded on a power threshold misstates the average demand by 5.8 to 10.4 percent and the leak flow by 21.3 to 33.1 percent on the sites it misses. A variable-speed machine's delivery comes from its power through its performance table.
- Demand is not supply. During a surge above the installed capacity the receiver and piping make up the difference, so the peak demand needs the storage term (V / p_atm times the rate of pressure change). Without it, peak demand is 9.1 to 11.4 percent low on every site.
- A power analyser connected with one current transformer records a third of the power. Nothing in the log says so; the running power, compared with what the compressor's own performance table allows, does.
- The pressure logger's clock is its own. On some sites it is minutes to an hour off the power analysers, and only the receiver's response to the compressors' load changes shows by how much.

The example site shows none of the logger faults. The hidden sites have all of them, eight sites with two to three compressors each, load/unload and variable-speed. Leaving out the storage term misses 8 sites, the one-CT check 3, the clock check 3 and the loaded-fraction reconstruction 5 (authoring/evidence/route_study.txt), against an allowance of 1.

## Reference solution

solution/audit.py is the reference program; solution/solve.sh installs it as /app/output/audit.py and runs it on the example audit. For one audit package it does the following.

Logs to supply:
- Each compressor's power is put on the power analysers' 10-second grid. A load/unload machine's power is divided by its full-load power at its discharge pressure (receiver pressure plus the pressure drop to the compressors, from its performance table). A log whose running power sits near a third of full load is multiplied by three (one CT). A variable-speed log whose running power lies below the table's minimum is treated the same way.
- Each load/unload interval's loaded fraction: 1 at full-load power. In an interval where the machine starts from stopped, the fraction is the power ratio. In an interval where it unloads, it is (ratio - 0.6) / 0.4. In an interval where it reloads from unloaded, it is (ratio - u) / (1 - u), where u is the previous interval's unloaded level. The supply is the loaded fraction times the free air delivery at the discharge pressure. Variable-speed supply is the table's delivery at the logged power, zero when stopped.

Clock and demand:
- The pressure logger's offset is the lag, searched over +/-3 h in 10-second steps, that best lines up the pressure change per interval with the fast part of supply (supply less its 31-interval moving average).
- Supply is recomputed with the pressure on the corrected clock. Demand per interval is supply less V / p_atm times the pressure change over the interval, in free air per minute.
- The results are the mean demand, the highest 12-interval mean, the mean over the non-production hours (by each interval's midpoint) and the total energy over the total supply.

On the 8 hidden sites its largest errors are 0.61 percent (average demand and specific power), 0.45 percent (peak) and 1.14 percent (leak) (authoring/evidence/reference.txt).

## Verification

tests/grade_audits.py runs the submitted /app/output/audit.py on each of eight hidden audit packages (tests/hidden; the agent's image does not contain them).

The verifier image has the agent's /app/data at the same path and read-only (tests/app_data, a copy that authoring/provenance/build.py writes). A program that reads the documents or the example at run time therefore behaves as it did in development.

How each audit is run and judged:
- audit.py alone and the audit package are copied to a scratch directory.
- It runs as the unprivileged user nobody, with only PATH and HOME set, as `python3 -I audit.py AUDIT OUT.json`, within 120 seconds, in its own process group. When the run ends or times out, its process group and every process of nobody are killed before the output is read, so nothing it starts in the background outlives the run. The eight runs are sequential, so the worst case (960 s) fits the 1200 s verifier timeout. The instruction states these run conditions, including that audit.py must be self-contained.
- The sealed results (tests/hidden/truth.json) come from the simulated true demand, supply and power, not from the logs. They stay in /tests, which only root can read.
- A site is right when the average demand and the specific power are within 3 percent of the true values, and the peak demand and the leak flow within 5 percent.

The single pytest test passes when at most 1 of the 8 sites is wrong. test.sh writes reward 1 only when pytest exits 0 and the ctrf report holds exactly one test, passed, with none failed, skipped, pending or other; otherwise 0. Per-site results go to /logs/verifier/metrics.json and do not affect the reward.

The hidden sites carry, by design:
- surges above the installed capacity on every site (peak demand needs the storage term);
- one-CT power logs on four compressors at three sites (three load/unload, one variable-speed);
- pressure-logger clock offsets of +60, -30 and +45 minutes at three sites;
- variable-speed compressors at three sites, two to three compressors per site, storage volumes from 7.5 to 14 m3.

Why these tolerances and at most 1 wrong (measured on the 8 hidden sites; every number below is copied from the named file in authoring/evidence):

Correct implementations:
| Program | Worst error: average demand | specific power | peak demand | leak flow | Sites wrong | File |
|---|---|---|---|---|---|---|
| solution/audit.py (reference) | 0.61 % | 0.61 % | 0.45 % | 1.14 % | 0 | reference.txt |
| independent_audit.py | 0.61 % | 0.61 % | 0.45 % | 1.57 % | 0 | independent.txt |
| reference with other sound settings (5 variants) | | | | | 0 each | method_spread.txt |

- independent_audit.py is a second program that shares no code with the reference. It uses pandas, percentile checks against the table's largest power, an FFT cross-correlation for the clock and a time-since-unload blow-down model.
- The 5 variants are: full-load threshold 0.88 or 0.95, blow-down start 0.55, an 11-interval high-pass, and no second pass.
- Correct implementations stay within about a fifth of the tolerance on average demand, specific power and peak, and within about a third on the leak (3 % and 5 %).

Defective implementations (route_study.txt), against the allowance of 1 wrong:
| Step left out | Sites wrong | Errors on the missed sites |
|---|---|---|
| storage term | 8 | peak -9.1 to -11.4 % |
| clock check | 3 | peak -5.1 to -12.2 % |
| one-CT check, on every compressor | 3 | average -31.3 to -61.0 %, leak down to -100.0 % |
| one-CT check, on the load/unload compressors only | 2 | average -34.6 and -61.0 % |
| one-CT check, on the variable-speed compressor only | 1 | average -31.3 % (s-307) |
| loaded-fraction reconstruction (counted loaded above half of full load) | 5 | average +5.8 to +10.4 %, leak +21.3 to +33.1 % |

- The tolerances sit between the two groups. Every method that leaves out a whole step misses 3 to 8 sites, and most misses are by several times the tolerance.
- The closest miss (peak -5.1 % on s-302, no clock check) comes from a variant that also misses s-305 (-7.9 %) and s-307 (-12.2 %), so the outcome does not hang on that one value.
- One wrong site is allowed so that a sound program with a single marginal site is not failed. The one partial omission it admits is a program that checks the load/unload logs for one CT but not the variable-speed log: it misses only s-307, so it is accepted. It has the right check and applies it to most of the machines; the allowance is set to accept that, and no method without the check is accepted.

Constant answers: no constant answer passes. A program that always writes the example's results misses all 8 sites, and one that writes fractions of the installed capacity with a typical specific power misses all 8 (constant_null.txt).

Malformed results (verifier_checks.txt): a result that is not a regular file (a symlink), not a JSON object (for example an empty array), has duplicate, missing or extra keys, or has a NaN, infinite, boolean, string or array value counts as a wrong site. It does not crash the verifier. A program that leaves a background process running has it killed when its run ends.

The agent works as a separate user that can only write to /app/output; /app/data is read-only. The verifier runs separately without network, and /logs/verifier is root-only.

## Layout

| Path | What it is |
|---|---|
| `instruction.md` | The task as the solver sees it. |
| `environment/Dockerfile`, `environment/data/` | The solver's image. `/app/data` holds `docs/audit_procedure.md`, `docs/site_package.md` and the example audit `examples/s-201/` with `audit_result.json`. |
| `solution/audit.py`, `solution/solve.sh` | The reference program, and the script that installs it at `/app/output/audit.py`. |
| `tests/` | The verifier: `test.sh` (writes the reward), `test_audit.py` (the single pytest test), `grade_audits.py` (runs and judges the program), `hidden/` (eight audit packages and `truth.json`), `app_data/` (a copy of `environment/data`, installed read-only at `/app/data` in the verifier image), `Dockerfile`. |
| `authoring/provenance/` | `gen.py` is the sealed definition of all nine sites, and simulates them. `build.py` writes `environment/data`, `tests/hidden` and `tests/app_data` from it. `docs/` holds the source of the two documents. |
| `authoring/evidence/` | The scripts behind the tolerance and the allowance of 1 wrong, with their saved outputs (`*.txt`). |

## Hidden sites

| Site | Compressors | Storage (m3) | Logger faults |
|---|---|---|---|
| s-301 | 3 load/unload | 12.0 | K-2 power logged on one CT |
| s-302 | 2 load/unload | 7.5 | pressure clock +60 min |
| s-303 | 1 variable-speed, 1 load/unload | 14.0 | none |
| s-304 | 3 load/unload | 10.0 | B-1 and B-3 on one CT |
| s-305 | 1 variable-speed, 1 load/unload | 8.0 | pressure clock -30 min |
| s-306 | 3 load/unload | 11.0 | none |
| s-307 | 1 load/unload, 1 variable-speed | 9.5 | G-2 (variable-speed) on one CT; pressure clock +45 min |
| s-308 | 3 load/unload | 13.0 | none |

Every site has demand surges above its installed capacity, so the storage term matters everywhere. The example
site s-201 (three load/unload machines, 9 m3) has no logger fault.

## Regenerating and checking

Python 3.11 with numpy 2.1.3, scipy 1.14.1 and pandas 2.2.3, as in the images. Add pytest 8.4.1 and
pytest-json-ctrf 0.3.5 to run the verifier outside Docker.

```
python3 authoring/provenance/build.py                 # rewrites environment/data, tests/hidden, tests/app_data
python3 tests/grade_audits.py solution/audit.py       # per-site errors of a program on the hidden sites
python3 authoring/evidence/reference.py               # reference errors and the hidden sites' true results
python3 authoring/evidence/route_study.py             # reference with one step left out at a time
python3 authoring/evidence/method_spread.py           # reference with other sound settings
python3 authoring/evidence/independent.py             # the independent second program
python3 authoring/evidence/constant_null.py           # programs that do not compute the audit
python3 authoring/evidence/verifier_checks.py         # malformed results and background processes
python3 authoring/evidence/preflight.py               # offline structural checks
```

The generator is deterministic: each site's random stream is seeded from its number, so `build.py` reproduces the
committed data byte for byte. The preflight checks this.

## Changing the task

- Change sites in `gen.py`'s `SITES` and rerun `build.py`. Then rerun the evidence scripts. The reference should
  stay at 0 wrong, and each left-out step should still miss more than one site.
- `MAX_WRONG`, `TOL` and `TIME_LIMIT_S` in `tests/grade_audits.py` come from instruction.md, so change them together.
  Eight runs at the time limit must fit within `[verifier] timeout_sec`.
- The documents must not name the logger faults. `site_package.md` does say that each logger stamps its readings
  with its own clock, and that the power analysers carry the plant's local time. The non-production hours depend on
  that second statement.
