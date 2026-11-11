# Rejection patterns and validation failures

## Team lead's list (Oct 18, 2026): the most common reasons tasks are rejected
1. **Tolerance inside the noise of correct methods.** The reference may even fail its own gate on some seeds.
2. **Accuracy bars the solver cannot see.** A tolerance or threshold that is stated nowhere.
3. **Unstated conventions decide the score.** Index bases, centring, boundary placement.
4. **Shipped data that is wrong without a warning.**
5. **Shortcuts that skip the science.** Noise columns that give back the noiseless signal, shipped fits.
6. **Results that don't separate good attempts from bad.** Every trial lands on the same answer, or the only
   failures are tiny overshoots.
7. **Puzzles, answer files, spec transcription, or recovering planted constants from a synthetic record.**
8. **Not a scientific result.** Schedules, staffing or cost plans don't count.

## Design rules we take from this
- Set the tolerance from the spread of all sound methods; a method is unsound only if it is wrong in the truth.
- Keep a wide gap (aim for 2x) between the worst sound method and the nearest unsound one.
- Difficulty must come from structure (evidence to go and get), never from tightening the band.
- Every source the solver might trust and the grader does not must be signalled as unreliable in the documents.

## Similarity rejections
- wafer-chill-control (Oct 4): too similar to wafer-chill-recipe.
- shrink-fit-hubs (Nov 9): too similar to flange-torque-spec. The overlap was joints J01-Jnn, friction measured
  on a budgeted rig, a maintenance log and one number per joint in JSON. Reworked as impeller-shrink-fits:
  a different subject, a CSV deliverable with two quantities per part, and a dilatometer lab.
- vacuum-pumpdown-time (Nov 9): too similar to weld-preheat-temperature, which was still in review. The overlap
  was the whole skeleton, not the subject: one program at `/app/output/<x>.py` run as
  `python3 -I <x>.py JOB_DIR OUT_JSON` writing one JSON scalar; seven hidden packages; a band with one package
  forgiven; the same package anatomy and `MS-xx` standard framing; the same provenance filenames; and about twelve
  document-fault layers of the same kinds. Paragraphs 3 and 4 of the two instructions were word-for-word identical
  once the nouns were swapped. Reworked as base-pressure-diagnosis: same vacuum subject, but a one-shot CSV with a
  categorical and two coupled quantities per unit, every unit required, and a blind measurement order.
- Rule: each new task must differ from the whole catalogue (docs/catalogue.md) in subject AND in deliverable
  shape and verification.
- Rule: two tasks in flight at once must differ from **each other**, not just from the catalogue. Build the second
  one against the first's instruction text, not only against the catalogue's one-line descriptions.
- Rule: before building, write the two instructions' middle paragraphs side by side with the subject nouns
  normalised. If they read the same, the shape is the same, whatever the physics is.

## Validation failures, Nov 9 (impeller-shrink-fits 20261109b)
**Blocking:**
- **Security:** preflight.py held the programme names base64-encoded for a banned-name scan and exempted the task
  name. That counts as obfuscation and self-check evasion. Rules: no base64, rot13 or encoded strings anywhere in
  a bundle, and no programme-name scan in preflight.
- **Verification explanation:** verifier_checks.py hard-coded an old reference sheet, so its output showed the
  valid variants as UNEXPECTED while the README claimed they were accepted. Rules:
  - build every verifier-check case from the current reference at run time;
  - make preflight fail if verifier_checks.txt contains UNEXPECTED;
  - rerun every evidence script after any change.

**Advisory (open):**
- task.name should use the benchmark's required prefix rather than "afterquery/"; ask Alex for the exact
  string.
- category/subcategory and the three explanation fields may belong only in README.md, not task.toml.

## Bundle structure failures, Nov 10 (base-pressure-diagnosis 20261110)
**Blocking, all three in task.toml:**
- `verifier-not-separate` — `[verifier] environment_mode` unset, so harbor defaulted the verifier into the
  shared container.
- `network-mode-missing` — `[environment] network_mode` unset, so the agent's egress was undeclared.
- `verifier-network-missing` — `[verifier.environment] network_mode` unset, so the verifier's offline
  grading was undeclared.

Cause: `task.toml` generation moved into `authoring/provenance/meta.py`, and the generator was written from
scratch rather than from the predecessor's file. The three sections were dropped and replaced with a single
invented key, `[verifier] network = false`, which harbor does not read. It survived preflight because
preflight's own check was written from the same mistaken assumption and matched that key with a regex over
the file's text. Both the generator and its check were wrong in the same way, so they agreed.

- Rule: when moving a generated file into a generator, diff the generated output against the file it replaces
  before trusting it. `meta.py --write` then `git diff task.toml` would have shown four lines replacing twenty.
- Rule: check structural config by **parsing** it, never by regex over the text. A regex confirms a string is
  present; it cannot tell you the key is one the consumer reads. Preflight now loads `task.toml` with
  `tomllib` and asserts each key by path, including that no bare `[verifier] network` key exists.
- Rule: a preflight check and the thing it checks must not come from the same assumption. Where a sibling task
  already carries the pattern, copy the sibling's check too.
- Rule: carrying a known-good block forward beats rewriting it. The three sections were correct in
  vacuum-pumpdown-time and in all 34 other tasks; only the rewritten one was wrong.
- Rule: before packaging, run the submitter's own structural checks against the **unpacked archive**, not the
  working tree.

## Task quality failures, Nov 10 (base-pressure-diagnosis 20261110, second submission)
Five blocking, two advisory. Every one was prose asserting something the code did not do, except the
extraneous files, which were the reverse: files shipped that no prose claimed and nothing read.

**instruction clarity.** The instruction said `/app/data/example/` held the chamber's audit result while
`about_this_chamber.md` and `records_format.md` both said no result is given. It also narrated the installed
packages. Both came straight from `docs/fact-sheet-base-pressure.md`, which still told Alex to write them: the
fact sheet had not been updated when the example stopped publishing a result.

**no extraneous files / task authoring dir.** `environment/rig/sealed/seed.json`, `tests/sealed/seed.json` and
`tests/sealed/truth.json` rode along from the predecessor task, read by nothing. The seed is a constant in
`build.py` and the truth is recomputed by the grader, so all three were records of a generation step, not
inputs.

**solution explanation quality.** It described an order of four tests on four chambers. The budget had been cut
to one test and `solve.sh` orders one analysis on VC08. The text was written when the budget was four and never
revisited.

**verification explanation quality.** It claimed eight accepted methods at 2.39% and 1.43%; the study had six
at 2.64% and 1.16%. It also drew conclusions from `hedge_study.txt`, in which **all 32 cases reported
TypeError** - a blanket `except Exception` caught the study's own bug and printed it as "not reachable", so a
broken study looked like a finding.

**README (advisory).** The same stale figures, plus "a residual gas analysis on VC08 is the only order that
works" when a helium test on VC08 also passes.

**task.toml schema (advisory).** `task.name` still carries the `afterquery/` prefix, and `[metadata]` carried
`category`, `subcategory` and the three explanations, which the benchmark does not read.

### Rules
- **Never type a measured number into prose.** `authoring/provenance/meta.py` now parses the evidence files for
  every figure the explanations quote and refuses to emit text with a placeholder it could not fill.
  `meta.py --check` regenerates and diffs, so re-running a study without rewriting README.md fails preflight.
  A number that is typed is a number that will drift; this is the second rejection caused by one.
- **No blanket `except` in a study.** A study's exception is a bug in the study. Let it crash. If a case really
  can be unreachable, that has to be a deliberate, named outcome, and preflight now fails on any evidence file
  containing Traceback, TypeError, ValueError, KeyError, IndexError, AttributeError, "not reachable" or
  UNEXPECTED.
- **A study must not keep its own copy of the reference's pipeline.** `hedge_study.py` had a stale copy of the
  audit's front end; the reference now exposes `diagnose.front_end()` and the study calls it. A copy of a
  pipeline measures the copy.
- **Sweep the whole space, or do not quote a fraction of it.** `plan_sweep.py` listed ten hand-picked orders
  while the prose claimed a result over all forty. It now enumerates every order the budget allows and counts
  the ones that pass.
- **Every file in a container is read by something.** Preflight now walks `environment/` and `tests/` and fails
  on any file nothing in the bundle names, and on any `seed.json` or `truth.json` in either tree.
- **When a design decision changes, grep the prose for it.** Cutting the budget from four tests to one left
  stale claims in the solution explanation, the README, the task description and `vacwork.md`'s example plan.
  The decision was made in `fleet.py`; nothing pointed at the six places that described it.
- **Update the fact sheet in the same change as the thing it describes.** The instruction's two failures were
  faithfully copied from a fact sheet that was correct a week earlier.

## Bundle structure failures, Nov 10 (base-pressure-diagnosis, third submission)
Eight errors, from two causes.

**Seven were self-inflicted.** The previous submission's *advisory* notes said `category`, `subcategory` and the
three explanations were "unsupported benchmark fields" and that the explanations "belong in README sections". I
removed them. The blocking structure check requires all five: every task ships the full metadata block. I had
deleted part of a block that all 34 other tasks in the repo carry, on the strength of a note that was not
blocking, and the fields came straight back.

**One was a leak.** `afterquery` appeared at `meta.py:399` and `:401` - a bare `NAME_PREFIX = "afterquery"`
constant and a comment about it - which I had introduced the round before while trying to make the prefix easy to
change in response to another advisory. The term is allowed only as the task's own name, `afterquery/<task>`.
The advisory that prompted the constant was itself resolved by this error: `afterquery/base-pressure-diagnosis`
is the correct value, so there was never a string to get from Alex.

### Rules
- **An advisory is a suggestion; a structure check is the contract.** Never remove a field, a section or a file
  because an advisory calls it unsupported. Advisories are written per task and can be wrong about the dataset.
  If an advisory contradicts what every other task in the repo does, the other tasks win, and the advisory goes
  in this file as an open question instead of into the bundle.
- **This is the second time a rewrite of a known-good block caused a blocking failure.** The Nov 10 first
  submission lost three `task.toml` sections by regenerating them from scratch; this one lost five fields by
  acting on an advisory. The block is known-good: leave it alone, and diff `task.toml` against a sibling task's
  before submitting.
- **Do not refactor in response to an advisory.** Making the prefix a named constant to be helpful created the
  codename leak. The smallest change that answers an advisory is usually no change plus a note.
- Preflight now checks, derived from `task.toml` rather than from a list written inside the bundle: the full
  metadata block is present, `category` is `Science`, `subcategory` is non-empty, each README section matches its
  metadata field, and the task-name prefix appears nowhere except as the full task name. Deriving the term from
  the one field permitted to hold it avoids keeping a list of programme names in the bundle, which was itself a
  blocking failure on Nov 9.
- The bundle no longer names internal infrastructure, points at repo files outside it, or narrates its own review
  history in comments. A bundle should read as a self-contained piece of work.
