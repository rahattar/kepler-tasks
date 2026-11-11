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

## Instruction-quality rejection, Nov 9 (cooler-fouling-assessment 20261023c)
"The result does not reflect genuine solving." Two faults, and they compounded:
- The pass band was printed for the solver (instruction.md and `assessment_requirement.md` both carried the same
  0.04 m2K/kW the grader uses), so runs stopped looking for the answer and started looking for a number inside the
  band.
- One quantity was not determined by the files at all: nothing said how the ribbed tubes' film-coefficient gain
  relates to their friction gain, so after measuring one ribbed unit every candidate law still fitted. Runs took
  "the midpoint between the extreme hypotheses as a minimax choice" and argued it was inside the stated band. One
  of the laws they entertained would have put E7 about 0.042 out.
- Fixed by deleting the band from every agent-visible file and putting the relation in the retube note
  (`h_ribbed/h_plain - 1 = K (f_ribbed/f_plain - 1)`, one K for the rib form, the same for all three tube lots, K
  not given), plus the crossflow-velocity / baffle-spacing relation in the design sheet for the same reason on E5.
  Shipped as cooler-fouling-assessment-20261109b.zip (20261109 was the same fix at the old 3 h agent budget).

**Rules taken from this**
- A band the solver can read is only safe where every graded quantity is determined by the files. Where a reading
  has to be taken, keep the band out of the agent's reach: state the quantity, the units and that one committed
  figure per item is wanted, and nothing about how close is close enough. This overrides list item 2 above, which
  came from tasks where the method was fixed and only the arithmetic was at stake.
- Every quantity the grader scores must be derivable from the agent-visible files. An empirical correlation the
  solver cannot derive (a film/friction tie, a geometric factor) has to be written down in a document, in its
  functional form, with the coefficient left to be measured on the budgeted tests.
- Ship a hedge_study: for each reading, the figure each reading gives and whether one number satisfies two of
  them. Where the gap is under 2x the band, the band must not be visible.

## Easiness-screen failure, Nov 9 (cooler-fouling-assessment 20261109b)
Solved 2 of 3 low-effort screening runs, median 3 minutes; more than 0 solves is below the difficulty bar. Why it
was easy, from the three traces:
- The maintenance log was a recipe. Each unit's mechanism was named on its own line and each mechanism's physics
  was spelled out in its own document, so ten units reduced to ten one-line corrections.
- Every unit the records could not settle was flagged plainly and there were exactly as many as there were slots,
  so the allocation was a one-to-one mapping found by reading, not reasoning (the one failing run picked the wrong
  three and failed only on that unit).
- The fouling history was one straight line plus a step on one unit, so a single fit over the window passed on
  nine of ten units.
- Nothing else bit: per-unit films sat within 2.5 per cent of the design split, so the design sheet used flat for
  every unit passed on its own.

**Rules taken from this**
- Count the units the records cannot settle against the slots. Equal numbers make the allocation a reading
  exercise. Keep the count above the budget and put the escape in a record as a fact, not as the inference: two
  new coolers sharing one vendor rating, so one slot serves both (20261109c).
- Do not let a document do the solver's reasoning. State that the vendor ran its program once for the pair and
  that the works certificates agree to a per cent; do not add "so a test on either carries to the other".
- Make the fouling history need its own model, not just a line: with the chlorine-free days and the shock dose both
  dated in the log, one line through the record now misses three units by up to 0.33 and the wrong one of the two
  events misses five by up to 0.50.
- Make the per-unit clean reference load-bearing. At 10 per cent scatter the design split used flat fails two
  units; at 2.5 per cent it passed and a whole layer could be skipped.
- Watch the sound-method spread while hardening: moving the shock dose a week earlier (longer post-event segment,
  same extrapolation reach) brought the worst sound method back from 0.031 to 0.026 against the 0.04 band.

## Similarity rejections
- wafer-chill-control (Oct 4): too similar to wafer-chill-recipe.
- shrink-fit-hubs (Nov 9): too similar to flange-torque-spec. The overlap was joints J01-Jnn, friction measured
  on a budgeted rig, a maintenance log and one number per joint in JSON. Reworked as impeller-shrink-fits:
  a different subject, a CSV deliverable with two quantities per part, and a dilatometer lab.
- Rule: each new task must differ from the whole catalogue (docs/catalogue.md) in subject AND in deliverable
  shape and verification.

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

## Grader-design failure caught by a probe, Nov 10 (relief-valve-adequacy)
A decimal-places cap copied from impeller-shrink-fits rejected a whole sheet because one answer, a thermal
expansion area of 0.052 mm2, was written to more than six decimals. The run had every valve right but one and was
graded 0 of 9. The cap made sense where it came from, a honed bore quoted to the micrometre; it makes none for a
computed area that spans four orders of magnitude across the deliverable.

**Rules taken from this**
- Cap decimals only where the physical quantity has a resolution. Otherwise bound the input by range and file
  size and let the solver write as many figures as it likes.
- Where a deliverable's values span orders of magnitude, say in the instruction how many significant figures are
  wanted. Three probe runs lost the same valve by rounding 0.052 to 0.05 before this was added.

## Bundle-structure rejection, Nov 10 (relief-valve-adequacy 20261110c)
"Bundle contains blocked internal terms: afterquery. Found at
authoring/evidence/preflight.py:138." The benchmark allows the programme's own name only as the task's own
`task.toml` name, `<prefix>/<task>`; every other occurrence is refused, and bundles must be self-contained and
provenance-free. My preflight had the prefix written down in the check that enforced it, so the tool that was
supposed to catch this was the only thing in the bundle that broke it. No other bundle in the repository has the
literal anywhere.

This also settles the advisory open since impeller-shrink-fits: `<prefix>/<task-name>` **is** the required form,
and the prefix we have been using is right. What was wrong was spelling it anywhere else.

**Rules taken from this**
- Never write the programme's name in a bundle file. Where a check needs it, derive it at run time from
  `task.toml`'s own name field and then confirm it appears on no other line.
- Check the name's *shape*, not its value: exactly one prefix segment, and a last segment equal to the task's own
  name.
- A checker that must name a forbidden string to look for it exempts itself explicitly, with a comment saying so.
  This happens twice now, for the decoder names and for the path prefixes; it is transparent, and it is not the
  obfuscation the security review refused.
- Verify the **zip**, not the working tree: unpack it into an empty directory and run preflight there. Two defects
  in two days existed only in the delivered artefact and not in the tree it was built from, a stale zip inside the
  bundle folder and a `__pycache__` holding a compiled copy of the sealed definition.

## Similarity rejection, Nov 10 (relief-valve-adequacy 20261110d)
"Task is too similar to an existing task." The subject was not the problem: no other bundle in the catalogue
touches pressure relief, and the solution code came out at 2 per cent overlap against its nearest neighbour. The
problem was the **verifier scaffolding**, which I had copied from impeller-shrink-fits and superheater-tube-life
and changed only where a filename forced me to.

The team's note on the check, the same day: it compares the verifier and solution code as well as the
instruction, **including against your own tasks still in validation or review**, so several tasks built from one
template block each other even when the science differs. `bore-form-acceptance` had gone in hours earlier, and my
verifier was 99 per cent of it.

Measured overlap, normalised for whitespace, against the nearest other bundle:

| file | before | after a rewrite |
|---|---|---|
| environment/Dockerfile | 1.000 | 0.345 |
| tests/test.sh | 0.996 | 0.378 |
| tests/Dockerfile | 0.994 | 0.360 |
| tests/test_<name>.py | 0.702 | 0.335 |
| tests/grade_<name>.py | 0.595 | 0.087 |
| instruction.md | 0.141 | 0.141 |
| solution/solve.py | 0.023 | 0.023 |

Whole submission, verifier and solution and instruction together: 0.081 against the nearest bundle afterwards.

**Rules taken from this**
- **The template is for the shape of a bundle, not its contents.** Copy the seven-entry layout, the evidence set
  and the rules. Write the grader, the pytest entry, the reward script and both images for the task in front of
  you. `tasks/impeller-shrink-fits` stays the worked example; it must stop being the source.
- Measure before submitting. Normalise whitespace and take difflib's ratio against every other bundle, per file
  and over the whole submission. Anything above about 0.4 on a verifier file is a rewrite, and an identical
  Dockerfile is an automatic one.
- What is dictated - the pins, the reward protocol, the closing paragraph of the instruction, the image's users
  and permissions - still has to be *expressed* freshly, and some of it can be moved out of the way: the pins now
  live in `tests/requirements.txt`, which took the verifier image from 0.65 to 0.36 on its own.
- Rewriting the reward script is a chance to test it. `verifier_checks.py` now runs `test.sh` for real with
  pytest stubbed and forces each combination of exit status and report counts, which the copied version never
  did: reward 1 only on a clean run with exactly one passing test, 0 for two tests, 0 for a failing run with a
  healthy-looking report, 0 for no report at all.
- The agent and verifier images are the easiest files in the repository to leave identical, and the ones nobody
  looks at twice. Every bundle's `environment/Dockerfile` should be assumed to collide until measured.
