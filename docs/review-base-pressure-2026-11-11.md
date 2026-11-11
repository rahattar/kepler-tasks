# Review: base-pressure-diagnosis, branch base-pressure-diagnosis at b3bbac9 (11 Nov 2026)

A read-only review of the mid-rebuild bundle. Nothing in `tasks/base-pressure-diagnosis` was changed. Every number
below was measured on a copy of the tree; the scripts that measured them are in `tools/review-bpd/`, and each
finding names the one to run. The design note was treated as a claim and checked, not assumed.

**Headline.** At 36 h the mechanism split is load-bearing on only three chambers, and on those three it is not
identifiable within the band. The other seven fall out of a single record and the tables. VC08 is unsolvable by any
method with any one test, and VC10 is unsolvable on the shipped readings even with perfect knowledge. Rewriting the
reference (step 1 of "What remains") cannot reach 10 of 10; the fleet has to change.

## Priority 1: shortcuts

**The speed never depends on the split.** The pump curves are flat at base pressure, so S_eff is a constant per
chamber.
- Eight chambers read it from a surviving speed test, once the reading-level corrections are made.
- VC09 and VC10 get it from two pumpdowns at the same pumping time on either side of the pump change, with one
  Arrhenius factor at E = 30 kJ/mol: +0.1% (VC09, ionization gauge, P1 to P3) and -1.4% (VC10, P1 to P2). No
  gas-budget fit is needed.

**Permeation is a table lookup, not an inference.** The truth is K20 L theta_p with no chamber factor, and the
reference computes it the same way ("Neither needs a measurement"). The four-way split is three unknowns: C_w, the
leak and the trapped volume. The "leak against permeation (VC04 against VC06)" layer is decorative.

**Seven chambers from one record** (`short.py` and `short2.py` on the shipped data,
`onerec_noisefree.py` without noise). Take the latest kept entry's corrected pressure times the speed, subtract the permeation the
seal table gives, and take the rest either as a constant leak (wall at the table's own figure) or as wall gas; carry
it to 36 h and 20 C. The cause comes out right on all seven.

| Chamber | Mode | Error on the shipped data | Error noise-free |
|---|---|---|---|
| VC01 | rest is wall | -2.8% | -2.2% |
| VC02 | rest is wall | -0.4% to +1.9% | -0.4% |
| VC03 | rest is leak | +2.0% | +3.0% |
| VC04 | rest is leak | +1.9% | +2.8% |
| VC05 | either | +1.8% | +1.4% |
| VC06 | rest is leak | -1.9% | -2.7% |
| VC09 | either | -2.1% | -3.5% |

The only judgement left is wall versus constant, which the time trend of two records settles.

**Where the split matters, it is not identifiable** (`mc.py`, `ideal.py`).
- **VC08 is underdetermined.** Every record and every orderable test is at 16 h, so nothing measures tau. With
  helium giving the leak exactly, the gas load at 36 h runs from -13.8% at tau 24 h through 0% at the true 32 h to
  +17% at 48 h. An analysis leaves the same freedom, and a rate-of-rise gives only Qv/tau. The reference's -62.6% is
  its hard-coded tau = 9 h, and `independent.py` hard-codes the same 9 h.
- **VC10 fails with perfect knowledge.** A fit given the true model, true speeds, true gauge factors and the true
  gas correction, run on the shipped readings, misses by +11.1% using the entries after the pump change and by
  +4.2% pooling both pump eras. With exact model and 0.6% read noise, P(within 4%) is 0.45 post-change and 0.82
  pooled. VC10 has no trapped volume; its failure is wall against leak conditioning, not "guards tuned for 6-9 h
  trapped volumes".
- **VC07** is +1.2% with perfect knowledge on the shipped draw, but P(within 4%) across draws is 0.73.

## Design-note claims, checked

Wrong:
- "still contributes 32-41% of its initial load at 36 h": exp(-36/tau) is 22% (VC07) and 32% (VC08).
- "nearly flat across a 12-24 h record window": the trapped volume falls 1.65x (VC07) and 1.45x (VC08) between
  12 and 24 h. If it were flat, clause 3.3 would make the right answer `air-leak`.
- "the helium test becomes decisive": for the cause, not for the gas load.
- "changed in all three places": the 16 h regime is still in `hedge_study.py:82` (tau 16 h, qv0 x e), in `meta.py`
  (three typed "16 h"), in the docstring of `diagnose.at_reference`, in `vacwork.md`, the instruction and the
  README.
- The three failing preflight checks are two fleet-range checks and "the instruction or the standard fixes the
  reference condition" (the instruction still says 16 h), not three README checks.

Confirmed:
- The reference scores 8 of 10, VC08 -62.6% and VC10 +9.5%.
- `tune.py` reports 0 failures; all five causes present; every chamber above its specification.
- The trapped-volume values (4.5e-4, 24 h) and (3.7e-4, 32 h).
- Both recorded corrections: `components()` takes the vent gas third, and `p_without_flow_mbar` carries no pumping
  time or wall temperature.

Not verifiable here: "4 of the 8 attempts passed with orders it says fail" needs the official run data.

## Priority 2: claims without measurements

**Six of eight evidence files are stale against the current definition.** Re-running every study: only
`null_baselines` is unchanged, and `fleet_ranges` is the one preflight catches. `reference_run`, `method_spread`,
`route_study`, `plan_sweep`, `hedge_study` and `verifier_checks` all differ. Now:
- the reference gets 8 of 10;
- every sound method is rejected, margin 0.06x;
- 0 of 41 orders work;
- 16 of 40 hedge cases stay in the band (27 recorded);
- 8 verifier cases are UNEXPECTED.

`meta.py --check` passes because it compares the README with the stale files.

False whatever the rebuild does:
- Leak against permeation as a data-only layer (README and task.toml), as above.
- "Fixtures left in the chamber (VC01, VC02, VC10)" leaves out VC04 (shield set on P2 and P4).
- `independent.py` "written from the documents alone": see Priority 3.
- "Each check left out ... gets chambers wrong": no route covers the dated recalibration (VC10) or leak against
  permeation.
- Hedge study: "on most chambers ... quantity right" counts cases (27 of 40), not chambers; it is 16 of 40 now.
  "not one of the 40 is accepted" is a tautology, since a wrong cause fails the chamber by definition.
- "14 per cent above": the throughput test shows 13.4% (1038.3 against 915.5); 14% is the certificate factor.
- Agent-facing `audit_note.md`: "twelve to twenty-four hours" (VC06 has 26 h) and "two chambers carry an
  ionization gauge" (three do: VC01, VC02, VC09).
- `vacwork.md`: tests are run "at the reference pumping time of MS-BP clause 2", but every report says 16.0 h
  (`fleet.AUDIT_TESTS`).

Typed by hand where they could be computed:
- the three "16 h" in `meta.py`;
- the rated-speed fraction (0.75), "42 per cent", "14 per cent", "0.64 of rated", "a factor of 2.6" (duplicates
  the computed fleet range), "a quarter";
- the layer counts "Nine" and "Eight";
- "both are spent on", "the other order that works, a helium test", "a residual gas analysis on VC08" (assume two
  orders, both on VC08);
- the three variation names;
- "none of them gets a single chamber right": `null_best` is parsed but never substituted;
- the `grade_audit.py` comment "1.7x ... 2.1x" (the file says 1.52x and 2.58x);
- "every one of the ten chambers": GATE is not tied to the prose.

## Priority 3: studies that do not measure what they claim

- **No study requires its baseline to pass.** With the reference at 8 of 10, `route_study` exits 0 and prints
  "all 19 routes rejected; every chamber defeats at least 3 routes", with VC08 and VC10 "defeating" all 19
  trivially. `hedge_study` and `plan_sweep` inherit the same flaw. A route should count against a chamber only
  where the baseline gets that chamber right.
- **`routes.py` is a copy of the reference pipeline** (`config_for`, `speed_for`, `points_for`, `identify`,
  `audit`). All 19 routes and 3 of the 6 sound methods run through it. It matches `diagnose.py` on all 40 orders
  today (checked), but nothing enforces that, and the planned trapped-volume rewrite will make them diverge.
- **`independent.py` is not independent.** It repeats the reference's undocumented heuristics: the "sound then,
  worked on since" test at 2 x specification with tau = 9 h, the trapped-volume thresholds 0.25, 0.60 and 0.08,
  the certificate slack 1.02, and pump identification from the first four rows within 0.02.
- **A shared bug, concretely.** An ordered speed test on VC01 reports 913.7 L/s (truth 915.5) and its header gives
  the gauge factor as 1.00. Both solvers still divide it by VC01's certificate error and land 12.5% low, so
  `plan_sweep` books "a speed test on VC01" as an order that fails. Requiring both solvers to pass (step 4) would
  not catch it.
- `null_baselines` omits the shortcut family that solved the last official run (corrected reading x correct speed)
  and the single-record routes above.
- `method_spread` prints absolute deviations with a "+" sign.

## Priority 4: preflight, perturbation-tested

Run with `tools/review-bpd/perturb.sh NAME 'command'`.

Caught:
- sealed copies differing (fleet.py, bpphys.py);
- REF_H and E_W drift in the solution and the independent audit;
- the instruction's tolerances, including against Q_TOL;
- pins, the zero-first reward write in `test.sh`, `category`;
- a base64 import or a `fromhex` call;
- an edited document;
- the hedge-coverage and band-case lines;
- an unread file with a new name.

Not caught:
- **stale evidence**: the baseline state, and the failure class of every earlier rejection;
- **the reference-condition check is a substring test**: adding "VC00 (1360 L)" while "16 h" stays makes it pass;
- GATE changed to 9;
- any unread CSV (CSVs are exempt wholesale);
- an unread file whose basename appears anywhere in the bundle, for example `tests/sealed/README.md`;
- a dynamic import such as `__import__("co" + "decs")`, low practical risk.

## Also

- The three sealed copies are byte-identical (md5).
- The shipped data is exactly what `build.py` writes now (`diff -r`).
- `tests/app_data` is copied into the verifier's `/app/data` "for the record" and nothing reads it.
- The metadata advisory was not acted on, as asked.

## Reproducing

From the repo root, with numpy 2.1.3 and scipy 1.14.1:

    python3 -B tools/review-bpd/split.py      # noise-free alternative fits per chamber
    python3 -B tools/review-bpd/short.py      # single-record and simple routes on the shipped data
    python3 -B tools/review-bpd/short2.py     # every record, both modes, with the cause
    python3 -B tools/review-bpd/onerec_noisefree.py  # the same routes on the noise-free truth
    python3 -B tools/review-bpd/mc.py         # identifiability by Monte Carlo, exact model
    python3 -B tools/review-bpd/ideal.py      # perfect-knowledge fit on the shipped readings
    PY=python3 tools/review-bpd/perturb.sh gate9 "sed -i 's/^GATE = len(IDS) /GATE = len(IDS) - 1 /' tests/grade_audit.py"

`TASK=/path/to/tasks/base-pressure-diagnosis` points the scripts at another tree. They import the task's own
`solution/diagnose.py` and sealed definition, so they measure whatever the tree holds when they run.
