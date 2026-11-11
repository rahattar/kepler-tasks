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
  made determinate by its reference instrument): low **9/10, 9/10, 10/10** - **1 of 3, which is the bar.** The
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
is the easiness bar: low effort is at 2 of 3 after three rounds of hardening, against a bar of at most 1 of 3.
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
