# milling-chatter-limit

A machine shop sets the axial depth of cut of its milling jobs from its own stability standard, MS-CH. The standard
uses the zero-order solution of Altintas and Budak (1995). Its inputs are the tool-tip receptances along the feed and
normal to it, the radial immersion of the cut, the number of cutting teeth and the cutting coefficients of the
material. The stability limit is the depth at which regenerative chatter starts at the spindle speed of the
operation.

The deliverable is `/app/output/chatter.py`, a program that reads one job's package and writes the job's stability
limit. The package holds the setup sheet, the tap test files of the machine and the machine log. The program is run on
seven jobs it has never seen.

## Difficulty

In practice this is the work of a manufacturing engineer who sets cutting parameters for many jobs with one program.
The program has to be right on jobs nobody has looked at. Its research analogue is machining dynamics: experimental
modal data at the tool tip combined with an analytic stability model to predict chatter, the method of Tlusty,
Altintas and Budak.

The jobs and records are synthetic, written by `authoring/provenance` (`chat.py`, `jobs.py`, `docs_job.py`,
`build.py`) from a sealed definition. They are realistic in their numbers:
- End mills of 12 to 20 mm with 3 or 4 flutes, and face mill bodies of 50 and 63 mm with 3 of 6 and 4 of 8 inserts
  fitted.
- Materials 6061-T6, 7075-T6, 1045, 4140 QT and GG25, with Kt of 700 to 2600 N/mm2.
- Tool-tip modes at 520 to 2100 Hz, with modal stiffness of 1.05 to 36 MN/m and damping of 2.8 to 4.2 percent.
- Spindle speeds of 2800 to 17000 rpm.
- Tap test files from 100 to 5000 Hz at 0.5 Hz, with 0.3 percent noise.
- True stability limits of 0.81 to 3.74 mm (`authoring/evidence/reference.txt`).

The example job, `job-ex`, has sound records and no reported answer, since MS-CH defines the limit:
- one tap test pair of its assembly at its stickout, in receptance;
- the accelerometer on the struck flank, with its mass corrected;
- an end mill fed along X in climb milling;
- no spindle work or speed limit in its machine log.

The seven hidden jobs carry the faults that shop records carry. Each looks like ordinary data, and the documents say
only what was done, never its effect:
- **Speed limit.** The machine's spindle speed limit is set in its log after a spindle rebuild or a drive derating
  (valve-body, programmed at 15000 and limited to 12000 rpm; lever-profile, 16000 and 9000 rpm). The control clamps
  the programmed speed to it.
- **Partly fitted face mills.** On housing-face and pump-cover, the face mill bodies have only some of their pockets
  fitted with inserts.
- **Other FRF quantities.** Tap test files in accelerance (shaft-flat, pump-cover) or in mobility (housing-face).
- **Accelerometer on the opposite flank.** On valve-body and manifold-slot, one axis's accelerometer was on the
  opposite flank, so the data are of the opposite sign.
- **Accelerometer mass not corrected.** On bracket-pocket and lever-profile, the data are not corrected for the
  3.0 g accelerometer, which is a large share of a 12 mm tool's modal mass.
- **Feed along machine Y.** On bracket-pocket, manifold-slot and lever-profile, the feed is along machine Y.
- **Conventional milling.** shaft-flat, manifold-slot and pump-cover are conventional (up) milling.
- **Stepover in percent.** On shaft-flat and lever-profile, the radial depth is given as a stepover percentage.
- **Stickout.** On manifold-slot and lever-profile, the latest tap test is of the same assembly set out to a longer
  stickout.
- **Spindle work.** On valve-body and lever-profile, an earlier test was made before the spindle was rebuilt or
  replaced.

Each check left out or done the obvious way gets jobs wrong, against an allowance of one wrong job
(`authoring/evidence/route_study.txt`). Each figure is the signed deviation from the truth:
- The lowest limit over all speeds (the speed-independent bound) instead of the limit at the speed: all 7 wrong,
  -22.9 to -75.0 percent.
- The programmed speed, not the machine's limit: 2 wrong, lever-profile +118.3 and valve-body -50.1 percent.
- The insert pockets as the teeth: 2 wrong, housing-face -75.9 and pump-cover -64.6 percent.
- Every file taken as receptance: 3 wrong.
- The accelerometer's flank ignored: 2 wrong, manifold-slot +76.0 and valve-body -42.2 percent.
- The accelerometer's mass left in: 2 wrong, bracket-pocket -18.4 and lever-profile -16.3 percent.
- The feed taken along machine X: 3 wrong, -85.2 to +138.4 percent.
- Every operation taken as climb milling: 2 wrong, manifold-slot +155.1 and shaft-flat -79.5 percent.
- The latest test of the assembly, whatever its stickout: 2 wrong, lever-profile -50.3 and manifold-slot -49.1 percent.
- The first test of the assembly at its stickout (before the spindle work): 2 wrong, lever-profile +99.9 and
  valve-body +106.8 percent.
- The records at face value (the programmed speed, the pockets, the latest test of the assembly): 5 wrong.

Every route misses at least two jobs, and every hidden job is missed by at least two routes. On the example, every
record route gives the reference's 1.9949 mm. Only the speed-independent bound differs there (1.0597 mm), and with no
reported answer the example does not expose it (`authoring/evidence/route_example.txt`).

## Reference solution

`solution/chatter.py` is the reference program; `solution/solve.sh` installs it as `/app/output/chatter.py` and runs
it on the example. For one job it does the following:
- **Setup sheet.** Reads the machine, tool assembly, diameter, the teeth that cut (the inserts fitted in a face mill
  body, or the flutes of an end mill), stickout, material, milling direction, feed axis, radial depth (in mm or as a
  stepover percentage) and the programmed speed.
- **Speed.** Takes the speed of the operation as the programmed speed, or the machine's spindle speed limit from the
  log when that is lower.
- **Tap tests.** Uses the latest X and Y pair of the job's assembly at the job's stickout made after the last spindle
  work in the log.
- **Receptances.** Turns each test into the tool-tip receptance:
  - the quantity converted (mobility divided by i omega, accelerance by -omega^2);
  - the sign reversed when the accelerometer was on the opposite flank;
  - the accelerometer's mass removed when the data are not corrected for it: G = Gm / (1 + m omega^2 Gm).
- **Feed axes.** Takes the receptances along and normal to the feed from the machine axes the setup sheet names.
- **Limit.** Computes the zero-order limit of MS-CH clause 2 at the speed of the operation on the measured frequency
  points. For both eigenvalue branches and each lobe it finds the chatter frequencies at which the lobe passes through
  the speed, and takes the lowest positive limiting depth among them.

Run through `tests/grade.py` as the verifier runs a submission, its limits are within 1.05 percent of the truth on all
seven hidden jobs. On the example it gives 1.9949 mm (`authoring/evidence/reference.txt`).

## Verification

`tests/grade.py` runs the submitted `/app/output/chatter.py` on each of the seven hidden jobs (`tests/hidden`; the
agent's image does not contain them). The verifier image has the agent's `/app/data` at the same path, read-only
(`tests/app_data`, written by the same `build.py`), so a program that reads the cutting coefficients from it at run
time behaves as it did for the agent.

How each job is run:
- The program alone and the package are copied to a scratch directory owned by root, where the package is read-only.
- The program runs as the unprivileged user nobody, with only PATH and HOME set, as
  `python3 -I chatter.py JOB_DIR OUT_JSON`, within 600 s, in its own process group.
- When the run ends or times out, its process group and every process of nobody are killed before the output is read.
  The seven runs are sequential, so the worst case (4200 s) fits the 4800 s verifier timeout.
- The instruction states these run conditions, including the 10 minutes and that `chatter.py` must be self-contained.

The output must be a regular file, not a symlink, of at most 65536 bytes. It must hold one JSON object with exactly the
key `stable_depth_mm`, once, a finite positive number (not a string or a boolean; NaN and Infinity are rejected). The
program must exit with status 0. A job whose output breaks any of this is wrong. The instruction states every one of
these rules.

A job is right when its value is within 5 percent of its stability limit. The instruction states the 5 percent as a
requirement. The truth (`tests/hidden/truth.json`, root-only in `/tests`) is computed by
`authoring/provenance/chat.py` on the sealed job as it will be cut: the speed of the operation, the teeth that cut,
the immersion, and the true tool-tip modes of the assembly as it is now on a 0.1 Hz grid. The method is MS-CH's zero-order
solution. The truth is a computation on the sealed job, not on its records.

The single pytest test passes when at most 1 of the 7 jobs is wrong; the allowance of one job is not in the
instruction. `tests/test.sh` does the following:
- Locks `/logs/verifier` to root before grading and again before the reward.
- Writes reward 0 first, and 1 only when pytest exits 0 and the ctrf report holds exactly one test, passed, with none
  failed, skipped, pending or other.
- Writes the per-job results to `/logs/verifier/metrics.json`, where they do not affect the reward.

Every calibration number below is measured by the verifier itself. Each method, route and method-free answer is a
complete JSON-writing program, run through `tests/grade.py` exactly as a submission. `authoring/evidence/common.py`
writes the program file and calls `score()`. It runs as nobody from a scratch copy, as
`python3 -I chatter.py JOB_DIR OUT_JSON`, and grade.py reads and judges the JSON. No evidence script calls a program's
functions directly.

Why 5 percent and at most 1 wrong job:
- **Correct methods.** All are right on every job, within 1.23 percent of the truth
  (`authoring/evidence/method_spread.txt`):
  - the reference;
  - `authoring/evidence/independent.py`, a second program that shares no code with it (within 1.21 percent);
  - three variants of the reference: every second frequency point, the FRF smoothed over three points, and chatter
    frequencies up to 3000 Hz only.

  The second program fits a two-mode model to each FRF and works on the fitted model on a 0.1 Hz grid. It takes the
  eigenvalues numerically from the 2 x 2 oriented FRF matrix, and interpolates each lobe's depth where its explicit
  spindle speed crosses the speed of the operation.
- **Defective routes.** The routes above miss by 16.3 percent or more. Only the records-at-face-value route has a
  smaller miss (lever-profile at -6.1 percent), and it also misses four other jobs by 49 to 76 percent.
- **The tolerance.** 5 percent sits between the correct methods (1.23 percent at most) and every single-check miss
  (16.3 percent or more).
- **The allowance.** One wrong job is allowed so that a sound program with a single marginal job is not failed. No
  route and no method-free answer stays within it.

Method-free answers (`authoring/evidence/constant_null.txt`) are all rejected, each with all 7 jobs wrong:

| Method-free answer | Deviation over the jobs (percent) |
|---|---|
| the example's limit (1.995 mm) for every job | -46.6 to +145.6 |
| 2.5 mm for every job | -33.1 to +207.7 |
| the example's limit scaled by 1 / (teeth x Kt) | -75.6 to +109.6 |

Every hidden job's limit is at least 25 percent from the example's, so the example's answer carries over to none of
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
