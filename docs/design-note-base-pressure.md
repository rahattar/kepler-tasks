# Design note: base-pressure-diagnosis (Nov 9 2026)

**Why it exists.** `vacuum-pumpdown-time` failed validation on Nov 9 as too similar to `weld-preheat-temperature`,
which was still in review. The two shared everything but their physics: one program at `/app/output/<x>.py`, run
`python3 -I <x>.py JOB_DIR OUT_JSON`, writing a JSON object with one scalar key; seven hidden packages; a tolerance
band with one package forgiven; the same package anatomy (a sheet, certificates, logs, records, an example named
`<thing>-ex`); the same `MS-xx` shop standard framing; the same provenance filenames; and about twelve
document-fault layers of the same kinds. Paragraphs three and four of the two `instruction.md` files were
word-for-word identical once the nouns were swapped. That is the `shrink-fit-hubs` against `flange-torque-spec`
rejection again, so changing the vacuum details would not have cleared it: the shape had to change.

Alex chose to keep the vacuum subject and replace the deliverable, the verification and the mechanic.

**Task.** A one-shot audit sheet, `/app/output/diagnosis.csv`, header `chamber,cause,q_total_mbarl_s,s_eff_l_s`,
one row for each of ten chambers VC01-VC10. Per chamber: which of five mechanisms limits its base pressure, its
total gas load and its actual effective pumping speed, all at one reference condition. No program, no hidden cases.

**Standard MS-BP.** p = Q_total / S_eff on a lumped volume. Q_total is the sum of four mechanisms: wall water
outgassing C_w W(t, T, vent, load), a constant air leak, a trapped volume Q_v0 exp(-t/tau), and permeation
K20 L_seal theta_p(T) through the elastomer seals. S_eff is the turbo curve in series with the high-vacuum port as
fitted. Clause 5 corrects a nitrogen-calibrated gauge for the composition of the gas it is reading. Clause 6 names
the pump as the cause when the actual speed is below 0.75 of rated, and otherwise the largest gas load. The
reference condition is 16 h after an air vent, 20 C, nothing in the chamber.

**Mechanic.** One contractor's test, ordered once through `vacwork` before its result is known, from four kinds:
`rate-of-rise`, `speed-test`, `rga`, `helium`. Forty ways to spend it and one that works - an analysis on VC08,
whose log holds a single pumping time, so nothing in its records separates a trapped volume from wall gas. A
rate-of-rise there gives the gas load but not what the gas is; a helium test finds a real leak but not a trapped
volume. Submit-once enforcement copied from `screen-fatigue-assessment`; the sealed definition and the sudo rule
from `impeller-shrink-fits`.

## Layers (15; chambers in brackets)

Data-only, needing inference rather than reading:
- a cold cathode fouling as a **ramp** against the chamber's reference instrument, which then fails part way
  through, leaving the later pumpdowns to be corrected by the fitted trend (VC02, VC09);
- **crossed gauge serials** on three pumpdowns of two chambers, the certificates right, visible only as the
  mirror-image step in the two chambers' own series (VC03, VC07);
- **a leak against permeation**, both constant in time, separated only by the temperature dependence across the
  log or by the oxygen and argon of an analysis (VC04 against VC06);
- **a trapped volume against wall gas**, exponential against a power law (VC08 against VC01, VC02);
- **a pump with an ordinary gas load**, so an audit that blames gas gets cause and both quantities wrong
  (VC09, VC10);
- **a gauge correction that depends on the answer**: the correction follows from the composition, the composition
  from the split, the split from the corrected pressures;
- **a wall gas load that is not the table's**, by up to a factor of 2.6.

Documented:
- internal surfaces replaced (VC01, VC02, VC06); a seal changed (VC04, VC06); a baffle or trap in the port
  (VC03, VC04, VC05); a turbo that lost speed, dated by the controller (VC09, VC10); a dated recalibration (VC10);
  dry nitrogen vents (VC01, VC02, VC07); fixtures left in the chamber (VC01, VC02, VC10); pumpdowns of different
  lengths and wall temperatures (all).

## Calibration

- Tolerances: cause exact, gas load 4.0 %, speed 3.0 %, **every** chamber right.
- Sound methods: 5, all accepted, widest 1.62 % on the gas load and 1.16 % on the speed (margins 2.47x, 2.58x).
- Defective routes: 18, all rejected. All but one miss >= 2 chambers, and the exception misses its one chamber by
  13 % on the speed, 4.5x the tolerance. Every chamber is missed by >= 3 routes and by >= 1 route on its cause
  alone.
- Nulls: every method-free answer gets 0 of 10. No chamber has a free pass.
- Verifier checks: 33 cases, all as the rules say, every one built from the live reference.
- Preflight: 196 checks clean.

### Probe history

- **Round 1** (budget 4, the example carrying its audited result): **6 of 6 solved it, 10 of 10 each** - three low
  effort and three xhigh. Every one of the fifteen layers was found unprompted. Diagnosis: the probes built the
  forward model, fitted it and iterated until the residuals reached the reading-noise floor, so no layer had to be
  known about - a missed one announced itself as a large residual. The example's published answer let them check
  the whole chain end to end (0.1 to 0.8 %), and no layer was degenerate with a fitted parameter.
- **Round 2** (example answer removed, a residual-invisible layer added, budget 4): low **10/10, 7/10, 10/10**.
  The one that failed blamed the register's port conductance rather than the gauge certificate, and also missed
  two causes. The two that passed each spent a test on the certificate chamber, which is what the spare slots
  bought them.
- **Round 3** (budget 1, VC06 given a third pumpdown so its split is settled by its records): low
  **10/10, 10/10, 9/10**. The one that failed failed on VC01 alone, the certificate layer: shown a throughput test
  reporting 1038 L/s against a rated 915, it concluded the register's port figure was a typo and trusted the
  measurement, so its gas load came out 11.7 % low and its speed 13.4 % high with sub-1 % fit residuals
  throughout. Still 2 of 3, so still above the easiness bar.

- **Round 4** (two more residual-invisible layers: a register naming the wrong pump, and VC01's certificate error
  made determinate by its reference instrument): low **9/10, 9/10, 10/10** - **1 of 3, which was the bar then (0 of 3 since Nov 11).** The
  progression over the four rounds is 3/3, 2/3, 2/3, 1/3. P2 failed on VC01, the certificate; P1 read VC07's
  controller correctly and caught the wrong pump, then over-corrected on the crossed gauge serials and threw away
  CC-7107's real 1.42 factor along with the clerical error, putting VC07's gas load 29 % low. That slip is
  available only because two gauge problems sit on neighbouring chambers.

- **Round 4, xhigh**: **3 of 3, ten of ten each.** All three found every layer: VC07's pump from the controller
  signature, VC01's certificate from the reference instrument it disagrees with, the crossed serials, the fouling
  cathodes, and the one order that works. By `difficulty-calibration.md` a local 3/3 is to be read as too easy,
  so on the repo's own rule this is not shippable yet, even though the easiness side is at the bar. What the
  rounds do show is a real effort gap: low 1 of 3 against xhigh 3 of 3.
- **A fairness gap the xhigh rounds exposed.** All three independently flagged VC04 as their one risk: a source
  constant over a 12 to 24 h window fits a leak and a trapped volume of some hundreds of hours equally well, and
  the standard did not say which to report. That is an unstated convention deciding a graded field, so MS-BP
  clause 3.3 now bounds a trapped volume at 48 h and says a source that does not fall over a pumpdown is a leak.
  The two real trapped volumes are at 6 h and 9 h, well inside it.

### What the probe rounds establish

- **Only the layers no residual can show have ever caught a low-effort probe.** The certificate error has caught 3
  of 11 (M2, N3, P2), every time the same way: told that a measured speed exceeds what the pump and port can
  deliver, they look for something other than the certificate to blame. Every layer that perturbs a residual -
  every document fault, every dated change, every crossed label - was found by every probe, including at low
  effort, because the probes all fit until the residuals reach the reading-noise floor and a missed layer
  announces itself.
- **An invisible layer can also be made fairer by adding a witness.** VC01's certificate error was at first
  ambiguous between a wrong gauge and a wrong port conductance, and both probes it caught chose the port - a
  reading the records could not exclude. Giving VC01 the reference instrument of clause 5, so the two gauges
  disagree by exactly the certificate's error while the controller confirms the register's pump, made it
  determinate without making it easier: it caught another probe in the next round.
- **Two faults of the same kind on neighbouring units make a new slip available.** Catching the crossed gauge
  serials on VC03 and VC07 is routine; what caught a probe was over-correcting - treating the real 1.42
  certificate as part of the clerical error and discarding it too.
- **Tightening a measurement budget does not help much.** Cutting it from four tests to one, so that only two of
  forty orders work, cost the probes nothing: they identified the one chamber that needed the test and spent it
  there. The budget is worth keeping because it is load-bearing and because getting it wrong is fatal, but it is
  not what separates effort levels.
- **The arithmetic held.** Each residual-invisible layer independently catches roughly a third of low-effort
  probes, so three of them put low effort at the bar, which is what round 4 measured. If another task of this
  shape needs hardening, this is the lever: not a tighter band and not a smaller budget, but a record that is
  wrong in a way no fit can see, with a physical consistency check as the only witness.
- **A register volume is not a candidate.** It enters only a rate-of-rise test and nothing else, so getting it
  wrong is invisible and also harmless unless a test is spent there. A port conductance is not a candidate
  either: without a second instrument, a wrong port and a wrong gauge give identical records, so a chamber
  carrying one would be unfair.

## Probe tooling

`tools/mkprobe-vacwork.sh` builds a sandbox for a bundle whose rig is a submit-once order program;
`tools/gradeprobe.sh` grades the sheets with the task's own grader and reports the order each probe placed;
`tools/brief-bpd.txt` is the brief.

## Lessons

- **An outgassing table given per surface makes the records decorative.** In the first design five chambers'
  answers followed from the register and the tables alone and two were defeated by no route at all. Making the
  wall gas load coefficient a *chamber* property identified from its own records is what moved the task from
  reading to inference, and it is what made every other layer load-bearing.
- **A constant scale error is invisible once a coefficient is fitted.** The internals and seal layers bite only
  where entries straddle the change, or through the exponent - not because the area or material is wrong. Design
  identification tasks with that in mind.
- **Date a change more finely than the records it voids.** Monthly controller rows dated a turbo change up to three
  weeks late, which silently contaminated the record-only speed route and made two of the four slots compulsory.
  Weekly rows fixed it and turned the budget back into a choice.
- **An allowance of one forgiven case can make a measurement budget decorative.** Here the reference passed with no
  order at all, because only one chamber truly needed a test. Requiring every chamber is what makes the order
  load-bearing; `plan_sweep.txt` measures it rather than asserting it.
- **Check that every chamber is defeated on the categorical, not only on a quantity.** Two chambers initially
  failed no route except on a number, so their grading would have rested on where the band sat.
- **A duplicated physical constant will drift.** `diagnose.py` carried its own copy of the wall gas composition and
  had drifted 5 % from the generator's, biasing every water-dominated chamber - the Nov 9 verification-drift
  failure in a new guise. Preflight now compares every shared table in the solution and the independent audit
  against the sealed definition, and checks the shipped documents are what the generator writes now.
- **Do not write a banned-name list into preflight.** The obfuscation check reads each file's syntax tree for
  imports of decoding modules, calls to decoding functions and literals that look like encoded data. It exempts no
  file, and its own vocabulary is not an occurrence because it never scans raw text for those names.
- **Fit a rate-of-rise slope over an early window.** Over a whole hour the slope is the gas load averaged over the
  hour, not the load at the reported pumping time; and take the base pressure from the figure the report carries,
  not from the trace's first sample, because the pressure rises a hundredfold across the window.

## Status

**Zip not cut.** Everything else is finished and verified: reference and independent audit both get all ten, five
sound methods accepted at 1.52x and 2.58x margin, eighteen routes rejected, nulls 0 of 10, 33 verifier cases
clean, preflight 196 checks, and a byte-identical rebuild from the provenance. The one thing standing in the way
is the easiness bar: low effort is at 2 of 3 after three rounds of hardening, against a bar of at most 1 of 3
(the bar as it stood then; it is 0 of 3 since Nov 11, with a difficulty band of 0 to 5 of 8).
The measured path to the bar is above; it is Alex's call whether to spend it.

The instruction is a draft awaiting Alex's rewrite, with the fact sheet in `fact-sheet-base-pressure.md`.

---

# STATE OF PLAY — 11 November 2026, 01:00 (mid-rebuild, do not submit)

The bundle on this branch is **part way through a redesign** and will not pass its own preflight. Three checks
fail on purpose (the README's fleet ranges for `tau_h`, `q_total` and `p_base` are stale until the physics is
frozen). Do not package or submit it in this state.

## Why it is being rebuilt

The fourth submission passed every structural and quality check and was then failed on difficulty: **8 of 8
official attempts solved it**, in 16 to 29 minutes of an eight-hour budget, against a bar of at most 5 of 8.

The root cause is one number. MS-BP clause 2 put the reference condition at **16 h**, and all ten chambers have
pumpdowns at exactly 16.0 h. So `q_total` at the reference condition was just *corrected pressure x correct
speed* — a product of two measurements. The mechanism split, which is the only hard inference in the task, was
worth **exactly 0.0%** of the graded answer. That is why every attempt passed, why they clustered at ~1.3% gas
load and ~0.5% speed against 4.0%/3.0% bands, and why `hedge_study` found 27 of 40 wrong attributions still
landing inside the band. The evidence had measured the defect; the author read it as reassurance.

Two framings in the review that are **wrong**, recorded so nobody rebuilds on them:
- "The fleet is 70 observations against 40 unknowns, 20 of them discarded." `p_without_flow_mbar` carries no
  pumping time and no wall temperature, so it is not a gas-load observation. There is no discarded-observation
  problem.
- A table of "cost of a wrong attribution by reference time" circulated with wrong numbers. It called
  `components(cfg, t, 293.15)`, and that function's third argument is the **vent gas**, not the temperature.

## What has been done (step 1 of 4)

- Reference condition **16 h -> 36 h**, off every measured pumpdown time (12/16/20/24/26 h). Changed in all
  three places: `authoring/provenance/fleet.py`, `solution/diagnose.py` (`REF_H`) and
  `authoring/evidence/independent.py` (`REF_HOURS`).
- Trapped volumes into the slow band: VC07 `(4.5e-4, 24.0)`, VC08 `(3.7e-4, 32.0)`, was `(2.0e-3, 6.0)` and
  `(9.0e-4, 9.0)`. A slow trapped volume is nearly flat across a 12-24 h record window, so the records cannot
  separate it from a real air leak and the helium test becomes decisive. It still contributes 32-41% of its
  initial load at 36 h, so `virtual-leak` survives as a dominant cause. Clause 3.3's 48 h bound still covers it.
- The worked example VC00 re-tuned (`wall_factor` 1.15 -> 2.00, seal 240 -> 170 cm): at 36 h its permeation had
  closed to 1.8x and `tune.py` wants 3x. Its stale comment about publishing an audited result is corrected.
- `tune.py` reports 0 failures. All five causes present, every chamber above its specified base pressure.

**Measured effect:** the reference solution now scores **8 of 10**, failing VC08 by -62.6% and VC10 by +9.5%.
The inference is load-bearing for the first time.

## What remains

1. **Rewrite the reference for the slow-tau regime.** Its guards (`TAU_RANGE`, `TAU_SPREAD`,
   `MIN_TRAPPED_SHARE`) and `identify_from_rga` were tuned for 6-9 h trapped volumes. This is why it fails VC08
   and VC10. `independent.py` needs the same treatment.
2. **Couple the fleet.** Outgassing coefficient per surface-treatment/cleaning class, turbo knockdown per
   overhaul batch, trapped-volume tau per trap type — shared across chambers and recorded only as class labels,
   so no chamber is identifiable from its own records alone. Today each chamber is an independent 4-parameter
   fit, which is why getting the model right once wins ten times.
3. **Thin the records** so several chambers are underdetermined alone and one test cannot cover the gaps.
4. **Re-measure everything and retune the tolerances.** 4.0%/3.0% gave the attempts 3x and 6x headroom.
   Rewrite `plan_sweep` to require *both* solvers to pass, so it cannot measure one solver's blind spot again —
   the old sweep claimed 2 of 41 orders work, and 4 of the 8 attempts passed with orders it says fail.

## A defect fixed on the way, worth knowing about

The sealed definition exists three times — `authoring/provenance/`, `tests/sealed/`, `environment/rig/sealed/`
— with **no sync step**. Editing the authoring copy alone leaves the grader scoring against the old truth, which
presents as the solver being wrong by 7-75% on every chamber. Preflight now checks all three copies are
byte-identical. Copy by hand after any edit to `fleet.py` or `bpphys.py`.

## Open, and not resolvable here

Two validators contradict each other on `task.toml`. The blocking structure check requires `category`,
`subcategory` and the three explanations in `[metadata]`; an advisory calls all five unsupported and asks for
them to be removed, and for `task.name` to change from `afterquery/base-pressure-diagnosis`. Acting on that
advisory once already cost a submission with seven blocking errors, so the current bundle satisfies the blocking
checks and keeps drawing the advisory. This needs a dataset owner to arbitrate; do not "fix" it from the
advisory alone.

---

# REVIEW OF 11 NOVEMBER, REPRODUCED

An independent review of `b3bbac9` (`docs/review-base-pressure-2026-11-11.md` on branch
`review/base-pressure-diagnosis`, not merged). Its scripts were extracted to a scratch directory, each was read
before it was run (all are read-only analyses; `perturb.sh` works on copies), and each was run against this tree.
Where a claim changes what the redesign must do, it was also checked with a separate script written for the
purpose rather than the review's own.

**Every finding reproduces. None was refuted.**

## Confirmed

| Finding | Review says | Reproduced |
|---|---|---|
| Speed independent of the split | pump curves flat at base pressure | spread 0.0000% on all ten chambers, 1e-8 to 1e-5 mbar |
| VC09 speed from a matched pair | +0.1% | +0.1% on IG-7209 (own script) |
| VC10 speed from a matched pair | -1.4% | -1.4% on CC-7110 (own script) |
| Permeation is a table lookup | K20 L theta_p, no factor | `bpphys.q_perm` is exactly that |
| Seven chambers from one record, noise-free | VC01 -2.2 ... VC09 -3.5/-2.9 | identical, all seven |
| Same, on the shipped data | within 4% on all seven | each of the seven has a record and mode within 4% |
| Every orderable test at 16 h | | `fleet.AUDIT_TESTS`: all 16.0 h |
| tau hard-coded at 9 h in both solvers | | `diagnose.py` 873, 902, 924; `independent.py` 496 |
| VC08 gas load over tau 24-48 h | -13.8% to +17% | -13.8% to +17.0% (own arithmetic) |
| VC10 with perfect knowledge | +11.1% / +4.2% pooled | +11.1% / +4.2% |
| VC07 with perfect knowledge | +1.2% | +1.2%, tau 25.8 h (true 24) |
| Monte Carlo VC07 / VC10 | 0.73 / 0.45, 0.82 pooled | 0.73 / 0.45; 0.82 pooled with `mc.py` cut at the pump change removed |
| Stale evidence | six of eight, plus fleet_ranges | seven of eight stale; only `null_baselines` unchanged |
| Stale figures | 0/41 orders, 16/40 hedge, 8 UNEXPECTED, margin 0.06x | all four exactly |
| No study requires its baseline | route_study exits 0 at 8/10 | exits 0. `verifier_checks` does exit 1; `route_study`, `hedge_study`, `plan_sweep` do not |
| routes.py copies the pipeline | config_for ... audit | all five functions present |
| independent.py shares heuristics | 0.25, 0.60, 0.08, 2x spec, 1.02, first four rows | all six, line by line |
| VC01 ordered speed test, shared bug | 913.7 L/s, factor 1.00, both divide: -12.5% | identical; `independent.py:462` divides the contractor's file explicitly |
| Reference check is a substring | "1360 L" passes | not caught, and it *satisfies* the failing check (3 -> 2 failures) |
| GATE not tied to the prose | | not caught |
| Unread CSVs exempt | | not caught when mirrored into `tests/app_data` (see below) |
| Basename anywhere passes | `tests/sealed/README.md` | not caught |
| `tests/app_data` unread | | nothing in `grade_audit.py`, `test.sh` or `test_audit.py` reads `/app/data` |
| Instruction says 16 h | | yes |
| vacwork.md vs the reports | "at the reference pumping time" | every report header says 16.0 h |
| audit_note.md | 24 h; two ionization gauges | VC06 has 26 h; three chambers carry one (VC01, VC02, VC09). **Agent-facing.** |
| README fixture list | omits VC04 | VC04 carries a shield set on P2 and P4 |
| Typed 16 h | three in meta.py; hedge_study tau 16 h | three; `hedge_study.py:82` |
| null_best never substituted | | parsed once, substituted nowhere |
| grade_audit.py comment | 1.7x / 2.1x | evidence says 1.52x / 2.58x |

The review listed as **not verifiable** "4 of the 8 attempts passed with orders the sweep says fail". It is
verifiable from the official run data attached on 10 November: the passing orders were VC08 helium x4, VC08
rate-of-rise x1, VC10 rate-of-rise x2 and VC02 rate-of-rise x1, and the sweep of the time booked only VC08 helium
and VC08 analysis as working. Confirmed.

## Nuances added in reproduction

- The VC09 matched-pair route works on the **ionization gauge only**: on the drifting cold cathode CC-7109 the same
  arithmetic gives +14.1%. It still needs no gas-budget fit, and the ionization gauge is the reference instrument.
- An unread CSV in `environment/data` alone *is* caught, but incidentally, by the check that the verifier's data
  copy mirrors the agent's. Mirrored into both, it passes. The exemption is real.
- The shortcut routes all run through the reference's own `front_end`, so they presuppose the instrument and
  configuration layers are solved. The official attempts solved those easily, so the conclusion stands.

## Found in reproduction, not in the review

- `tests/Dockerfile` still carries an internal infrastructure name in a comment ("which harbor uploads here"). The
  earlier sweep for such names covered `.py`, `.md`, `.toml` and `.sh`, and missed Dockerfiles.

## Claims of this note refuted by the review

All of these were stated as fact in the STATE OF PLAY section above. Each is wrong:
- "still contributes 32-41% of its initial load at 36 h": it is 22% (VC07, tau 24) and 32% (VC08, tau 32). The
  32-41% range was computed for tau 32-40, which is not VC07's.
- "nearly flat across a 12-24 h record window": it falls 1.65x (VC07) and 1.45x (VC08). And if it *were* flat,
  clause 3.3 would make the right cause `air-leak`, so flatness was never the property wanted.
- "the helium test becomes decisive": for the cause, not for the gas load, which still depends on tau.
- "changed in all three places": the 16 h regime survives in `hedge_study.py`, `meta.py`, a docstring, `vacwork.md`,
  the instruction and the README.
- The three failing preflight checks are two fleet ranges and the reference-condition check, not three README
  checks.
- VC10's failure "because its guards were tuned for 6-9 h trapped volumes": VC10 has no trapped volume. It is
  wall-against-leak conditioning, and it fails even with perfect knowledge.
- "rewrite the reference" as step 1 of what remains: it cannot reach 10 of 10. VC08 is unidentifiable and VC10
  misses with perfect knowledge on the shipped readings.

## Measured for the redesign

Two measurements made to test the old plan, both exact model, true speeds, 0.6% read noise:

- **Coupling does not pin VC08.** If VC08 shared VC07's trap type and inherited the tau VC07's records give, then
  even with VC08's leak and wall factor known exactly, VC08 is within 4% on 0.58 of draws (95% range -28.4% to
  +4.4%). VC07's own tau estimate spans 14.7-25.9 h. Step 2 of the old plan would not have fixed VC08.
- **One observation past the reference time does.** Adding one VC08 observation at a chosen pumping time:

  | Extra observation at | Leak | P(within 4%) |
  |---|---|---|
  | 8 h | known (helium) | 0.32 |
  | 24 h | known | 0.78 |
  | 40 h | unknown | 0.89 |
  | 40 h | known | 1.00 |
  | 48 h | known | 1.00 |

  The missing information is a long-hold observation and the leak. Measured on VC08 only.

---

# DECISIONS FOR THE REDESIGN (11 November, agreed with Alex)

Supersedes "What remains" in STATE OF PLAY above.

1. **The agent chooses the pumping time of the ordered test**, within fixed bounds that the `vacwork` wrapper
   enforces. It goes in `vacwork.md`'s plan format, not in the instruction. Measured basis: one VC08 observation
   past the reference time pins tau (P = 1.00 at 40-48 h with the leak known); one before it does not (0.32 at 8 h).
   Ordering at exactly 36 h reads that chamber's gas load almost directly; that is the right engineering decision
   and helps one chamber only, so the other nine must be identifiable from their records.
2. **Speed stays the instrument-and-configuration check.** Its band comes from the new sound-method spread, with
   the nearest defective speed route at 1.5x the band or more and no tighter than the stated repeatability supports.
   This adds no difficulty (narrow windows do not); it makes the band honest.
3. **No permeation factor in the documents.** An MS-BP clause explaining one would be a hint in the files (Alex's
   Nov 5 rule) and, being stated, no trap at all. Instead, a **data-only seal layer**:
   - the register's seal material on one chamber is wrong from the start, a clerical error, with no log line;
   - the seal actually fitted is another material in the same table, so the inference lands on a discrete,
     checkable answer;
   - placed on a chamber with seasonal temperature spread (eight qualify, x1.62-1.82 in permeation across their own
     records; VC06 and VC08 do not), where trusting the register gives the wrong cause;
   - kept only if it passes both checks below and a "trust the register's seal" route fails on it.
4. **Shared-coefficient coupling is dropped.** Measured: VC08 inheriting VC07's tau is within 4% on 0.58 of draws
   even in the best case.
5. **Order of work: the checks before the fleet.** `tune.py` gains two measured design rules, and the fleet is
   redesigned until both pass on every chamber, before any solver rewrite or tolerance retune:
   - *load-bearing*: the best single-record shortcut misses by at least 2x the tolerance or names the wrong cause;
   - *identifiable*: a sound solver with the records and the right single test is within tolerance on at least 0.99
     of draws.
6. Also required by the playbook and missing until now: a seed screen, and route counts on lab seeds 5301-5320.
7. `task.toml` metadata advisory: not acted on.

---

# THE REBUILD OF 11 NOVEMBER: WHAT THE EVIDENCE FOUND

Steps 5-7 of the redesign (evidence, prose, packaging). Recorded because several of these were found by the
studies, not planned, and two of them were faults in the reference that the shipped seed hid.

## Found by the studies and fixed

- **The reference overfitted small samples.** With an RGA on VC02 the reference took a trapped volume from
  2026-10-10 (the date of the note that VC02's ionization gauge filament had failed) on four observations and four
  parameters, chi-square zero, and missed VC02 by 17%. A structure is now admissible only if it leaves more
  observations than parameters. The independent audit had the same fault and the same fix.
- **The seed screen caught a spurious trapped volume on VC10.** On 2 of the 20 screened build seeds both audits
  gave VC10 a trapped volume from the date its turbo drive overheated, on one degree of freedom, and missed it by
  10% on the gas load and 15% on the speed. The shipped draw happens not to. The reference now selects by AICc
  (AIC where no structure leaves two degrees of freedom, which is VC01's case), and the independent requires any
  added mechanism to leave two degrees of freedom. After the fix both are right on every chamber on all 21 draws.
  Measured: the reference's VC02 is the loosest chamber across draws (sd about 1.4%, worst 3.6% on seed 5303);
  left as is, inside the band on every draw.
- **The reference took tau by luck where nothing measured it.** With a helium test on VC08 the reference was right
  (-0.1%): its misfit is flat in tau to the fourth decimal, and the grid's minimum landed near 14 h by noise. The
  independent already took clause 3.3's bound in that case. The reference now does too (`tau_flat`: chi-square
  within 1 across the grid), and VC08 with helium is +129% for it, as it should be: helium measures the leak, not
  how fast the trapped volume empties.
- **Both helium readers missed a leak under a permeation ramp.** On VC05 and VC06, whose seals are long, the
  leak region's step sits under a seal's ramp, and the "most of the rise in 30 s" test rejected it, reading the
  leak as zero and pushing the constant load into a trapped volume. The reference now fits each trace as a
  background, a fast rise and a slow rise; the independent fits the trace from 40 s on as a constant plus a ramp
  and takes the step from the constant. Both now read every chamber's leak within a few per cent.
- **VC04's register_seal route grazed.** It missed VC04 alone by 1.94x the tolerance. VC04's seal length went
  from 520 to 600 cm; the route now names the wrong cause there.
- **The plan sweep had collateral damage**: before the fixes above, five off-path orders (an RGA on VC02 at 16 or
  20 h, a rate-of-rise there at 16 h, helium on VC05 or VC06) broke the chamber they were spent on. None does now.

## Retuned

- Gas-load tolerance 4.0% (unchanged), speed tolerance 3.0% -> **3.5%**. Rule: twice the widest deviation any
  sound method reaches on any chamber, rounded up to the half per cent; preflight recomputes it from the record.
  On the records with the inverted gauge equation the spread was 2.00% and 1.25%, giving 2.5% on the speed; after
  the fix below the independent audit's VC09 speed (fitted through the gas budget, so through the gauge
  correction) reaches 1.70%, and the rule gives 3.5%.
- The instruction's two figures were edited to match (16 h -> 36 h, 3.0 -> 3.5 percent). Those are the only
  edits to Alex's text.

## Measured, for calibration

- Orders that carry the reference: 18 of 221, every one a gas-load test (rga, rate-of-rise or speed-test) on VC08
  at 20 to 48 h. The default 16 h does not. The independent audit is carried by exactly the same 18. The design
  tool (`identify.py`) predicted 24-48 h; the solvers do better at 20 h than its noise model allows.
- Routes: 22, all rejected; every chamber missed by at least 5, and VC08 by at least 4 on every laboratory seed.
- Sound methods: 18, all accepted; both audits right on VC08 on all 20 laboratory seeds.

## Other changes

- `tests/app_data` removed (read by nothing), with its Dockerfile copy and the mirror check; preflight instead
  checks that `environment/data` is byte for byte what build.py writes now.
- Instrument repeatabilities are single-sourced in `fleet.py` (`REPEAT`) and stated in `records_format.md` and
  `vacwork.md`, so the figures an agent weights by are the figures the noise was drawn from.
- Every evidence record carries a fingerprint of its inputs on its first line; preflight fails a stale record.
- Preflight's read check is path-aware (directory and name, or the path in the image), and a CSV is exempt only if
  the record definitions or the instruction name it.

## The gauge equation was inverted (found by the probes, fixed)

Three of the first six probes remarked that MS-BP clause 5, p = p_N2 / sum(x_i / K_i), is the reverse of the
physics, and they were right: vacuum_data.md lists K as the gauge's relative sensitivity (H2 0.42, H2O 1.12, Ar
1.29, CO2 1.42, the textbook figures), and a gauge with sensitivity K_i reads sum(K_i p_i), so the true pressure
is p_N2 / sum(x_i K_i). The generator, both audits and the standard all used the inverted form, so the task was
self-consistent but physically wrong, by about 25% on a water-dominated gas between the two forms. A domain
reviewer would reject it. Fixed in `bpphys.indicated`, `diagnose.gas_correction`, the independent audit and
clause 5's text; the records were rebuilt. The truth does not depend on the gauge, and tune.py and both audits
still pass unchanged. Every study was rerun after the fix.

## Local calibration

On the records with the inverted gauge equation (superseded, recorded for the trend): low effort 0 of 3 (each
9 of 10, all on VC07), xhigh 2 of 3 (the miss on VC07). Every probe ordered a gas-load test on VC08 at 36 h.
The one discriminating chamber is VC07: its crossed serials read as a wrong certificate (fit CC-7107 at 1.00
everywhere) and its register names the wrong pump. Every other layer, VC05's wrong register seal included, was
found by every probe.

On the shipped records (gauge equation corrected; these probes were briefed with the 2.5% speed band, the
shipped band is 3.5%, and no probe sheet lands between them): low effort 1 of 3 (R4 solved; R5 and R6 missed
VC07, one on the gas load by -29%, one on the speed by +43%), xhigh 3 of 3 (S4, S5, S6). Across both rounds:
low 1 of 6, xhigh 5 of 6. Every probe again ordered a gas-load test
on VC08 at 36 h, and every miss is on VC07.

Reading for the official run: inside the low-effort bar, but xhigh solves at a rate that puts the official 8
near the top of 1-5 or above it. VC07 is a single point of difficulty. A further layer that no fit residual shows
(as VC01's certificate and VC07's pump are) would be needed to bring it down with confidence.

---

# A LAYER THAT EVERY SIMPLE READING FITS (11 November, afternoon)

Agreed with Alex after the calibration above: add a data-only layer that leaves the fit clean, since every layer
that shows as a misfit was found by every probe.

**VC04: a replacement gauge whose certificate is out.** CC-7104 would not strike on 09-15 and was replaced by
CC-7114, certificate factor 1.00. Its true factor is 0.80 of that, so it reads every pressure high by a quarter.
The old gauge's speed tests (07-08, 09-02) put the pump at rated; the new gauge's (10-07) at 0.80 of rated, while
the controller shows the pump in order throughout. Measured on the reference's own fit:

| Reading | Fit | q | s | cause |
|---|---|---|---|---|
| each entry at the speed tested on its gauge (trust the test) | clean | -0.4% | -19.8% | right |
| rated speed, certificates as issued | clean, chi2 0.3, by a trapped volume dated to the gauge replacement | +10.5% | 0 | wrong (wall) |
| every entry at the latest test | misfit | -9.5% | -19.8% | wrong |
| rated speed, CC-7114 put right by test/rated | clean | -0.2% | 0 | right |

Only the gauge explains both the step in the readings and the low test: a trapped volume cannot change a
throughput test, and the vacuum data say a pump in order delivers its rated speed. The September test on the old
gauge was added after a prototype probe argued that the old gauge might have been reading low before it failed; it
rules that out directly.

Both audits now group speed tests by the gauge they were read on, and treat a certificate as out where its tests
report a speed the pump cannot have: above rated, or below it with the pump in order. New route `rated_speed`
(pump in order at rated, certificates as issued) misses VC04 on the cause; `trust_certificate` now misses VC01 and
VC04.

Prototype probes (xhigh, the layer without the September test): 0 of 3, every one on VC04's speed, two of them
reading the low test as the newly calibrated gauge being right.

Final records: all 23 routes rejected; 18 sound methods accepted with spread 1.99% / 1.70% (tolerances 4.0 / 3.5,
unchanged); 18 of 221 orders work for both audits; seed screen 20 of 20; preflight 349 of 349. Low effort 1 of 3
(U1 solved; U2 missed VC04 and VC07, U3 VC04).
Final records, xhigh 1 of 3 (V2 solved; V1 and V3 took the new gauge's low test, both naming the replacement gauge
as the possible culprit and choosing against it). With the prototype round: xhigh 1 of 6 on this layer, every
miss on VC04's speed; low 1 of 3.

---

# EASINESS PROBE FAILED (1 of 3 low-effort solves, allowed 0): A NEW CORE (11 November, evening)

The official easiness probe solved 1 of 3 at low effort (bar: 0 of 3), in 6 minutes median. Its feedback asks for
a harder core problem, not more of the same. Diagnosis: all 15 probes seen up to then, official and local, spent
the one test on VC08, because VC08's log points at itself (ninefold jump after the bracket work, every entry since
at 16 h). The core inference - which chamber the records cannot settle - was free.

Agreed with Alex: make the obvious chamber settle from its own records, and move the unsettled one where nothing
announces it.

- **Speed tests became readings.** `speed_tests.csv` gains `pumping_time_h` and `wall_temp_c`; records_format.md
  says a test is run on the empty chamber at the end of a pumpdown after an air vent, and that the no-flow pressure
  is the chamber's own base pressure. Both audits take each test's no-flow pressure times its own speed as one
  more gas-load observation. The reference's drift line is no longer carried backwards past the first pairing
  (a 2025 speed test on VC09 had been "corrected" by a factor of 1.8).
- **VC08 (the decoy)** keeps its jump, but its October speed test was taken after a 42 h pumpdown, and that reading
  pins its time constant. `tune.py` measures VC08 settled from records alone (P = 1.00).
- **VC07 (the target).** All its pumpdowns are now at 16 h (the 44 h entry is gone), so its trapped volume reads as
  a constant; only the July speed test, the eve of the refit, shows the constant part is new, and nothing says how
  fast it falls. `tune.py`: records alone P = 0.03; a test at 24-48 h settles it.
- **VC10** load-bearing again after its 2025 speed test was moved to 12 h (at 16 h and 7.4 C it sat at rho near 1).
- The reference now settles tau between its grid points (golden section); the grid's step had put VC07 2.45% out
  under an RGA at 24 h. The independent audit requires an added mechanism to be significant at 1% over the plain
  budget, after the seed screen caught it taking a spurious trapped volume on VC10 on two draws.
- New route `speeds_only` (speed tests read for their speeds alone) misses VC08. `rated_speed` now leaves the
  speed tests aside, since with their readings the fit happened to land VC04 right through a misfit (chi2 77).

Probes on the new core: every one, 3 low and 3 xhigh, ordered VC07 (from the speed test readings and the 07-20
note), and every one then missed VC04's speed (low 0 of 3, xhigh 0 of 3). The decoy did not fool anyone; VC04 is
what stops them, and at 9 of 9 xhigh misses across three rounds it risks 0 of 8 officially. Their stated reasons
were the replacement's "fresh certificate" and the old gauge "failing", both artefacts of my wording, not of the
evidence. Changed: the replacement is a spare head from stores with a 2025 certificate, and the maintenance note
says only that it was swapped.

Probes after the neutral wording (spare head with a 2025 certificate, plain maintenance note): low 2 of 3, xhigh
3 of 3. VC04 is a switch on wording: with the "fresh certificate" and "would not strike" cues every probe failed
it, without them nearly every probe passes it. The decoy fooled no one (12 of 12 ordered VC07). Not shipped;
waiting on a decision about the core.

---

# A FLEET-WIDE HIDDEN FAULT: THE SHOP'S CALIBRATED LEAK (11 November, late)

Agreed with Alex. The layers that separate effort levels are the ones that need more than one chamber (the crossed
serials); every single-chamber call is found by a careful fit at any effort.

- One calibrated leak for every shop speed test (`STATED_FLOW` 0.0200 mbar L/s). From 2026-05-18 it admits 1.14
  of its stated flow (`FLOW_FAULT`), so every 2026 shop test reports a speed 0.88 of the truth on every chamber at
  once, and no pump appears faster than its curve. Nothing in any document says so; `records_format.md` says only
  that the column is the flow the leak is stated to admit. The contractor's tests are unaffected.
- VC03's baffle and VC05's trap are now logged without their conductance, so their speed has to come from their
  post-fit speed tests, put right by the fleet's factor. MS-BP clause 4 makes the rated speed the pump as new in
  series with the port as fitted, so a pump in order behind an unrecorded port is at its rated speed: their
  pump-speed gate is not in question.
- VC01's 2026 test moved to 07-21 so that it is not the first test after the change: its certificate error (1.14)
  almost cancels the leak's factor, and as the first 2026 test it made the changepoint ambiguous. VC00's 2026 test
  moved before the change, so the example stays sound throughout.
- Both audits estimate the factor before anything reads a test: the reference by the least-absolute-deviation split
  of the fleet's speed ratios (medians), the independent by the split with the largest separation of trimmed means.
  Both find 2026-06-30 and 0.879. New route `flow_as_stated` misses all ten chambers.

Probes on the leak fault, low effort: 2 of 3 solved (A1, A3), and all three found the fault themselves ("every
2026 speed test reads about 0.88 of rated on every chamber with a healthy pump"). A2 missed VC03 and VC07 on the
crossed serials. A low-effort run compares every test with its rated speed as a matter of course, so a fault that
shows as a ratio is found, however many chambers it spans.
xhigh on the leak fault: 3 of 3 solved (B1, B2, B3), each finding the fault and correcting VC03 and VC05 by it.

---

# Every local probe, regraded against its own sealed fleet (tools/probe-regrade)

`tools/probe-regrade/regrade.py` grades each sandbox's sheet against the `rig/sealed` fleet that sandbox was built
from, at today's tolerances (4.0 / 3.5); output in `regrade-2026-11-11.txt`. All probes since R1 ran through the
Agent tool with no model override, so on this session's model, claude-opus-5-5, the screen's model; effort as
labelled (R, U, W, Y, A low; S, T, V, X, Z, B xhigh).

- VC04 with the "fresh certificate" and "would not strike" cues (T, U, V, W, X): missed by 13 of 15 (low 5 of 6,
  xhigh 8 of 9); passed by U1 and V2. With neutral wording (Y, Z, A, B): passed by 12 of 12.
- VC01 since the redesign: missed by 0 of 39 sheets (R1 to B3). The three VC01 misses on record are all in the
  earlier multi-test rounds (M2, N3, P2 of L1 to Q3).
- The test: 21 of 21 VC08-era sheets ordered VC08 at 36 h; 18 of 18 on the new core ordered VC07.

---

# MECHANISM A: THE TEST'S CHAMBER UNFLAGGED (11 November, evening)

Agreed with Alex after `docs/trap-analysis-2026-11-11.md` §6.3. `authoring/provenance/auditor.py` runs a
systematic first pass on the agent-visible files (controllers against every model; every speed test against rated,
pooled and split by year; serials against certificate owners; CC/IG ratios; pumping-time coverage; steps at dated
work; face-value budgets with seal and trapped-volume alternatives). On the bundle before this change it flagged
every layer, VC07's core included (controller, crossed serials, one pumping time), which is why every probe
ordered VC07. `auditor-2026-11-11.txt` holds that run.

The change:
- **VC06 holds the core.** The September refit (new electropolished shroud panels, shroud seals renewed in
  nitrile) brings a trapped volume (4.0e-4 mbar L/s at the vent, tau 40 h) present from the refit, so nothing
  steps and the pre-refit entries are void by the change of internals. Of the four pumpdowns since, the air vents
  are at 12 and 14 h and the nitrogen vents at 20 h: the face-value budget reads the trapped gas still present at
  20 h as a leak and its fall between the short and long pumpdowns as the wall gas the nitrogen vents leave out. It
  fits the entries and the October speed test with a chi-square noncentrality of about 0.1, with plausible
  coefficients, and puts the 36 h gas load 17.6 per cent high (the reference with no order). Truth stays
  permeation, dominant 1.88x. The auditor flags nothing on VC06 beyond the 2026 speed ratio every chamber shares.
- **VC07 is a decoy.** Same trapped volume, pump and crossed serials, but its pumpdowns now span 12-24 h and both
  vents, so its own records settle it. VC02 gained a 24 h pumpdown (10-13) so its post-refit records are not open.
- **The order is derived, not asserted.** `diagnose.py --plan` refits every chamber with every trapped volume
  clause 3.3 allows (start of records or any logged work, every time constant up to the bound, every size) and
  keeps the budgets within chi-square 4 of the best; the spread of their 36 h gas loads is how open the chamber is.
  VC06 29.7 per cent, next VC01 9.2 (3.2x); VC06 on all 20 lab-seed rebuilds (lowest 18.0, next at most 10.9).
  `solve.sh` places that order (VC06 rga at 36 h), and preflight checks the evidence runs it.
- Feasibility first (`/tmp` scratch, not shipped): with a 2-parameter plain budget the quiet-miss ceiling over a
  12-22 h window with mixed vents is about 10 per cent at noncentrality 4; confounding vent gas with pumping time
  raises it to 30 per cent at under 1. tau 40 rather than ~26 so that no single-entry route lands within 2x the
  tolerance (identify.py: nearest 8.9 per cent).
- Orders that work: rga or rate-of-rise on VC06 at 30 h or longer (16 h does not).

Follow-ups found by the studies:
- `reference + drop oldest` lost VC06 with four pumpdowns (three left, and the trapped structure inadmissible), so
  VC06 gained a fifth (10-30, nitrogen, 20 h; noncentrality 0.16, face-value miss unchanged at +18 per cent).
- At a 3.0 per cent gas-load band (the old rule on the shipped spread, 1.49 per cent) VC02 fails on three rebuilt
  seeds (up to 3.88 per cent; it did before this change too). The rule is now twice the shipped spread and never
  less than the widest deviation on any screened seed, rounded up to the half per cent: 4.0 and 4.0. The speed band
  moved from 3.5 to 4.0 (twice 1.79); `instruction.md` changed in that one figure.
- VC07's P5 moved from 20 to 24 h so that it is identifiable at the gas-load band (P 0.98 to 1.00).
- `plan_sweep`: a helium test on VC06 also carries both audits (it measures the leak the face-value budget
  overstates). The two audits differ on VC06 rga at 20 h alone, the shortest time that separates the structures;
  the sweep now reports such orders as the edge of the working region rather than a disagreement.

Probes on this bundle (claude-opus-5-5, built before the fifth VC06 pumpdown; graded at 4.0/4.0):
- Low effort, 0 of 3. C1 and C2 ordered a test on VC09 (C2 had estimated VC06's load "known to about 1%") and missed
  VC06 by +18.8 and +17.7 per cent; C3 ordered VC06 at 36 h for another reason (to separate leak from permeation)
  and got it. All three dropped CC-7107's certificate as "inconsistent" instead of uncrossing the serials, and
  missed VC07 (gas load -30 per cent, or the speed +42 per cent, or the cause).
- xhigh, 2 of 3. All three ordered VC06 at 36 h by the planning rule's own reasoning ("the least constrained
  chamber ... fits that matched equally well gave Q_ref anywhere from 4.5e-4 to 6.1e-4"). D1 and D2 also uncrossed
  the VC03/VC07 serials and passed; D3 kept CC-7107 at 1.00 and missed VC07.

---

# OFFICIAL DIFFICULTY RUN 6 OF 8, AND A DECOY ONLY BOTH GAUGES SETTLE (11 November, night)

The official difficulty run on 20261111b (claude-opus-5-5, xhigh) solved 6 of 8 against a band of 0-5. Every pass
did the same thing: profiled the admissible trapped-volume budgets per chamber, saw VC06 at 29.7 per cent against
9.2 for the next, and spent the test there. The two failures ordered VC08 (no profile) and VC07 (and missed VC04's
spare gauge and VC07's pump). So the plan step was the part to make harder.

The change:
- **Two gauge-type sensitivity tables.** The vacuum data now give hot-filament ionization and cold cathode gauges
  their own relative sensitivities; the cold cathode reads water at 0.80 against the ionization gauge's 1.12.
  Clause 5 says K is the gauge type's. Every cold cathode reading needs its own table, and on a pumpdown read with
  both, their ratio measures the wall's share of the gas.
- **VC01 is the decoy.** Since its September reline its air vents are short (12, 14 h) and its nitrogen vent long
  (24 h), VC06's confounding; both gauges were read on every pumpdown, and it has no trapped volume. Profiled on
  the reference instrument alone (clause 5 names the ionization gauge as such) VC01 spreads about 60 per cent at
  36 h, ahead of VC06's 30, so that profile orders VC01 and misses VC06. Read with both gauges, each through its
  own table, VC01 closes to about 3 per cent.
- **The reference** keeps both readings where the cold cathode holds its line. It fits a first budget on one
  reading per pumpdown, divides each pair's composition ratio out of the CC/IG ratio, tests the remainder for a
  drift (a change of more than 4 per cent across the pairings; 2 per cent flagged noise on one seed), and keeps
  every reading the drift does not cloud. Pre-change pairs (VC02's drift evidence) get their composition from a
  plain budget fitted to their own reference readings on the then-surfaces. `determinacy` now works in reading
  space with per-type weights, so a paired pumpdown tells wall water from air.
- **The independent audit** does the same in its own idiom (forward model in log space, so both readings carry the
  composition into its fit directly; composition iterated four rounds).
- **Truth: a change of internals brings its own wall coefficient** (VC01 1.90 to 2.60, VC02 0.70 to 0.45, VC06
  2.30 to 1.60). Before this the fleet kept one coefficient across a reline, and two probes had used that
  regularity, which the documents do not give, to pin VC06 and VC01 from their pre-change records.
- **Routes:** `reference_gauge_only` and `one_sensitivity_table`, each placing the order its own reading of the
  records gives (VC01), then missing VC06. VC04's seal length 600 to 680 cm so that `register_seal` misses VC04 by
  more than twice the band under the cold cathode table.
- **records_format.md:** the shop's reported speed is the flow over the rise taken through the gauge's certificate
  factor, which is what the records have always held (a probe found the unstated factor on VC07's test).

Local probes on this bundle (claude-opus-5-5, graded at 4.0/4.0), before the VC04 seal and drift-threshold changes:
- Low effort, 0 of 3: E1 ordered VC06 but missed VC07's speed (dropped CC-7107's certificate); E2 ordered VC09
  and missed VC06 by +19 per cent; E3 ordered VC08 and missed VC06 and VC07.
- xhigh, 0 of 3: F1 and F3 ordered VC07 (unsure of CC-7107's factor), F2 ordered VC08; all three missed VC06 by
  +19 per cent, F1 also VC07's cause and F2 VC03's speed. None ordered VC01: the decoy did not draw the order this
  round, VC07's instruments did.
