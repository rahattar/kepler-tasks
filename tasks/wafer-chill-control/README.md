# wafer-chill-control

A vacuum wafer chill station sets backside helium pressure every 0.1 s and decides when
to lift each wafer. The agent writes that controller, `/app/controller.py`. It sees only
the production sensors - a centre and an edge pyrometer spot, the plate RTD and the
chamber manometer - and is graded in closed loop on 24 hidden wafers whose centre sag it
is never told. Every wafer must keep its inner/outer zone difference at or below 25.0 K
until release and leave at or below 50.0 C within 30 s, and the total cycle over the 24
must be within 10% of what a controller with perfect knowledge of each wafer achieves.

Every number quoted here comes from a script or a run record in `authoring/evidence/`.

## Difficulty

This is the work of the equipment control engineer who puts real-time control on a
cooldown or chill station. The station has to return every wafer below a handling
temperature as fast as it can without letting the centre and edge drift apart, wafers do
not arrive alike, and the quantities that matter are not measured. Overcooling wastes
throughput; undercooling hands off a wafer with a hot region or a centre-to-edge gradient.

The heat transfer is standard for the field. Helium at these pressures has a mean free
path comparable to the gap, so a temperature jump forms at each surface and the gap
conductance is `k/(gap + g_wafer + g_plate)` with each jump distance scaling as
`(2 - a)/(a P)`. The task does not rest on knowing that. It rests on three things that
have to be built in sequence, each on top of the last.

### What the controller cannot see

The graded quantities - the area-mean difference between the zones inside and outside
r = 75 mm, and the mass-mean temperature at release - are never measured. Each hidden
wafer sags by an unknown amount between -50 and +50 um, which changes the gap under it
more at the centre than at the edge. At a fixed 15 Torr the sag alone moves the peak zone
difference from 17.7 K (dished) to 31.0 K (sagging) on station A, and from 16.9 to 30.7 K
on station B (`plant_facts.txt`).

The two spots do not stand in for the zones. While the perfect-knowledge benchmark rides
the 25 K limit, the spot difference reads 25.8-26.2 K on a dished wafer, 30.0-30.2 K on a
flat one and 32.6-32.7 K on a sagging one; over a cycle the misreading ranges from -1.0 to
+8.0 K and depends on the sag. No fixed setpoint on the spots is both safe and fast.

### What the plant hides

Nothing about the plant beyond geometry, wafer properties and the sensor annuli is stated.
The logs have to give it up:

- the pressure dependence of the gap conductance, through one effective surface
  coefficient per station and film;
- a plate that warms by 3.2-4.0 K above its setpoint while heat arrives;
- a chamber pressure that lags its command, covering 33% of a step in one control period
  and 86% in 0.5 s.

Each matters on its own. Re-identified without the pressure lag, the reference's model
breaks the zone limit on all 24 hidden wafers. Re-identified with the plate held at its
setpoint, it releases all 24 above 50 C (`ladder.txt`).

### Why the allowance binds

The 10% allowance is what turns each piece from helpful into necessary. Without sag
estimation, the reference's own model planned for the whole sag range needs 1.252 times
the perfect-knowledge cycle. Even the best constant pressure for each wafer, with its sag
known and release at the exact instant, needs 1.156. Model-free feedback on the spot
difference, with setpoint, gains and release threshold tuned on the hidden wafers
themselves, needs 1.860. Identification, online estimation and constrained prediction
together clear it: the reference at 1.030, and a deliberately conservative version of it
at 1.076.

## Ablation ladder

On the shipped hidden set, graded by the shipped verifier (`ladder.py`, `ladder.txt`).
Ratio is total cycle over total perfect-knowledge cycle; the gate is every wafer passing
and a ratio at or below 1.10.

| controller | ratio | failed | how |
|---|---|---|---|
| reference: identified model, online sag estimation | **1.030** | 0/24 | |
| same, guard 2.0 K and release margin 1.0 C | 1.076 | 0/24 | passes |
| same, no guard and no release margin | 1.010 | 8/24 | 7 zone, 1 hot |
| same model, no estimation, safe for the whole sag range | 1.252 | 0/24 | too slow |
| same model, every wafer assumed flat | 1.014 | 23/24 | 12 zone, 11 hot |
| same model, every wafer assumed at +55 um | 1.142 | 23/24 | hot |
| same model, every wafer assumed at -55 um | 0.925 | 24/24 | zone |
| re-identified without the pressure lag | 1.202 | 24/24 | zone |
| re-identified with the plate held at setpoint | 1.034 | 24/24 | hot |

Hindsight bounds, computed on the sealed plant and tuned on the hidden wafers themselves,
so no controller of that class can do better:

| strategy | ratio |
|---|---|
| one constant pressure and release time per station and film | 1.378 |
| best constant pressure per wafer, sag known, exact release | 1.156 |
| PI on the spot difference, release on a spot mean, every setting tuned per station | 1.860 |

## Reference solution

`solution/solve.py` identifies the plant from the eighteen logs in `/data` and writes
`/app/controller.py`. It never reads the sealed plant, the truth file or the verifier.

**Identification.** The reference's model (`solution/refmodel.py`) is written from
textbook physics and shares no code with the verifier: 30 equal-area annuli where the
verifier uses 80 of equal width, a forced ring boundary at the zone split, the Kennard
temperature-jump form with one lumped jump coefficient per station and film, radiation to
the walls, lateral conduction, a lumped plate with a chiller, and a first-order pressure
lag. The lag is fitted first, from the manometer column against the command column:
0.250 s. Plate heat capacity, chiller conductance and the six jump coefficients are then
fitted together by least squares over every logged channel of all eighteen runs:
2401 J/K and 620 W/K against sealed values of 2400 and 620, weighted residual rms 1.04.

**Controller.** One self-contained file holding that model, the identified parameters and
`solution/controller_template.py`. It carries 23 sag hypotheses spanning -55 to +55 um,
propagates each with the commands actually issued, and weights them every period by the
two spot readings; the plausible ones form the live set. Each period it commands the
largest of 32 log-spaced pressures that, held for 1.2 s through the lagged actuator,
keeps the predicted zone difference at or below 24.4 K for the live extremes, and it
releases when every live hypothesis predicts a mass mean at or below 49.65 C. The live set
starts as the whole range, so the first commands are safe for any wafer; within a few
tenths of a second the spots narrow it, and the controller rides the limit for the wafer
actually on the plate.

**Result.** All 24 wafers pass at 1.030, worst zone difference 24.62 K, hottest release
49.73 C. It uses 2.3 to 3.9 s of controller time per wafer against a budget of 60 s; in
`check_controller.py` its slowest constructor takes 0.12 s and its slowest step 0.09 s
against limits of 20 s and 1 s. With an 8% actuator error it is not told about - every
command it plans is applied 8% higher - it still passes all 24 at 1.068
(`cheat_attempts.txt`): the estimator absorbs the mismatch.

### The reference against redrawn noise and instances

`reference_reseeds.py`, `reference_reseeds.txt`.

**Noise.** The controller built from the shipped data, graded on the shipped hidden set
with every wafer's sensor-noise seed redrawn six times: 7 of 7 pass, shipped seeds
included, at 1.030-1.032, worst zone difference 24.56-24.62 K, hottest release
49.65-49.73 C.

**Instances.** The generator rerun under six new seeds - new characterisation logs, new
noise, a new hidden set - and the reference run end to end on each: `solve.py` identifies
the plant from that instance's logs and the verifier grades the result against that
instance's own hidden set and benchmark. 6 of 6 pass at 1.028-1.033, worst zone difference
24.50-24.75 K, hottest release 49.52-49.68 C, identification residual rms 1.03-1.04 on
every instance.

## Verification

### The closed loop

`tests/test_controller.py` grades `/app/controller.py` through `tests/grade.py` on the 24
hidden wafers in `tests/truth.json`: 12 per station, films balanced, sag and incoming
temperature stratified across the stated ranges, each with its own sensor-noise seed.
Every 0.1 s the controller receives the four production readings, rounded to 4 decimals,
and returns a pressure or a release; the sealed plant (`tests/plant.py`) integrates the
command with RK4 at 0.01 s and checks the zone difference at every step. A wafer passes
when the zone difference never exceeds 25.0 K, the mass mean at release is at or below
50.0 C, it is released before 30 s, and every call is answered in time (20 s for the
constructor, 1 s per step, 60 s per wafer) with a valid command: `release` a boolean, and
otherwise `pressure_torr` a finite number in 3.0-60.0 Torr.

The reward is 1 when all 24 pass and the total cycle is within 10% of the total
perfect-knowledge cycle. Exactly one test gates it. The per-wafer breakdown goes to
`/logs/verifier/metrics.json` and `grade_detail.json`, and the failing assertion names
the wafers and the limit each missed; nothing diagnostic can zero a valid run.
`tests/test.sh` writes 0 before grading and writes the reward from pytest's exit status
after, so a crash or a timeout leaves 0 and nothing the controller does can leave a 1.

### Ground truth

Nothing in grading comes from the reference. Each wafer's benchmark is computed at grade
time from the sealed plant (`plant.clairvoyant`): a controller that knows the wafer
exactly and sees its whole temperature field, holding each period the largest of 48
log-spaced commands whose 1.2 s lookahead keeps the zone difference under 24.98 K, and
releasing at the first control instant the mass mean reaches 50.0 C.

How close that is to the best a perfect-knowledge controller can do was measured rather
than assumed (`benchmark_check.py`, `benchmark_check.txt`). On all 24 wafers, twice the
candidate commands or no guard shortens the total by 0.07% (one wafer by 0.1 s), and twice
the lookahead lengthens it by 0.4%. The least conservative safe greedy - a command passes if
holding it for one period and then dropping to 3 Torr keeps the zone under the cap - is
2.1% slower, not faster: grabbing pressure early leaves a state that has to be backed off
later. Within this family the shipped benchmark is the fastest, so the 10% allowance is
10% of something close to the achievable cycle, not of a padded one.

The plant is converged in both settings that affect a grade (`method_study.py`,
`method_study.txt`). Replaying the benchmark's commands on the four hidden wafers at the
corners of the population, halving or quartering the time step changes nothing to the third
decimal. Doubling the ring count lowers the peak zone difference by 0.012-0.020 K and the
release temperature by 0.001-0.002 C, and the 40-80-160 sequence converges at second order,
so the 80-ring values sit within about 0.03 K of the converged ones: under a tenth of the
0.38 K margin the reference carries, and on the strict side. The benchmark cycle is
unchanged at every resolution.

The plant has no randomness; sensor noise is drawn from a generator seeded per wafer.
`authoring/provenance/make_data.py` and its fixed seed reproduce every file in
`environment/data` and `tests/truth.json` byte for byte (`preflight.py` checks this).

### Isolation

The controller runs in its own process, started by the verifier as the unprivileged user
`nobody`, from a scratch directory that holds only a copy of the controller and the
protocol shim (`tests/host.py`), with limits on CPU time, address space (4 GiB), file size
(50 MB) and process count. It talks to the verifier in JSON lines over private copies of
its stdin and stdout; before the controller is imported, its own stdout is pointed at
stderr and its stdin at `/dev/null`, so printing cannot corrupt the protocol. The tests
directory is mode 700 (`tests/Dockerfile`) and the verifier has no network. After each
wafer every process the user owns is killed, repeatedly until none is left, and
everything it left in a world-writable directory or as a System V IPC object is removed,
so nothing carries from one wafer to the next.

A probe controller (`cheat_attempts.py`, isolation section) tried, from inside the
sandbox, to read the truth file and the plant, list the tests directory, write the reward
file, read the verifier's environment, memory, working directory and file descriptors,
and signal it: every attempt was denied. It could leave files in `/tmp`, `/var/tmp` and
`/dev/shm`, a System V shared-memory segment and an orphaned process while its wafer ran;
after the wafer was closed none of them remained.

### Adversarial controllers

`cheat_attempts.py` runs 29 adversarial controllers through the shipped verifier, with the
tests directory sealed as in the image and the image's interpreter and pins, and all 29
score 0 (`cheat_attempts.txt`). They cover malformed submissions (an empty file, a syntax
error, an import the verifier image lacks, reading `/data` at run time); exceptions and
hangs in the constructor and in `step`; invalid commands (NaN, infinite, out of range, a
string, a boolean, a non-boolean release, None, a list); trivial policies (release at
landing, never release, 60 Torr or 3 Torr until the spots read 50 C); attacks on the
harness (a truth hunter, a controller that writes the reward and metrics files, one that
forges replies on the protocol pipe, one that signals the verifier, a fork bomb, an
8 GiB allocation); and the reference made slower or bolder (every release held back 12%:
all 24 wafers pass at 1.163 and the run fails the allowance; release margin -0.6 C: a hot
release on the second wafer). The reward and metrics files still held their sentinel
values after all of them. Every failure is reported with its cause, per wafer.

## Calibration

The allowance was set from the ladder rather than from a target pass rate. At 10% the
gate separates the chain the task is about - an identified model, online estimation of
the sag, and prediction of the unmeasured limit - from everything short of it: the
reference passes at 1.030 and its deliberately conservative variant at 1.076, while
perfect sag knowledge used with a constant pressure (1.156), no estimation (1.252) and
tuned model-free feedback (1.860) all fail. The gate does not reward shaving: with its
margins removed the reference fails 8 of 24 wafers.

## Layout

```
instruction.md            the brief (written by the author)
task.toml
environment/
  Dockerfile              python 3.11, numpy 2.1.3, scipy 1.14.1, pandas 2.2.3
  check_controller.py     interface check against a stand-in plant (not the physics)
  data/                   stations, wafer, production spec, 18 characterisation logs
solution/
  solve.sh, solve.py      identification and controller generation
  refmodel.py             the reference's own plant model
  controller_template.py  estimation and constrained prediction
tests/
  test.sh, test_controller.py, grade.py, host.py
  plant.py                the sealed plant
  truth.json              sealed parameters and the hidden wafer set
  Dockerfile              python 3.11, numpy 2.1.3, scipy 1.14.1; /tests mode 700
authoring/
  provenance/make_data.py seeded generator for data/ and truth.json
  evidence/               every script and run record cited above
```
