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
