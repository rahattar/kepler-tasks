# grinding-burn-limit

A grinding shop sets the depth of cut of its plunge surface grinding jobs from its own grinding burn standard, MS-GB.
The surface temperature is the coolant temperature plus the rise under a uniform band heat source moving at high
Peclet number. The net grinding power that drives it is identified from the machine's spindle power records, with
the wheel at the end of its dressing interval. The burn limit is the part lot's highest tempering temperature plus
200 K.

The deliverable is `/app/output/burn.py`, a program that reads one job's package and writes the job's burn-limited
depth of cut. The package holds the job sheet, the lots' heat treatment certificates, the machine log and the spindle
power records. The program is run on seven jobs it has never seen.

## Difficulty

In practice this is the work of a grinding process engineer, who sets the depth of cut of many jobs with one program.
The program has to be right on jobs nobody has looked at. Its research analogue is the thermal modeling of grinding:
the moving heat source models of Jaeger, Malkin and Rowe calibrated from in-process power measurements, with the
energy partition and the wheel's wear state as the uncertain inputs.

The jobs and records are synthetic, written by `authoring/provenance` (`heat.py`, `jobs.py`, `docs_grind.py`,
`build.py`) from a sealed definition. They are realistic in their numbers:
- Vitrified alumina wheels (A80K5V, A60J6V) and a vitrified CBN wheel (B126V), 400 mm when new and 365 to 398 mm now.
- 5 percent emulsion or straight grinding oil, with heat shares into the workpiece of 0.22 to 0.78.
- Hardened 100Cr6, 42CrMo4, 16MnCr5 and X40CrMoV5-1, tempered at 150 to 600 C.
- Programmed work speeds of 7 to 20 m/min.
- Specific grinding energies of 27 to 55 J/mm3, with sliding power of 3.6 to 9.0 W per mm of width that grows with
  the volume removed since dressing.
- Spindle idle power of 820 to 1640 W.
- Four to five months of power records per machine, with 0.4 to 1.2 percent noise.
- True burn-limited depths of 10.0 to 41.7 um (`authoring/evidence/reference.txt`).

The example job, `job-ex`, has sound records and no reported answer, since MS-GB defines the depth:
- one wheel and one coolant over all the records;
- one lot, tempered once;
- the dressing interval in mm3/mm;
- no table or chiller work in its machine log.

The seven hidden jobs carry the faults that shop records carry. Each looks like ordinary data, and the documents say
only what was done, never its effect:
- **Wheel and coolant changes.** The machine log records a coolant change on race-face and gauge-block, and a wheel
  change on die-insert, cam-flank and bushing-od. The power records carry no wheel or coolant column, so the records
  of the operation's wheel and coolant are the ones since the change.
- **Idle power shifts.** The idle power shifts at some of those changes (race-face, gauge-block, die-insert) and after
  spindle work (punch-land). Each session's air passes give its own idle power.
- **Lot certificates.** The heat treatment file lists several lots, and the job's lot is not the first (race-face,
  gauge-block, bushing-od).
- **Re-tempered lots.** Two lots were re-tempered at a higher temperature after a hardness check (shaft-seat,
  punch-land).
- **Table speed limit.** The table's speed is limited in the log after a valve replacement: race-face is programmed at
  12 and limited to 10 m/min; bushing-od is programmed at 16 and limited to 12 m/min.
- **Chiller out of service.** The coolant chiller is out of service, so the coolant runs at 46 and 44 C rather than
  the job sheet's 25 and 23 C (shaft-seat, gauge-block).
- **Dressing interval in parts.** The dressing interval is given in parts, with the stock and the face length
  (die-insert, cam-flank, punch-land).

Each check left out or done the obvious way gets jobs wrong, against an allowance of one wrong job
(`authoring/evidence/route_study.txt`). Each figure is the signed deviation from the truth:
- Every power record, whatever the wheel and coolant: 4 wrong, -16.2 to +52.0 percent.
- The wheel's state averaged over the records, not the end of the dressing interval: 6 wrong, +6.0 to +23.6 percent.
- The first lot's certificate: 3 wrong, -23.8 to +25.1 percent.
- The first tempering temperature of a re-tempered lot: 2 wrong, punch-land -11.4 and shaft-seat -16.6 percent.
- The programmed work speed, not the table's limit: 2 wrong, bushing-od -14.2 and race-face -10.7 percent.
- The job sheet's coolant temperature while the chiller is out: 2 wrong, gauge-block +12.5 and shaft-seat +8.7
  percent.
- A dressing interval in parts taken per part: 2 wrong, die-insert +8.9 and punch-land +7.5 percent.
- One idle power for all sessions: 3 wrong, -12.0 to +48.2 percent.
- The records at face value (the programmed speed, the job sheet's coolant temperature, every power record): 6 wrong.

Every route misses at least two jobs, and every hidden job is missed by at least two routes. On the example, every
record route gives the reference's 8.5730 um, or 8.5970 um with one idle power. Only the averaged wheel state differs
there (9.7000 um), and with no reported answer the example does not expose it (`authoring/evidence/route_example.txt`).

## Reference solution

`solution/burn.py` is the reference program; `solution/solve.sh` installs it as `/app/output/burn.py` and runs it on
the example. For one job it does the following:
- **Job sheet.** Reads the wheel, the material and lot, and the contact width (the ground width, or the two lands of a
  face with a relief groove). It also reads the programmed work speed, the coolant and its temperature, and the
  dressing interval (in mm3/mm, or parts times stock times face length).
- **Machine log.** The work speed is the programmed one, or the table's speed limit when the log sets a lower one. The
  coolant temperature is the job sheet's, or the one the log gives while the chiller is out of service. The wheel
  diameter is the one after the last dressing. The power records used are those since the last wheel or coolant
  change.
- **Burn limit.** The highest temperature at which the job's lot was tempered, from its certificate, plus 200 K.
- **Power model.** Each grind pass's net power is its spindle power less the idle power of its session (the mean of
  that day's air passes). p0, p1 and u are fitted by least squares on P = b p0 + b V p1 + u b ae vw.
- **Depth.** The largest depth at which the coolant temperature plus 1.13 Rw q sqrt(lc / vw) / beta stays at the burn
  limit, with the wheel at the end of its dressing interval. It is bracketed on a logarithmic grid of depths and
  refined by Brent's method (the upper root: the rise first falls with depth, then rises).

Run through `tests/grade.py` as the verifier runs a submission, its depths are within 1.21 percent of the truth on all
seven hidden jobs. On the example it gives 8.5730 um (`authoring/evidence/reference.txt`).

## Verification

`tests/grade.py` runs the submitted `/app/output/burn.py` on each of the seven hidden jobs (`tests/hidden`; the
agent's image does not contain them). The verifier image has the agent's `/app/data` at the same path, read-only
(`tests/app_data`, written by the same `build.py`), so a program that reads the grinding data from it at run time
behaves as it did for the agent.

How each job is run:
- The program alone and the package are copied to a scratch directory owned by root, where the package is read-only.
- The program runs as the unprivileged user nobody, with only PATH and HOME set, as
  `python3 -I burn.py JOB_DIR OUT_JSON`, within 600 s, in its own process group.
- When the run ends or times out, its process group and every process of nobody are killed before the output is read.
  The seven runs are sequential, so the worst case (4200 s) fits the 4800 s verifier timeout.
- The instruction states these run conditions, including the 10 minutes and that `burn.py` must be self-contained.

The output must be a regular file, not a symlink, of at most 65536 bytes. It must hold one JSON object with exactly the
key `max_depth_um`, once, a finite positive number (not a string or a boolean; NaN and Infinity are rejected). The
program must exit with status 0. A job whose output breaks any of this is wrong. The instruction states every one of
these rules.

A job is right when its value is within 5 percent of its burn-limited depth. The instruction states the 5 percent as
a requirement. The truth (`tests/hidden/truth.json`, root-only in `/tests`) is computed by `authoring/provenance/heat.py`
on the sealed job as it will run. That means the true power model of the current wheel and coolant at the end of the
dressing interval, the current wheel diameter, the table and coolant conditions of the machine log, and the lot's
burn limit. The method is MS-GB's. The truth is a computation on the sealed job, not on its records.

The single pytest test passes when at most 1 of the 7 jobs is wrong; the allowance of one job is not in the
instruction. `tests/test.sh` does the following:
- Locks `/logs/verifier` to root before grading and again before the reward.
- Writes reward 0 first, and 1 only when pytest exits 0 and the ctrf report holds exactly one test, passed, with none
  failed, skipped, pending or other.
- Writes the per-job results to `/logs/verifier/metrics.json`, where they do not affect the reward.

Every calibration number below is measured by the verifier itself. Each method, route and method-free answer is a
complete JSON-writing program, run through `tests/grade.py` exactly as a submission. `authoring/evidence/common.py`
writes the program file and calls `score()`. It runs as nobody from a scratch copy, as
`python3 -I burn.py JOB_DIR OUT_JSON`, and grade.py reads and judges the JSON. No evidence script calls a program's
functions directly.

Why 5 percent and at most 1 wrong job:
- **Correct methods.** All are right on every job, within 1.38 percent of the truth
  (`authoring/evidence/method_spread.txt`):
  - the reference;
  - `authoring/evidence/independent.py`, a second program that shares no code with it (within 1.13 percent);
  - three variants of the reference: each session's idle from its first air pass only, every second grind pass only,
    and the power model fitted per unit width.

  The second program takes each session's idle power as the median of its air passes. It fits the power per unit
  width by its own normal equations, and finds the depth by stepping down from 1 mm and bisecting.
- **Defective routes.** The routes above miss by 6.0 percent or more. The closest misses, +6.0 and +6.9 percent, come
  from the averaged wheel state, which misses six jobs, by up to 23.6 percent. Every miss of the other routes is 7.5
  percent or more.
- **The tolerance.** 5 percent sits between the correct methods (1.38 percent at most) and the closest defective miss
  (6.0 percent).
- **The allowance.** One wrong job is allowed so that a sound program with a single marginal job is not failed. No
  route and no method-free answer stays within it.

Method-free answers (`authoring/evidence/constant_null.txt`) are all rejected, each with all 7 jobs wrong:

| Method-free answer | Deviation over the jobs (percent) |
|---|---|
| the example's depth (8.57 um) for every job | -79.4 to -14.3 |
| 15 um for every job | -64.0 to +49.9 |
| the example's specific removal rate at the job's work speed | -84.6 to +83.6 |

Every hidden job's depth is at least 14 percent from the example's, so the example's answer carries over to none of
them.

Malformed output and misbehaving programs (`authoring/evidence/verifier_checks.txt`) write the reference's value for
each job and then corrupt it. They are run through `grade.py` as the verifier runs them. Each of the following has
every job counted wrong, and none crashes the verifier:
- an output that is a symlink;
- a missing, extra, renamed or repeated key, or a list instead of an object;
- a NaN, infinite, string, boolean, negative or zero value;
- an empty file, bytes that are not UTF-8, or a correct object padded past 65536 bytes;
- a non-zero exit status, or a run past the time limit.

A background process left running is killed when its run ends, and no process of nobody survives any case.

The agent works as a separate user that can only write to `/app/output`; `/app/data` is read-only. The verifier runs
separately without network.
