"""Writes README.md and task.toml from one copy of each explanation, so the two cannot drift apart.

    python3 -I meta.py          print the three explanations
    python3 -I meta.py --write  write ../../README.md and ../../task.toml
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TASK = os.path.dirname(os.path.dirname(HERE))

DIFFICULTY = """In practice this is the work of a vacuum process engineer auditing a shop's chambers: naming what
limits each one's base pressure and quantifying it, so that the shutdown can be planned around the chambers worth
opening. The engineer has the chambers' own records and a single contractor's test that has to be ordered before its
result is known. Its research analogue is the identification of vacuum systems from operating data: the
steady gas balance p = Q / S_eff of a lumped volume, water desorption from chamber walls and its temperature
dependence, permeation of atmospheric gas through elastomer seals and the composition it admits, the emptying of a
trapped volume, gas corrections for nitrogen-calibrated gauges, and residual gas analysis read as a mixture of
sources.

The chambers and records are synthetic, written by `authoring/provenance` (`bpphys.py`, `fleet.py`, `docs_bp.py`,
`build.py`) from a sealed definition. They are realistic in their numbers:
- Chambers of 900 to 5200 L, on turbomolecular pumps of 360 to 1480 L/s through ports of 420 to 2600 L/s.
- Effective pumping speeds of 124 to 943 L/s.
- Elastomer seals of 120 to 900 cm, in nitrile, fluoroelastomer and perfluoroelastomer.
- Turbo controllers reporting rotor frequency, drive power and bearing temperature weekly, against the maker's
  figures for a pump of that model in order.
- Internal surfaces of 2.6 to 11 m2, electropolished, machined or bead blasted, with anodised aluminium shields.
- Wall gas load coefficients of 0.6 to 2.6 times the outgassing table's nominal figure.
- Real air leaks of 7 x 10^-6 to 3.6 x 10^-4 mbar L/s, and trapped volumes emptying with time constants of 6 and
  9 h.
- Total gas loads of 8.4 x 10^-5 to 2.1 x 10^-3 mbar L/s, and base pressures of 1.8 x 10^-7 to 3.4 x 10^-6 mbar,
  every one of them above the chamber's specified base pressure.
- Two to six recent pumpdowns per chamber, of 12 to 24 h, in a shop whose air runs from 25 C in July to 14 C in
  November, with gauge readings repeatable to 0.6 per cent.

The reference condition is the same for every chamber: 16 h from the start of roughing after an air vent, the
chamber wall at 20 C, nothing in the chamber. Each chamber's limiting cause is the mechanism with the largest gas
load there, except that a chamber whose actual speed is below 0.75 of its rated speed is limited by its pump
whatever its gas load is doing.

The example chamber, VC00, has sound records throughout: one gauge, a speed test that still describes its pump, no
work in the maintenance log over the period of its log, and no load on any pumpdown. It is there to show the
format of the records and that they can be sound. **No audited result is given for it**: MS-BP clauses 2 to 7 fix
every convention the audit needs, so a worked answer would add nothing but an end-to-end check of a whole audit
against a known figure.

The ten chambers carry the faults that shop records carry. Each looks like ordinary data, and the documents say
only what was done, never its effect. Nine of the layers are settled by the data alone:
- **A fouling cold cathode.** On two chambers a cold cathode reads progressively low. The drift is a ramp and never
  a step, so it shows only as a slow trend in the ratio to the chamber's reference instrument, and on both the
  reference instrument fails part way through, leaving the later pumpdowns to be corrected by the fitted trend
  (VC02, VC09).
- **Crossed gauge serials.** Two chambers have each other's gauge serial in the log for three pumpdowns. The
  certificates are right, the two factors differ by 42 per cent, and the only sign is the mirror-image step in the
  two chambers' own series on the same dates (VC03, VC07).
- **A leak against permeation.** Both are constant in pumping time and both admit air, so only the gas load's
  temperature dependence across the log, or the oxygen and argon of a residual gas analysis, separates them
  (VC04 against VC06).
- **A trapped volume against wall gas.** Both decay, one exponentially and one as a power law, and on the chamber
  whose log holds a single pumping time nothing but the composition of its gas can tell them apart - which is
  what the one test the audit can order is for (VC08 against VC01, VC02).
- **A pump with an ordinary gas load.** Two chambers are limited by speed while their gas loads are unremarkable
  and wall-dominated, so an audit that puts every shortfall down to gas names the wrong cause and reaches the wrong
  figure for both quantities (VC09, VC10).
- **A gauge correction that depends on the answer.** The correction of MS-BP clause 5 follows from the composition,
  the composition follows from the split of the gas load, and the split follows from the corrected pressures, so
  the cause and the quantities have to be settled together.
- **A wall gas load that is not the table's.** Every chamber's coefficient differs from the outgassing table's
  nominal figure, by as much as a factor of 2.6, so the table sizes a pump but does not audit a chamber.
- **A gauge certificate that is wrong, and that no residual can show.** On one chamber the calibration laboratory
  issued the factor wrong. The error cancels in the gas load - every pressure the certificate yields is low by the
  same factor and every speed it yields is high by it, so Q = p S_eff comes out right and the gas budget fits to
  the reading noise - and it shows nowhere else except in the speed, which comes out 14 per cent above what the
  chamber's pump in series with its port can deliver. MS-BP clause 4 says a pump delivers at most its curve, so
  the chamber's own throughput tests contradict its certificate. Which instrument is out is settled rather than
  guessed: the chamber also carries the hot-filament gauge that clause 5 makes its reference instrument, and the
  two disagree by exactly that factor, while its controller figures confirm the pump the register names. A fit
  that reaches the noise floor is not evidence that the answer is right (VC01).
- **A register that names the wrong pump, which no fit can see.** On one chamber the register names a pump two
  sizes up from the one that is fitted. Nothing in the gas budget depends on it, because the speed comes from a
  throughput test, so every fit is as good as ever; what depends on it is the rated speed, and with the register's
  pump the chamber's sound speed comes to 0.64 of rated and clause 6 calls the pump the cause. The controller
  reports the rotor frequency, drive power and bearing temperature of the pump that is actually turning, and the
  vacuum data give those three figures for each model, so the record of what is fitted is there to be read
  against the register (VC07).

Eight more are recorded somewhere in the documents and have to be found and applied:
- **Internal surfaces replaced**, so the register's surface no longer applies and the entries before the work
  cannot be pooled with those after it (VC01, VC02, VC06). Note that a constant error in the surfaces is absorbed
  by the fitted coefficient; what bites is pooling records from both sides of the change.
- **A seal changed**, so one permeation constant does not serve the whole log (VC04, VC06).
- **A baffle or trap fitted** in the high-vacuum port, so the chamber's rated speed is not the register's and a
  sound pump is not judged against a conductance it no longer has (VC03, VC04, VC05).
- **A turbo that has lost speed**, dated by the controller's weekly rows, which voids every speed test taken
  before it (VC09, VC10).
- **A dated recalibration** of a gauge, which the certificate carries and the log does not (VC10).
- **Dry nitrogen vents** on some pumpdowns, after which the wall gas load is a quarter of what an air vent leaves
  (VC01, VC02, VC07).
- **Fixtures left in the chamber** on some pumpdowns, adding their own area to the outgassing (VC01, VC02, VC10).
- **Pumpdowns of different lengths and wall temperatures**, which have to be referred to one condition before any
  of them can be compared.

Each check left out or done the obvious way gets chambers wrong, and every chamber of the fleet must be right
(`authoring/evidence/route_study.txt`). Seventeen routes, one per layer, are each rejected; each misses at least
two chambers; each chamber is missed by at least three routes; and each chamber is missed by at least one route on
its cause alone, so no chamber's grading turns on where the tolerance is drawn. Taking the records at face value -
the register's surfaces, seal and port, the latest speed test, the logged serials, every entry pooled, the table's
gas load and no gauge correction - gets all ten wrong.

The audit test is load-bearing and measured to be so (`authoring/evidence/plan_sweep.txt`). There are forty ways
to spend it - four kinds of test on ten chambers - and one of them is right: a residual gas analysis on VC08,
whose log holds a single pumping time, so that nothing in its records separates a trapped volume from wall gas.
A rate-of-rise there gives the whole gas load but not what the gas is; a helium test finds a real leak but not a
trapped volume; and a test spent on any other chamber is spent where the records already answer. Every one of the
other nine orders in that record is rejected, as is placing no order at all."""

SOLUTION = """`solution/diagnose.py` is the reference audit and `solution/solve.sh` places the order and runs it.
For each chamber it does the following.

- **The chamber as it stands.** The register entry, changed by every maintenance row on or before the audit date:
  internal surfaces replaced, a seal changed in material or length, a trap or baffle fitted in the high-vacuum
  port. The seal is kept as a dated history, because a seal changed part way through the log means one permeation
  constant will not serve every entry.
- **Which records still describe it.** Base-pressure entries are kept from the last change of internals onwards,
  one per pumpdown, preferring the hot-filament gauge where a chamber carries both. Where a cold cathode reads
  progressively low against that reference instrument, the ratio is fitted as a straight line in days and carried
  forward to correct the pumpdowns the reference instrument did not see. A speed test is kept only if no trap was
  fitted after it and the controller shows no step in drive power or bearing temperature since; a step voids it,
  because the pump it measured is not the pump now. Where a gauge serial in one chamber's log belongs to another
  chamber's certificate and that chamber's log carries this one's serial, the two are read back the right way
  round.
- **The speed.** From an ordered speed test, or from an ordered rate-of-rise test as the gas load it measures
  divided by the base pressure it reports; failing either, from the latest surviving speed test; and failing that,
  from the chamber's own records before the turbo changed, by identifying the gas budget there against the speed
  test that still held and dividing the same budget, evaluated at a later entry's condition, into that entry's
  true pressure.
- **The gas budget.** Each entry's nitrogen-equivalent pressure is its reading times the certificate factor in
  force; the true pressure follows from the composition by MS-BP clause 5, and the entry's total gas load is that
  times the effective speed. The loads are fitted to C_w W + Q_perm + Q_L, with W the nominal wall shape of the
  entry from the outgassing table, its pumping time, vent gas, wall temperature and any fixture it names, and
  Q_perm computable from the seal. Since the correction depends on the split and the split on the correction, the
  two are iterated to a fixed point, and the linear fit is solved with every coefficient held at or above zero.
- **A trapped volume, or not.** Where the log spans more than one pumping time, the constant model is compared
  with one carrying a decaying trapped volume, over a grid of time constants from 2 to 48 h, keeping only those
  whose exponential is comparable across the entries and whose trapped volume still carries at least 8 per cent of
  the gas load at the reference condition. It is accepted on evidence: a residual gas analysis whose nitrogen and
  oxygen outweigh its water, with the oxygen short of what an elastomer would pass, or failing an analysis a clear
  improvement in fit.
- **A log of one pumping time.** Where the log holds only one, the wall gas load cannot be separated from the
  constant part by the log alone and the split comes from the composition: only the wall admits water, so the water
  the analyser reads fixes the wall's load; the analyser's partial pressures are true pressures, so their sum times
  the speed is the whole gas load; permeation is computable; and what is left is air through a channel, a leak
  unless the chamber was sound when it was first speed-tested and has been worked on since, in which case it is a
  trapped volume. All of it is done at the test's own pumping time and wall temperature.
- **The reference condition and the cause.** The fitted budget is evaluated at 16 h, 20 C, an air vent and no
  load, with the surfaces and seal the chamber has on the audit date. The cause is the pump where the actual speed
  is below 0.75 of the rated speed of the chamber as it is now, and otherwise the mechanism with the largest load.

The order it places is a residual gas analysis on each of the two chambers whose own records cannot settle their
cause, and a speed test on each of the two whose turbo has changed since its last speed test.

Run through `tests/grade_audit.py` as the verifier reads a submission, the reference gets every chamber right, with
its gas loads within 1.4 per cent of the truth and its speeds within 1.5 per cent
(`authoring/evidence/reference_run.txt`)."""

VERIFICATION = """`tests/grade_audit.py` reads the submitted `/app/output/diagnosis.csv` and compares it with the
sealed fleet. The truth is computed from `tests/sealed/fleet.py` and `tests/sealed/bpphys.py` at grading time, from
the chamber's true volume, pumps, port, surfaces, seal, wall gas load coefficient, leak and trapped volume as they
are on the audit date, by MS-BP's model at the reference condition. It is never taken from running the reference
solution, and `authoring/evidence/preflight.py` checks that the sealed files under `tests/` and
`environment/rig/` are the provenance files byte for byte.

The sheet must be a regular file, not a symlink, of at most 100000 bytes of ASCII text: the header line exactly
`chamber,cause,q_total_mbarl_s,s_eff_l_s`, then one row for each of the ten chambers with none repeated, missing
or unknown; the cause one of MS-BP's five names, spelled as the standard spells it; the gas load and the speed
finite numbers inside generous ranges. Blank lines and surrounding spaces are ignored and the rows may be in any
order. Anything else is rejected, with a reason, and no submission crashes the grader. The instruction states
every one of these rules.

A chamber is right when all three of its fields are right: the cause matches exactly, the gas load is within 4.0
per cent of the truth and the speed within 3.0 per cent. The sheet is accepted when every one of the ten chambers
is right. The instruction states the two tolerances; it does not say how many chambers must be right.

Why these tolerances, and why every chamber:
- **Correct methods.** Eight of them are accepted, each a complete sheet scored through this grader
  (`authoring/evidence/method_spread.txt`): the reference on the order it places and on three other sound orders,
  including one that buys no test for the chambers whose turbo has changed and works their speed out from their own
  records instead; `authoring/evidence/independent.py`, a second audit written from the documents alone that shares
  no code with the reference, solving the whole budget by a nonlinear least squares in the logarithm of the gas
  load with the gauge correction inside the residual and unmixing all six species of an analysis by non-negative
  least squares; and three variations of the reference. Over every one of them and every chamber the widest
  deviation is 2.39 per cent on the gas load and 1.43 per cent on the speed, so the tolerances stand at 1.7 and
  2.1 times the spread of sound work.
- **Defective routes.** Nineteen routes, each the reference with one check left out or done the obvious way, are
  all rejected (`authoring/evidence/route_study.txt`). All but two miss at least two chambers, and each of those
  two misses its one chamber decisively: trusting a gauge certificate that the chamber's own throughput tests
  contradict puts its speed 13 per cent out, four and a half times the tolerance, and taking the pump the register
  names rather than the one the controller reports gets the cause itself wrong. No route is rejected by a chamber
  that merely grazes a band. Every chamber is missed by at least three routes, and by at least one route on its cause alone; a cause
  is right or wrong whatever the tolerances are, so no chamber's grading rests on the band.
- **Every chamber.** The allowance of one wrong chamber that earlier tasks carried is not used here, and the
  reason is measured (`authoring/evidence/plan_sweep.txt`): with an allowance of one, the audit test is not
  load-bearing at all, because the reference passes with no test ordered. Requiring every chamber makes the one
  chamber whose own records cannot settle its cause decide the sheet, which is what the test is for. It is not a
  knife edge: every sound method gets all ten right, with the margins above.

Method-free answers are all rejected and none of them gets a single chamber right
(`authoring/evidence/null_baselines.txt`): the worked example's audited result copied onto every chamber; each of
the five causes given to all ten; the latest reading times the latest speed test; the specified base pressure times
the latest speed test; and the register's rated speed with the gas load it and the specification imply. No chamber
has a free pass.

`authoring/evidence/hedge_study.txt` records what a wrong attribution does. The total gas load is the total
whatever it is attributed to, so on most chambers a sheet that names the wrong mechanism still has its gas load
inside the band; those chambers are decided by the cause, which is graded on its own and cannot be hedged.

Malformed sheets and edge cases are all built from the current reference at run time, never hard-coded, and scored
by the same grader the verifier calls (`authoring/evidence/verifier_checks.txt`). Thirty-three cases all behave as
the rules say: a sheet that is a symlink, a directory or absent; no header, a renamed column, the columns
reordered, an extra column; a row missing or repeated; an unknown chamber; a cause outside the list or in the
wrong case; a gas load that is not a number, NaN, infinite, negative, zero or far out of range; a speed of zero,
far out of range, or a boolean; an empty file; bytes that are not ASCII; a sheet padded past the size limit; and a
chamber nudged just inside and just outside each band. Preflight fails if any case in that record did not behave as
the rules say.

The single pytest test decides the reward. `tests/test.sh` writes 0 to the reward file before grading starts, locks
`/logs/verifier` to root before grading and again before the reward, and writes 1 only when pytest exits 0 and the
ctrf report holds exactly one test, passed, with none failed, skipped, pending or other. A crash, a timeout or a
missing sheet all leave 0. Per-chamber results go to `/logs/verifier/metrics.json`, where they do not affect the
reward. The verifier pins numpy 2.1.3, scipy 1.14.1, pandas 2.2.3, pytest 8.4.1 and pytest-json-ctrf 0.3.5, runs in
its own environment without network, and keeps `/tests` at 700 so the sealed fleet is not readable.

In the agent's image the agent works as its own user and can write only to `/app/output`; `/app/data` is read-only.
The audit test order and the sealed definition belong to a separate contractor user, and the agent reaches the
order through one sudo rule that allows nothing but its status and submit commands. The order is charged to the
contractor's state file before any report is written, and a state that cannot be read counts as already placed, so
no test can be had twice."""


def readme():
    return """# base-pressure-diagnosis

A coating and thermal-processing shop audits the ten vacuum chambers that are not reaching their specified base
pressure. For each chamber the audit names what limits it and quantifies it, under the shop's standard MS-BP.

The chamber is a lumped volume, p = Q_total / S_eff, and MS-BP splits the gas load into four mechanisms: water
outgassing from the internal surfaces, which decays as a power of the pumping time and rises steeply with
temperature; a real air leak, constant in both; a trapped volume emptying as a single exponential; and permeation
of atmospheric air through the elastomer seals, constant in time, steeply temperature dependent and enriched in
oxygen by the elastomer. The effective speed is the turbo pump in series with the high-vacuum port as fitted. A
chamber whose actual speed has fallen below 0.75 of its rated speed is limited by its pump, whatever its gas load.

Everything is referred to one condition: 16 h from the start of roughing after an air vent, the chamber wall at
20 C, nothing in the chamber.

The deliverable is `/app/output/diagnosis.csv`, with the header `chamber,cause,q_total_mbarl_s,s_eff_l_s` and one
row for each of VC01 to VC10: the limiting cause, the total gas load at the reference condition in mbar L/s, and
the chamber's actual effective pumping speed there in L/s.

The records are the chamber register, the base-pressure log, the shop's throughput speed tests, the turbo
controllers' weekly rows, the maintenance log, the gauge certificates and the shop's daily climate record, with the
standard and the shop's vacuum data in `docs/` and an example chamber's records, without a result, in `example/`.

Beyond the records there is one contractor's test, ordered once through the `vacwork` command before its result is
known, from four kinds: a rate-of-rise, a throughput speed test, a residual gas analysis and a helium leak test.

## Difficulty

%s

## Reference solution

%s

## Verification

%s
""" % (DIFFICULTY, SOLUTION, VERIFICATION)


def task_toml():
    return '''schema_version = "1.4"

artifacts = ["/app/output/diagnosis.csv"]

[task]
name = "afterquery/base-pressure-diagnosis"
description = "Audit the ten vacuum chambers of a coating shop that are missing their specified base pressure: for each one name the mechanism that limits it and report its total gas load and its actual effective pumping speed at the standard's reference condition, from the chambers' own records and one contractor's test order of four tests placed before any result is known."
authors = [{ name = "Alireza Bafandeh", email = "rahattar@gmail.com" }]
keywords = [
    "vacuum-technology",
    "base-pressure",
    "outgassing",
    "permeation",
    "residual-gas-analysis",
    "system-identification",
]

[metadata]
author_name = "Alireza Bafandeh"
author_email = "rahattar@gmail.com"
author_organization = "MEMC"
author_profile = "https://www.linkedin.com/in/alireza-bafandeh"
research_advisor = ""
referred_by = ""
conflicts_of_interest = "I am employed by MEMC (GlobalWafers), a silicon wafer manufacturer; this task has no connection to my employer's products, processes or data. It uses only published vacuum technology (the steady gas balance of a lumped volume, pump speed curves, water outgassing laws, permeation through elastomers, gauge gas corrections and residual gas analysis) on synthetic chambers and records. I also author evaluation tasks for other AI benchmark programs; this task shares no data, code or scenario with them."
domain = "engineering-sciences"
field = "mechanical-engineering"
subfield = "vacuum engineering and gas dynamics"
category = "Science"
subcategory = "Mechanical & Aerospace Engineering"
tags = [
    "vacuum-technology",
    "base-pressure",
    "outgassing",
    "permeation",
    "residual-gas-analysis",
    "system-identification",
]
expert_time_estimate_hours = 8
relevant_experience = """I am a control scientist and thermal engineer with a PhD in mechanical engineering. Vacuum and gas-handling systems of crystal growth and thermal processing equipment, identifying their models from operating records, and the fault diagnosis that turns those records into maintenance decisions are part of my work on industrial equipment and of my teaching. The chambers and records are synthetic."""
difficulty_explanation = """%s"""
solution_explanation = """%s"""
verification_explanation = """%s"""

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
''' % (DIFFICULTY, SOLUTION, VERIFICATION)


def main(argv):
    if "--write" in argv:
        with open(os.path.join(TASK, "README.md"), "w") as f:
            f.write(readme())
        with open(os.path.join(TASK, "task.toml"), "w") as f:
            f.write(task_toml())
        print("wrote README.md and task.toml")
        return 0
    print(DIFFICULTY)
    print()
    print(SOLUTION)
    print()
    print(VERIFICATION)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
