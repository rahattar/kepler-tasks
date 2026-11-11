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

## Round 3: the official screen solved 1 of 3 at low effort, 3 minutes

Three changes, in the order they were made.

**The tester has two states, not one.** Round 2's undocumented error motion took local low probes from 2-of-3 to
0-of-3, but one official attempt still separated it and passed: averaging nine records and keeping the orders that
stand clear of the scatter is a known trick, and a capable solver reaches for it. So the machine is no longer one
machine. The log has its spindle bearings re-greased and the preload reset on 2026-09-30, half way through the
campaign; six records are from before (14.0 um peak to valley, 4.0 at order 23 and 3.0 at 29) and three from
after (9.6 um, 2.8 and 2.0), with both orders moved most of a radian in phase. The separation has to be done
twice, once from six records and once from three. What makes this bite rather than merely add arithmetic is the
failure mode of the obvious route: pooled over the whole campaign the two states disagree in phase, nothing
survives a significance test, the tester looks clean, and the solver charges the whole error to the parts and
sentences the same 8 wrong as if it had never looked. A null result that reads as a clean bill of health is a
better trap than a wrong number, because there is nothing in it to check.

There is a second-order trap inside the first, and it caught this author's own independent solution. On the
three records of the later campaign a phase-agreement test alone also picks up a part order that happens to line
up, and subtracting it costs a feature. The fix is physical rather than statistical: the machine writes the same
*amplitude* as well as the same phase into every record it touches, and a part does not, so requiring both to
agree separates them cleanly (ratio 1.14 to 1.23 for the machine orders against 2.5 to 84 for every part order).

**Taylor's principle made to do real work.** The local-size half of the size rule was documented and inert: every
feature's worst local size sat 4 um or more inside its limit, so a solver that computed one size figure was never
caught. Two features now come off the boring bar oval, CB-26 by 9.5 um of amplitude and RJ-46 by 7.0, and each is
decided by a local size alone: a plug gauge goes through an oval bore on its minor axis, so CB-26's mating size
clears the lower limit by 16.7 um while a pair of opposite points across the major axis is 6.0 um over the upper,
and RJ-46 is inside the ring gauge by 5.4 um but 9.0 um under the lower limit across its minor axis. The gap
between the mating size and the two-point extreme turned out to be wider than the ovality alone (43.6 um on
RJ-46 against 4A = 28), because the circumscribed circle is set by the whole profile's peak while two-point sizes
cancel every odd order, so the original drawing windows already allowed it and no limit had to be tightened.

**A claim removed.** The difficulty text said a least-squares zone misses every feature by up to 5.0 um. It does
not, and it cannot: FM-7 drops orders 0 and 1, which puts the least-squares centre at the origin, so on these
profiles least squares agrees with the minimum zone to 0.00 um on roundness and 0.19 um on cylindricity. The
localized jaw marks added to make the two diverge do not help either, and the geometry says why: with a single
narrow feature the zone's high and low points move together under a translation of the centre, so the origin is
already the minimax centre. The marks were kept, because they widen the mating-size-against-mean-diameter gap
which is real, but the claim is gone and the route is out of the route study. The honest statement is in the
difficulty text now: the reference figure is the one piece of FM-7 a solver can get wrong here without being
caught, and that is a property of the assessment rather than of the parts.

Round 3 probes: three low-effort runs, 4 of 14 each, ten features wrong each. All three planned the booking
correctly, filtered correctly, applied Taylor and the 20 C reference correctly, and two of the three found the
re-grease line in the log and wrote it up as a caveat they chose not to act on. The gap is the instrument layer,
and it is wide rather than marginal.

One xhigh run, for the other end: 13 of 14. It booked the reference plan, separated both machine states, and got
both oval features right on a local size. It lost CB-25 on the form number alone, by 3.75 um, and its sentence
for CB-25 was right - which is the same failure the note records from rounds 1 and 2, the setup transfer
elaborated rather than taken straight. So the task now fails at xhigh too, by one feature and on the number
rather than the sentence, while both reference implementations pass. That is the shape to keep: the low-effort
failures are wide and in the layers, the xhigh failure is narrow and in the one step where being clever hurts.

## Round 4: validation failed on four criteria

Four blocking findings, and what each one actually taught.

**Every graded item has to require the work, not just the sheet.** A sheet naming 20.00 and accept for all 14
features earned credit on GB-32 and RJ-44, whose form errors were 0.26 um apart against a 1.2 um band. The gate
being all-or-nothing hid it: the sheet failed, so the study never asked how much it got for free. Two features
that a method-free answer can reach are two features that do not discriminate. Class re-assignment could not
fix it either - six features sat within 1.4 um of each other, so with four sentences some pair had to share one
- which meant the physics had to spread. The forms are now laid out so that within each sentence they are at
least 2.94 um apart, built from the knobs the design already had: the setup lobing scale, the taper of each
cylindricity feature, and the ovality of the two oval ones. The null study sweeps 4804 constant sheets through
the verifier and the best reaches one feature. One is the floor and cannot be removed - some constant always
names some feature's own answer - so the claim to make is that none reaches two, and preflight now fails if the
spacing is lost.

Two couplings showed up while laying the forms out, worth remembering. Within a setup the twin's floor is its
lobing-only form, so the twin with the higher floor must get the higher target; and the tuner's own form
function was measuring lobing alone while the truth included taper, so taper searches were silently no-ops.
The tuner now computes the form the truth computes.

**A conflicting identifier counts as a typo wherever it lives.** The sealed rig's docstring called the metrology
room's tester RT-1, the shop's machine. The agent cannot read that file; a reviewer can. Grep every identifier
across the whole bundle, authoring and sealed included.

**Evidence that grades itself is proxy evidence.** The studies compared numbers with their own arithmetic, so
the calibration rested on a stand-in for the verifier rather than the verifier. common.grade now writes a
complete sheet, to two decimals under the real header, and hands it to tests/grade_form.py - the module the
pytest test itself calls - so every study inherits the real CSV reader, the real comparison and the real gate.
truth() is memoised because it is pure, which is what makes a thousand-booking study affordable. A new study,
verifier_runs.py, runs the whole pytest verifier in a clean subprocess on 21 complete sheets and takes the
reward from pytest's exit status the way test.sh does. The second solution hands its sheet to the grader as a
subprocess too, so it no longer holds an opinion about what counts as right. The same finding caught stale
committed evidence: independent.txt and reference_run.txt still carried figures from two rounds earlier. Every
.txt is regenerated after any change to the data, and a stale number in a committed file reads as a false
claim.

**A premise the solver cannot infer is not specification until it is written down.** The whole booking rests on
two features bored in one setup carrying the same lobing, so that one feature's scan can serve its twin; without
it four scans cannot cover six deficient records and an expert can reasonably refuse the transfer. It was never
stated anywhere - it lived in the generator and in the author's head. The tell had already appeared in round
3's xhigh probe, which tested the premise by correlating same-setup profiles, found nothing (of course: each
part is clamped where it comes to rest, so the profiles are the same shape at unrelated angles), and wrote the
whole idea off as a distractor. It is now process note PE-114, which states the premise and is equally careful
about the three things that do not transfer: the angular position, the diameter, and the taper. Writing that
third one down exposed a real inconsistency - the re-honed bore's pre-hone taper had differed from its present
one, so the one booking that serves it from its twin was being punished for a fact no record carried. A hone
does not correct taper, so the pre-hone surface now carries today's taper, 4.5 um smaller in diameter.

Round 4 probes, on the rebuilt bundle: three low-effort runs, 7 of 14 each, all three rejected. All three
planned the booking correctly and used PE-114 to do it, which is what writing the premise down was for; all
three noticed RT-1's lapsed certificate and wrote it up as a caveat rather than acting on it, so all three lost
the same seven features to the instrument. One xhigh run solved it outright, 14 of 14 at 0.20 um worst - it
found both machine states from the phase step at the re-grease, checked them against the room tester's scans
(zero content at those orders) and against a single rotation matching CB-22's two records, and caught both oval
features on a local size. That is the shape to hold: the gap at low effort is seven features wide and sits in
one identifiable layer, and the task is demonstrably solvable rather than merely unsolved. Note the direction
of travel from round 3, where xhigh got 13 of 14: documenting PE-114 did make the task easier, as it had to,
and the easiness screen is where that shows up. If a later screen solves it at low effort, the lever to reach
for is the instrument layer, not the booking - the booking is now fair and should stay that way.

Advisory in the same review: task.name's prefix, and [metadata] carrying category, subcategory and the three
explanations. Acting on the second half was a mistake: the five fields were removed, intake's structure check
requires them, and the bundle bounced the same morning. They are back, word for word the README's sections, and
preflight now enforces the intake's block instead of its absence. The prefix is a question for Alex, not a
guess: it is the same for every task in the catalogue.

## Round 5: the reader was kinder than the instruction

One blocking finding: the instruction asks for an exact header and two decimal places, and the reader trimmed
the header's fields and took any number of decimals up to two. It also took a quoted header, blank lines above
it, exponent form, a plus sign and a trailing space on a sentence. The reader now enforces each stated clause
literally and leaves alone what the instruction leaves alone. verifier_checks proves it both ways: 16 sheets
carrying fully correct answers in a format the instruction does not allow, all refused; the correct sheet
varied six ways the instruction does not constrain, all accepted. No physics, data or answer changed.

## Layers
- **Undocumented, from the records together:** the tester's error motion, in two states either side of a service
  date, each estimated from its own records.
- **Undocumented, from one record alone:** the 12-point records alias order 12 onto the mean radius, so RJ-45's
  own record gives a mean diameter 6.6 um out; its size has to come from the scan it must have anyway.
- **Data-only:** the 12-point records cannot resolve the band (five features); the re-honed bore's record predates
  the hone; which features shared a boring setup (the log records it, the inference is the solver's); the feed
  waviness above the band, which swamps a profile assessed unfiltered.
- **Documented but against the natural choice:** the mating cylinder against the mean diameter; the two-point
  local size, which alone decides the two oval features; cylindricity counting taper where roundness does not;
  the 20 C reference. Not the reference figure: least squares and the minimum zone agree here.
- **Allocation:** six needs in four setups for a booking of four. Of the 1001 bookings, 8 pass; the best of the
  rest gets 13 of 14; one scan per sparse feature needs five.

## Calibration
Reference worst 0.20 um; independent solution 0.90 um; 192 sound runs all pass, worst 0.20 um, and no single
feature is given more than 0.20 um by any of them. 16 defective routes, every feature sentenced wrong by at
least 4 of them, the nearest wrong route 2.88 um against the 1.2 um band. Best constant sheet 1 of 14 and none
reaches two; transcribing the inspection report 0 of 14. 21 complete sheets through the whole pytest verifier,
every one decided as it should be. preflight 179 checks.

**A note on the band.** The 4-parameter minimum-zone cylindricity fit is numerically delicate: a Nelder-Mead
search on the non-smooth maximum stalls 1.2 to 2.0 um high on the four cylindricity features, which would fail the
band. The linear-programming form (and SLSQP on the constrained form) converge properly. This is solver skill
rather than engineering insight, so if a later round shows probes losing features to it rather than to the
layers, widen the band: the nearest wrong route is at 2.85, so there is a little room but not much. The
independent solution now sits at 0.99 um, nearly all of it the setup transfer on the one booking that serves the
re-honed bore from its twin rather than scanning it, so the band cannot be narrowed either.
