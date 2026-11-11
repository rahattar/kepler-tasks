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
