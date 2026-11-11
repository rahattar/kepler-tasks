# Design note: bore-form-acceptance (Nov 10 2026)

**Status:** built and preflight-clean (110 checks). Local probes: low effort 0 of 3, xhigh 2 of 3. Zip
bore-form-acceptance-20261110c.zip sent to Alex, carrying Alex's own instruction.md (the two
earlier zips of the day held my draft). The instruction is a draft
awaiting Alex's approval, including its relevant_experience line.

**Task:** `/app/output/form.csv` with `feature,form_um,verdict` for each of 14 finish-machined features of a press
overhaul (six cylinder bores, two gland bores, six ram journals, 180 to 400 mm). A feature is right when the form
error is within 1.2 um of the minimum-zone value of its true surface and the sentence (`accept`, `reject_size`,
`reject_form`, `reject_both`) matches exactly. The gate is all 14. The records are raw profiles: absolute radius at
three sections, 1800 points a revolution from the shop's form tester or 12 touch points from its coordinate
machine. A metrology room scans a feature densely on request, booking of 4.

**Why this subject.** It was chosen against the five levers the Nov 2026 calibration note lists as untried, after
skid-noise-guarantee and recip-cylinder-limits both went 3 of 3 at low effort. The sealed truths are 4 accept,
3 reject_size, 3 reject_form, 4 reject_both, so no constant sentence scores.

## What the first design got wrong
Round 1 went 2 of 3 at low effort (14/14, 14/14, 13/14), median 3.5 minutes. Every layer was found by every probe:
the Nyquist argument against the 12-point records, the re-honed bore's stale record, the single-clamping transfer
between setup mates, minimum zone against least squares, Taylor mating sizes against mean diameters, the 20 C
correction. The reason is structural and worth keeping in mind for the next task:

- **A documented method is an implementation, not a difficulty.** FM-7 has to state the reference figure, the
  filter band and the envelope rule for the task to be fair. Once it does, "the natural estimator is biased" costs
  a probe nothing: it reads the standard and implements it.
- **Unidentifiability that one line of reasoning settles is not a squeeze.** "12 points cannot resolve 50 UPR" is
  Nyquist, stated in one sentence, and every probe reached it.
- **A self-check I did not mean to ship.** Four boring setups held two *dense* features each, so two probes
  validated the setup transfer against known pairs before trusting it. The lever asks for an answer that cannot be
  confirmed from the inputs; I had handed them a confirmation.
- The only round-1 failure was self-inflicted: a probe invented an amplitude scaling for the transfer and put one
  feature 1.51 um out. The naive transfer would have been right.

## What fixed it
One layer, in no document: **the shop's form tester has its own error motion**, 4.62 um at 23 undulations a
revolution and 3.87 um at 29, and it rides on all nine of its records at the same phase, because a record's angle
is the spindle's angle while a part is clamped wherever it comes to rest. The metrology room's tester is certified
and carries none, so a scan is clean.

- **It is derivable, and only from the records together.** Averaging the tester's nine records leaves the machine
  and averages the parts down; the orders to keep are those whose mean stands clear of the scatter between parts.
  The independent solution finds the same two orders by a different test: the mean resultant length of the phases
  across records is 1.00 at orders 23 and 29 and at most 0.53 at every other order.
- **Nothing in the records contradicts getting it wrong.** The inspection report's own least-squares figures are
  computed from the same records, so they carry the same error: a solver that checks its answer against the report
  finds agreement. That is the no-self-check lever, and it is what the two failing probes walked into.
- **The parts carry nothing at those orders.** Their own content was moved below 20 UPR for this, so the
  separation is clean and the correct route is not noise-limited.
- Fairness: the instrument notes record that the tester's error motion was last certified in 2019 and the
  certificate has not been renewed. That records the fact without naming the error or its size, which is the line
  the note draws.

## Round 2, low effort (0 of 3)
| probe | right of 14 | what happened |
|---|---|---|
| P4 | 13 | Found the error motion, named both orders and amplitudes. Then scanned both members of one pair, so two features had to be estimated; one came out 1.83 um wrong. |
| P5 | 6 | Charged the error motion to the parts. Reported "no feature is acceptable as it stands" where four accept, and predicted 12 of 14. Noted that its filter "reproduces the inspection report's LS roundness exactly" as a check. |
| P6 | 4 | Same, and also concluded "no feature passes". Predicted 12 of 14. Ran its optimisations from multiple random starts, which agreed to 0.2 um, and so had no reason to doubt the answer. |

Both failures were confident and self-consistent, which is the behaviour the lever was aimed at.

## Round 2, xhigh (2 of 3)
| probe | right of 14 | tool calls | minutes | what happened |
|---|---|---|---|---|
| P7 | 14 | 26 | 15 | Found the error motion and confirmed its removal four ways, including that the room's scans carry no 23/29 content of their own while the part's genuine lobing survives, rotated by a consistent re-clamping angle. |
| P8 | 14 | 34 | 15 | Same, with the phase-lock ratio measured at 1.000 against 0.82 or less for every genuine part order. Built a de-aliasing estimator for the transfer and rejected it after validation showed it worse on three known pairs. |
| P9 | 12 | 44 | 30 | Found everything, then fitted harmonic amplitudes to the alias bins of the two transferred features and marginalised over unknown phases, instead of taking the scanned partner's measured form. Both landed about 2 um out. It predicted this itself, to the feature. |

Against low effort's 12 to 13 tool calls and 3.5 minutes, so the effort gap is real and it buys the right things.

**The one repeated failure mode is worth remembering.** The only miss in round 1 (a low probe) and the only miss
in the xhigh round both came from *elaborating* the setup transfer rather than taking it straight: one invented an
amplitude scaling, the other a phase-marginalised alias fit. The simple transfer is the correct one, and it is
correct because the lobing is the setup's. A task whose hardest step is also its simplest step is a good property,
but it means the form column, not the sentence, is what catches a clever solver: P9 had all 14 sentences right.

## Layers
- **Undocumented, from the records together:** the tester's error motion.
- **Data-only:** the 12-point records cannot resolve the band (five features); the re-honed bore's record predates
  the hone; which features shared a boring setup (the log records it, the inference is the solver's); the feed
  waviness above the band, which swamps a profile assessed unfiltered.
- **Documented but against the natural choice:** minimum zone against least squares; the mating cylinder against
  the mean diameter; cylindricity counting taper where roundness does not; the 20 C reference; the local-size
  check of Taylor's principle.
- **Allocation:** six needs in four setups for a booking of four. Of the 1001 bookings, 8 pass; the best of the
  rest gets 13 of 14; one scan per sparse feature needs five.

## Calibration
Reference worst 0.16 um; independent solution 0.63 um; 192 sound runs all pass, worst 0.16 um. 15 defective
routes, every feature sentenced wrong by at least 4 of them, the nearest wrong route 3.36 um against the 1.2 um
band. Best null baseline 1 of 14.

**A note on the band.** The 4-parameter minimum-zone cylindricity fit is numerically delicate: a Nelder-Mead
search on the non-smooth maximum stalls 1.2 to 2.0 um high on the four cylindricity features, which would fail the
band. The linear-programming form (and SLSQP on the constrained form) converge properly. This is solver skill
rather than engineering insight, so if a later round shows probes losing features to it rather than to the
layers, widen the band to 2.5 um: the nearest wrong route is at 3.36, so there is room.
