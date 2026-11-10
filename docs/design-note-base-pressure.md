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

**Mechanic.** One contractor's order of 4 tests across the fleet, placed once through `vacwork` before any result
is known: `rate-of-rise`, `speed-test`, `rga`, `helium`. Submit-once enforcement copied from
`screen-fatigue-assessment`; the sealed definition and the sudo rule from `impeller-shrink-fits`.

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
- Sound methods: 8, all accepted, widest 2.39 % on the gas load and 1.43 % on the speed (margins 1.67x, 2.10x).
- Defective routes: 17, all rejected. Every route misses >= 2 chambers; every chamber is missed by >= 3 routes and
  by >= 1 route on its cause alone.
- Nulls: every method-free answer gets 0 of 10. No chamber has a free pass.
- Verifier checks: 33 cases, all as the rules say, every one built from the live reference.
- Preflight: 196 checks clean.

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

Zip not yet cut. Probe rounds in progress. The instruction is a draft awaiting Alex's rewrite, with a fact sheet.
