# What survived the low-effort screen, and what did not (Nov 11, evening)

Written to answer one question for a redesign: which traps on record stopped a low-effort run, how each worked,
and which of them still work against today's gate. It covers bore-form-acceptance in full, then every other task
with official low-effort evidence, then everything that failed, then advice.

It replaces the short answer given in chat at 17:21, which was written against a checkout nine hours old and
missed the model-matched probe results. Corrections to that answer are listed at the end.

## 0. Bottom line

1. **bore-form-acceptance has exactly one layer that ever stopped a low-effort run:** the shop form tester's own
   error motion, in two states either side of a service date. Every other layer was found by every probe at every
   effort.
2. **Whether that layer survives the gate is not established.**
   - It stopped every low-effort probe on the session's earlier model: 0 of 6 solved in its two-state form.
   - It stopped both low-effort probes run on the round-6 variant with the model forced back through the Agent
     tool's `model` argument (0 of 2 solved).
   - It did not stop Fable 5.2 at low effort: 2 of 2 solved on 20261111d in about 5 minutes, 3 of 3 on round 6.
   - It has never met the official screen in its two-state form. Its one-state form met it once and was solved
     1 of 3, in 3 minutes.
3. **The gate today:** claude-opus-5-5 at low effort, 3 trials, 0 solves allowed. Two rejections on Nov 11 say
   so: flare-load-study 20261111e (3 of 3) and base-pressure-diagnosis (1 of 3).
4. **What has officially beaten the low-effort screen 0 of 3** is hvac-submittal-review (Oct 15, the same model),
   and it did so by a different mechanism: a verification budget with no slack on a building where every room had
   drifted. vav-airflow-calibration went 1 of 3 by the same mechanism.
5. **The strongest single effect on record** is in turbine-tool-repair: a fault that exists only in hidden inputs
   took the official xhigh run from 8 of 8 to 0 of 8.
6. **My own checks of bore-form found four things its notes do not say** (section 2.6): the pooled diagnostic is
   clean only under one particular test; every passing booking hands the solver a witness; the README on main
   makes a false claim about least squares; and the drawing file rounds eight form tolerances that the sealed
   definition holds to the half micrometre.

## 1. Evidence, and how far it goes

| Kind | What | Where |
|---|---|---|
| Computed by me today | bore-form's instrument layer, from the shipped records of main at d578a4b | section 2; scripts in `tools/trap-analysis/` |
| Official trial records I read | vav-airflow-calibration: the three easiness analyses in full, the difficulty run's summary and several of its eight analyses; impeller-shrink-fits difficulty (8 trials) | project docs `vav-official-run-oct19*`; Alex's attachment of Nov 9 |
| Official results captured in notes | hvac, chill-bench, superheater, pump-wear, turbine-tool-repair, weld-preheat, furnace, cz, impeller, cooler-fouling, flare, base-pressure | project and repo design notes |
| Reported by the building session | every bore-form, flare and base-pressure local probe | `design-note-bore-form.md`, `difficulty-calibration.md`, branch notes |

- I ran no probes for this and saw no bore-form trajectory. Where the list of questions asks what separated
  trajectories, the answer for bore-form is the building session's report.
- Probe models are not named in the notes. From commit trailers, the bore-form session was on Opus 5 on Nov 10
  and on Fable 5.2 from Nov 11 08:58; the flare session was on Opus 5 until about 14:00. So "the session's earlier
  model" is Opus 5 and "the current, stronger model" is Fable 5.2. That is inference.
- `model: "opus"` on a probe is taken to be the screen's model because the flare session's opus-forced probes
  reproduced the official screen (2 of 2 solved in about three minutes, against 1 of 3 on Opus 5). Also inference.
- The bore-form note says its round-6 control probes were "forced with the Agent tool's `model` argument" to the
  earlier model. That argument offers a model family, not a version, so those probes most likely ran on the same
  "opus" as the flare session's. If so they ran on the screen's model. The bore-form session should confirm.

## 2. bore-form-acceptance: the layer that held

Task in one line: a form error and one of four sentences for each of 14 bores and journals, all 14 right, the
form error within 1.2 um of the minimum-zone value of the true surface.

### 2.1 What a first pass sees

- `measurement_index.csv`: nine features measured on "form tester RT-1" at 1800 points a revolution between
  2026-09-29 and 2026-10-01, five on the coordinate machine at 12 points. Each has a file under `measurements/`
  with columns `section_mm,angle_deg,radius_mm`.
- `docs/standard_fm7.md`: the whole assessment. Mean radius out, orders 0 and 1 dropped, order n weighted by
  `exp(-pi (0.4697 n / 50)^2)`, then a minimum-zone form error.
- A careful first pass applies FM-7 to each RT-1 record as it stands. Result, against the sealed truth (computed):

| feature | tolerance | truth | as measured | error |
|---|---|---|---|---|
| CB-21 | 28 | 23.99 | 34.31 | +10.32, verdict flips |
| CB-23 | 15 | 18.50 | 30.60 | +12.09 |
| CB-26 | 33 | 29.50 | 33.12 | +3.61, flips |
| GB-31 | 17 | 20.51 | 24.48 | +3.97 |
| GB-32 | 24 | 20.76 | 21.85 | +1.08, inside the band by 0.12 |
| RJ-41 | 30 | 26.57 | 37.38 | +10.81, flips |
| RJ-44 | 18 | 13.99 | 23.07 | +9.08, flips |
| RJ-46 | 26 | 23.11 | 28.63 | +5.52, flips |

  Seven features lost (CB-22's record is stale for another reason and is scanned). That is the "7 of 14" every
  low-effort run scored in round 4: the five 12-point features and CB-22 come right through the scans, GB-32
  survives by 0.12 um, and the other seven RT-1 features are wrong.

### 2.2 Why that pass looks complete

- **The plant's own report agrees with it.** `docs/inspection_report.md` lists a roundness per feature computed
  by the tester's software from the same records. Filtering to FM-7 and taking the least-squares zone reproduces
  all nine report figures to 0.1 um (34.3, 32.4, 32.0, 30.6, 29.7, 22.8, 37.8, 23.4, 31.1; computed). One probe
  cited this as its validation.
- **The numbers are stable.** One probe ran its minimum-zone search from many random starts and they agreed to
  0.2 um.
- **The sheet is plausible.** The truth already has eleven rejects in fourteen, so more rejects do not look
  wrong.
- **The one cue reads as boilerplate.** `docs/instrument_notes.md`: "Its spindle error motion was last certified
  in 2019 and the certificate has not been renewed." All three low-effort runs in round 4 reported this as a
  caveat and did not test it. In round 3, two of three treated the service line in the log the same way.
- **A pooled test can come back clean,** but only under one choice of test. See 2.6.

### 2.3 What the right answer depends on, and where the evidence sits

1. **The angle convention.** `instrument_notes.md`: "A record's angle is the spindle's angle, from the spindle
   encoder's zero; a part is clamped wherever it comes to rest." The nine parts come from five setups on three
   machines (`machining_log.csv`, column `features_in_this_setup`). So anything at the same spindle angle in all
   of them belongs to the instrument.
2. **The service date.** `machining_log.csv`, row 2026-09-30, machine "RT-1 form tester", operation "spindle
   bearings re-greased, preload reset", note "carried out in the evening after the day's inspection work". With
   `measured_on` in the index this splits the records exactly: six before (CB-21, RJ-41, CB-22, CB-23, RJ-44,
   RJ-46), three after (CB-26, GB-31, GB-32).
3. **The step.** Per state, average the filtered profiles in the spindle frame and keep the orders that stand
   clear of the scatter between parts. Computed from the shipped records:

| | records | order 23 | order 29 | phase lock (23, 29) | amplitude max/min | peak to valley |
|---|---|---|---|---|---|---|
| before | 6 | 4.02 um | 3.02 um | 1.00, 1.00 | 1.20, 1.23 | 14.0 um |
| after | 3 | 2.80 um | 2.00 um | 1.00, 0.99 | 1.14, 1.22 | 9.6 um |

   Phase moved 1.50 rad at order 23 and 1.76 rad at order 29 across the service. The largest phase lock at any
   other order before the service is 0.84.
4. **The result.** With each record's own state removed, every RT-1 feature except the stale CB-22 lands within
   0.20 um of the truth (computed; the reference reports the same).
5. **Second-order catch.** On the three records after the service, phase agreement alone also passes orders 7, 8,
   24, 41, 48 and 49 (lock above 0.9; computed). Their amplitudes are near zero, so here it costs nothing, but the
   building session's independent solution lost a feature this way in an earlier round and now requires the
   amplitudes to agree too.

### 2.4 Why low effort skipped the step and high effort sometimes made it (reported, not seen)

- **Size of run.** Low: 12 to 13 tool calls, about 3.5 minutes. xhigh: 26 to 44 calls, 15 to 30 minutes.
- **Low effort** treated the certificate line as something to report. Its check was the inspection report, which
  is circular.
- **xhigh** treated it as a hypothesis and tested it in the spindle frame: phase lock across records (1.000
  against 0.82 or less), the phase step at the service, the certified scans (nothing at 23 or 29), and CB-22's
  two records matching by one rotation.
- **The separating behaviour** is an unprompted comparison of one instrument against an independent one.
- **Model matters more than effort here.** Fable 5.2 at low effort found the error from phase agreement across
  records and split it at the service date, in under five minutes. On round 6 its xhigh runs took 40 minutes and
  followed the same route as its low runs: effort bought nothing.

### 2.5 What keeps it fair

- Stated facts, none naming the error: the angle convention; the lapsed 2019 certificate; the service, timed to
  the evening so the split is exact; "RT-3 ... is inside its certification" (`docs/metrology_room.md`).
- The parts carry almost nothing at 23 and 29 (own content 0.44 to 0.61 um at those orders), so the separation is
  not noise-limited.
- Only an instrument can be phase-locked to the spindle across five setups on three machines.
- 192 sound method variants pass, worst 0.20 um. A second solution written separately passes at 0.90 um.
- Preflight fails if any document gives the error motion away.
- No review flagged this layer. The quality reviews flagged the setup-transfer premise (now PE-114), a typo, proxy
  evidence and the reader. Reported from `rejection-patterns.md`.
- Weak points: three records carry the second state, and 0.90 um against a 1.2 um band is modest margin.

### 2.6 What my checks add

Scripts: `tools/trap-analysis/check.py` and `check2.py`. They read `environment/data`; `check2.py` also imports
the sealed module for its fits and the truth, which a reviewer may do and an agent cannot.

1. **The pooled diagnostic is clean only under the reference's test.** The reference keeps an order when the real
   and the imaginary part of its mean each stand three standard errors clear. Pooled over nine records nothing
   passes, as the notes say. Under a test on the modulus of the mean, pooled orders 23 and 29 pass (z 3.6 and
   3.0), and they are the two top-ranked orders in the pooled data by a distance (phase lock 0.77 and 0.68,
   next 0.63).
   - A solver using that test sees the two lines at once.
   - It is still wrong if it stops there: with the pooled estimate removed, every RT-1 feature but RJ-46 is
     outside the band, and three are worse than untreated (CB-26 +8.52, GB-31 +7.75, GB-32 +3.27).
   - So "the first diagnostic returns a clean bill" is true of one test and false of another. Fable 5.2's
     low-effort runs found the error "from phase agreement across records", which fits.
2. **Every passing booking hands the solver a witness.** All 8 passing bookings scan CB-22 or RJ-44. Both also
   have an RT-1 record. Comparing amplitude spectra, which needs no knowledge of the clamping angle:
   - RJ-44: record 4.18 um at order 23 and 3.86 at 29; certified scan 0.46 and 0.00. No other order differs by
     more than 0.5 um.
   - CB-22: record 4.62 and 4.25; scan 0.00 and 0.48. The only other differences are orders 4, 6 and 10, the
     score the hone removed.
   - This witness covers the "before" state only. Nothing re-measures CB-26, GB-31 or GB-32.
   - The chat answer said no clean re-measurement existed. That was wrong.
   - Round 6 closes it for CB-22 on purpose, by giving the honed bore a new signature.
3. **README.md and task.toml on main make a false claim.** They say a least-squares zone "agrees with the minimum
   zone to within 0.2 um" on these profiles. On the sealed true surfaces the two differ by 0.24 to 3.86 um on the
   ten roundness features, and seven differ by more than the 1.2 um band (CB-23 1.82, GB-31 3.37, GB-32 3.72,
   RJ-42 1.23, RJ-43 1.30, RJ-44 3.86, RJ-46 2.10).
   - The round-6 commit message already knows: a shared variable name "had silently switched the least-squares
     route off. It loses 8 features, not none."
   - Main was not corrected. 20261111d carries the claim in `difficulty_explanation`, and `route_study.txt` has no
     least-squares route.
   - Three bundles have been rejected this month for prose that contradicts the evidence (impeller-shrink-fits
     20261109b, bore-form 20261110d, flare-load-study 20261111d). Fix this before any resubmission of 20261111d.
4. **One RT-1 feature does not test the layer.** GB-32 passes untreated, by 0.12 um.
5. **The drawing and the sealed definition disagree on eight form tolerances.** `gen.py` writes the tolerance with
   `%.0f`, and eight sealed tolerances end in a half micrometre.

   | feature | drawing file | sealed |
   |---|---|---|
   | CB-21 | 28 | 27.5 |
   | CB-24, CB-25 | 12 | 11.5 |
   | RJ-42, RJ-43 | 22 | 22.5 |
   | RJ-44 | 18 | 17.5 |
   | RJ-45 | 18 | 18.5 |
   | RJ-46 | 26 | 26.5 |

   - No verdict changes today: every true form error is at least 2.9 um from its tolerance on either figure.
   - It is still a sentence decided against a number the solver was not given, and a reviewer comparing the
     drawing with the sealed file will see it. Print the tolerance as held, or hold integers.

### 2.7 Everything else in bore-form was found

| layer | where | why it was found |
|---|---|---|
| 12-point records cannot resolve 50 undulations (5 features) | `points_per_rev` | one line of Nyquist |
| CB-22 re-honed after measurement | log row 2026-10-03, which says so | stated |
| setup transfer between twins | `features_in_this_setup`, PE-114 | first self-validating on four dense pairs, then stated |
| minimum zone against least squares | FM-7 section 3 | documented, so implemented |
| mating size against mean diameter; two-point size on the oval CB-26 and RJ-46 | FM-7 section 4 | documented |
| 20 C reference | `room_c`, FM-7 section 2 | documented |
| Gaussian band | FM-7 section 1 | documented |
| cylindricity against roundness | `form_characteristic` | one column |
| the booking, 8 of 1001 pass | | once PE-114 existed every run planned it right |
| one-state tester error | | pooled average is a known trick: found by 1 of 3 local runs, solved by 1 of 3 official |
| round 6: second machine line under the setups' own lobing | | Fable 5.2 solved it from the twins, 3 of 3 |

The one thing that has cost xhigh a feature is accidental: elaborating the setup transfer (an amplitude scaling,
a phase-marginalised alias fit) where taking it straight is right. It cost one feature in three separate rounds.

### 2.8 Count and coupling

- **One** trap stops low effort. It has two parts in sequence: seeing that the tester has an error at all, then
  splitting it at the service. The split matters only after the first part.
- It is independent of the booking, except that the booking's scans supply the witness in 2.6.
- All 7 lost features come from it. One discovery passes the task.

### 2.9 Solve rates

All local unless marked. Counts are features right of 14 per run.

| bundle | probe model | low effort | xhigh |
|---|---|---|---|
| round 1, every layer documented | earlier (Opus 5) | 2 of 3 (14, 14, 13), 3.5 min | - |
| round 2, one-state tester error | earlier (Opus 5) | 0 of 3 (13, 6, 4) | 2 of 3 (14, 14, 12) |
| round 2 | **official, opus-5-5** | **1 of 3, 3 min** | not reached |
| round 3, two states and the oval features | earlier (Opus 5) | 0 of 3 (4, 4, 4) | 0 of 1 (13) |
| round 4 = records of 20261111c and d | earlier (Opus 5) | 0 of 3 (7, 7, 7) | 1 of 1 (14) |
| 20261111d | Fable 5.2 | 2 of 2 solved, about 5 min | - |
| round 6 (branch) | Fable 5.2 | 3 of 3 solved, 3 to 8 min | 3 of 3, about 40 min |
| round 6 (branch) | forced back, most likely "opus" | 0 of 2 (7, 7) | - |

No bundle has reached the official difficulty stage.

**The missing cell is the one that matters:** 20261111d at low effort on the screen's model. Round 6 was stopped
on the Fable 5.2 result. The screen is not Fable 5.2, and the round-6 control on the other model went 0 of 2.

## 3. The same questions for every task with official low-effort evidence

### 3.1 hvac-submittal-review: official easiness 0 of 3 (Oct 15)

Opus 5.5, low effort, 140 to 158 s per trial. Difficulty passed (count not captured). Later rejected in human
review for an instruction that printed the tolerances, which has nothing to do with the trap.

1. **First glance.** Seven rooftop units, 33 rooms, a contractor's submittal that passes the owner's standard on
   the 2004 record drawings. Facilities records (work orders, an asset inventory, minutes) suggest the building
   changed. A field-verification service returns as-built inputs for 8 items.
2. **Why it looks complete.** The method is hard and they got it right: ASHRAE 62.1 Appendix A outdoor air,
   mixed-air entering wet bulb, catalogue capacities with their corrections. Official trials had capacities
   within 0.2 per cent and all seven verdicts right. Every check on the method passes.
3. **What the answer depends on.** Every refurnished room drifted, by rules that depend on room class (14 m2
   offices, 16 m2 offices, conference rooms, open offices, the workroom, two labs). The classes exist only as
   furniture work orders and a line in the minutes that layouts "followed the planner's room-size standards". A
   pass needs one verification in each class the records cannot settle, and none spent elsewhere. The reference
   used seven of the eight.
4. **Low against high.** All three official low-effort trials spent verifications on salient items before sorting
   rooms into classes: the server room (which the records already settle), the roofs, and duplicates of one class
   (110 and 210, 116 and 144, 223 and 233). No 14 m2 or 16 m2 office was verified, and unverified rooms were left
   at record values. RTU-3 came out 25 per cent off, RTU-7 13 per cent. Local runs that passed verified each
   class once.
5. **Fairness.** The standard states the as-built rule and the limited verification capacity. Two notes from the
   run audit: do not hardcode class thresholds in the reference, and word the rule so unverified rooms need a best
   estimate, not the record value. One weakness at the time: skipping either of two classes still passed, and a
   later passing trial left one unverified and aimed inside the printed tolerance. In the Nov 6 revision a
   complete campaign passes on nine drift seeds at 0.37 of a tolerance or less, and skipping any class fails by
   1.6 to 6.3 times the tolerance.
6. **What failed first on the same subject.** Nine probe runs on three earlier packagings, all solved:
   - facts in cell comments, strikethrough, addenda and footers: 3 of 3 in 2 minutes;
   - an as-built behind a budget, magnitudes in the records: 3 of 3;
   - a renumbering memo as a third layer: 3 of 3.

   What changed the result was drift in every room, structure that must be sampled, and no slack.

### 3.2 vav-airflow-calibration: official easiness 1 of 3, difficulty 7 of 8 (Oct 19)

Opus 5.5. Low-effort trials ran 110 to 141 s. I read the three easiness analyses in full, and the difficulty
run's summary and several of its trial analyses.

1. **First glance.** 40 VAV boxes, K and offset for each. Records: a box schedule, an inlet survey, a 2024
   balancing report, two weeks of trends, a renovation close-out. Five capture-hood visits.
2. **Why it looks complete.** All three low-effort trials got the hard-looking parts right: zero offsets from
   night trends, including a failed auto-zero on one box; the 2024 ratios kept for the unchanged west wing only;
   tight fits on the boxes they visited.
3. **What the answer depends on.** Five classes the records cannot settle, for five visits: three laboratory
   boxes that never close (zeros 0.040, 0.008 and 0.038 in. w.c., so no sibling predicts another), one
   vertical-drop elbow class, one sagging-connector class. Evidence: the firmware column, `renovation_2025.md`,
   and the survey's orientation and flex-length columns.
4. **What the failures did.**
   - Trial AVJV4am visited two sagging connectors (31 and 35) and left the vertical drops at factory K: five
     boxes at +18.1 to +20.5 per cent against 10. Its own final message named them as likely to fail.
   - Trial iSp5ZKh visited three crushed connectors (38, 30, 34), a class one visit covers: eight boxes at +15.9
     to +22.2 per cent.
   - The one xhigh failure gave lab 37 the mean of the other two lab zeros: +29.9 per cent.
   - The analyser's words: "confirm an already-measured class instead of covering an unmeasured one", and of the
     other trial, "The agent did not first sort the floor into inlet classes, decide which classes the records
     already settle, and then target the unsettled ones."
5. **Fairness.** Every analyser check passed on all eleven trials. The specification check cites that each class
   is derivable from named documents, and that the 6 of 4368 campaigns that pass follow from asking what the
   records leave open.
   Sound methods land at 4.0 to 6.1 per cent; the nearest incomplete plan misses at 13.6.
6. **What failed first.** The first prototype leaked the truth through a trend column. The second was solved 3
   of 3 in about five minutes each, because every fallback for an uncovered class still landed inside 10 per
   cent. A note saying "some" long connectors sag made hedging defensible and had to be made determinate.

### 3.3 turbine-tool-repair: official xhigh 8 of 8, then 0 of 8 and accepted (Oct 25-26)

The deliverable is a repaired reduction program, graded on eight hidden record sets.

1. **First glance.** The plant's program, the procedure it should follow, two example record sets, one with a
   contractor's report.
2. **Why it looks complete.** Nineteen of the twenty defects are departures of the code from the procedure, and
   xhigh runs fixed all nineteen and built fault-injection tests for each documented variant. Both examples then
   reduce cleanly.
3. **What the answer depends on.** Hidden set h7 has one inlet RTD frozen at an overnight 22.41 C on a day warming
   from 29 to 35 C. The acquisition system does not flag it. Keeping it puts output 0.62 per cent out against a
   0.3 per cent band. The note lists the fault for h7 only.
4. **Low against high.** No gradient: every official trial fixed 19 of 20 and failed h7. "Their self-made stress
   tests only inject faults they have already imagined." One local pass came from a blanket rule that drops any
   RTD more than 5 K from the others.
5. **Fairness.** The record format says -999 marks only failures the acquisition system detects. The run audit
   passed specification on all eight trials and called flat-line screening routine test-code data validation.
6. **What failed first.** Revision a failed quality review as a compliance audit: every defect was a mismatch
   with explicit text. Revision b, with the procedure rewritten in engineering terms and 16 defects, went 8 of 8
   officially in 5 to 20 minutes.

### 3.4 chill-bench-commissioning, sixteen stations: official 1 of 3 and 1 of 8, approved (Oct 2)

- **Trap.** Eight bench runs for sixteen stations. Seven stations are vertices of the fleet's convex hull in
  (roughness, bath temperature). A campaign that leaves one unmeasured extrapolates there. Only 9 of 12,870
  campaigns leave nothing outside.
- **Why the first pass looks complete.** Every agent that built a sound model found the physics, including the
  degeneracy and the hinge in the bath effect. The model was never the problem.
- **What failed them.** Where the runs went. Every failure skipped the low-roughness plateau corner and lost the
  same two stations.
- **No effort gradient:** 1 of 3 low, 1 of 8 xhigh.
- **What failed first.** Twelve stations and a 20 per cent allowance: official 3 of 3, because any model of
  roughly the right shape passed.

### 3.5 Records-only tasks that passed every stage

| task | official | what the notes credit |
|---|---|---|
| superheater-tube-life (Oct 25) | all green, difficulty 7 of 8; local low 1 of 3 | faults the data show and no document names: two thermocouple offsets visible only as a ratio step against a neighbour, a silent drift, swapped tags, a tube thinner than the register |
| pump-wear-assessment c (Oct 24) | difficulty 7 of 8 (revision b: 8 of 8) | the failed trial trusted the installation sheet's tapping height for P5 (0.80 m, true 1.55 m), never looked at P5's stopped-hour readings, and leaned on a nearly degenerate free offset in its fit |
| weld-preheat-temperature (Nov 9) | all green; local low 0 of 3, xhigh 1 of 3 | records that disagree where other records settle it: the oven log issued a different electrode batch than the joint sheet; the joint sheet's heat number against the certificate's plate list |

Easiness counts for these were not captured. All were screened before Nov 11.

### 3.6 base-pressure-diagnosis (other account; reported)

- **Official.** The fourth submission reached the difficulty stage and failed it 8 of 8 (Nov 10). The rebuilt
  bundle failed easiness 1 of 3 in 6 minutes median (Nov 11), with 0 allowed.
- **What caught probes:**
  - VC01: a gauge certificate that is wrong. It caught 3 of 11 low-effort probes. Shown a throughput test
    reporting 1038 L/s against a rated 915, they blamed the register's port figure. Fit residuals stayed under 1
    per cent throughout.
  - VC07: a register naming the wrong pump, next to crossed gauge serials. The slip was over-correction: throwing
    away a real 1.42 certificate factor along with the clerical error.
  - VC04: a replacement gauge reading a quarter high. With the words "fresh certificate" and "would not strike"
    in the log every probe failed it (xhigh 1 of 6). With neutral wording nearly every probe passed it (low 2 of
    3, xhigh 3 of 3). "VC04 is a switch on wording."
- **What every probe found:** every layer that moves a fit residual (all fifteen layers, by 6 of 6 probes in
  round 1); the one chamber needing the test (15 of 15 ordered it); a fleet-wide calibrated-leak fault that
  shows as a 0.88 ratio on every chamber (6 of 6).

### 3.7 relief-valve-adequacy and flare-load-study (other account; reported)

- The one step that separated runs for four rounds was a carried fact: a feed meter's stale configured density
  also feeds one control valve's trend. Two runs in three missed it on Opus 5. In round 4 both failing runs
  claimed a cross-check they had not run.
- The official screen (opus-5-5, low) made the step in all three trials, in 2m39 to 3m06. Matched local probes
  agreed. The lever does not exist at the gate.
- Two-state traps where a log line names the item it voids (a valve retrim, a steam-trap renewal): every run cut
  both records at the right day.

## 4. Everything that failed, and what made it visible

| lever | evidence | why it was found |
|---|---|---|
| a fact stated anywhere: note, column, log line, cell comment, strikethrough, addendum, footer | impeller-shrink-fits official 8 of 8 in 14 to 28 min; hvac ideas 1 to 3, nine of nine | agents read every file in full and reconcile every record |
| a documented method, however far from the natural choice | bore-form round 1; recip-cylinder-limits, 16 layers, 3 of 3; turbine revision b | a stated method is something to implement |
| more layers, records or units | flare +4 layers, still 3 of 3; pump-wear b, 8 of 8 | adds reading, not difficulty |
| a dated change that voids a record, named in a log | flare, every run cut correctly; wafer-chill-recipe, 3 of 3 discarded the campaign before a recondition; bore-form's re-hone | a log line is a signpost |
| a fault that shows as a step, a ratio or a balance | cooling-tower v2; base-pressure leak fault (0.88 on every chamber); vav's failed auto-zero | low effort runs peer ratios, step searches and balances unprompted |
| a fault that moves a fit residual | base-pressure round 1, 6 of 6 found all 15 | they fit until the residual is at the noise floor; a missed layer announces itself |
| "unstated" corrections that are still cells of text | flare round 4: sub-cooled condensate, a mis-ranged transmitter | found by all three low runs |
| a budget whose gaps are flagged, or equal the symptoms | cooler-fouling 20261109b official 2 of 3 in 3 min; recip 6 of 6; flare, every run; base-pressure 15 of 15 | the plan follows by counting |
| decoy tests or decoy units | flare, base-pressure (12 of 12 ignored the decoy) | ruled out by reasoning already done for another part |
| tight tolerances | impeller: one pass at a relative margin of 0.00004 | unforgiving is not hard |
| coupling, unsolved duties, heavier modelling | recip third design 3 of 3; borefield 3 of 3; cz-silicon-control official 3 of 3 (30 to 58 min each) | identify, fit and plan are inside the model's strengths at any effort |
| a carried fact | flare official 3 of 3 | Opus 5.5 at low effort makes the link |
| a temptation to over-check | furnace-tc-calibration 7b: official low 2 of 3 in 100 to 160 s, local xhigh 3 of 8 | catches careful runs, not quick ones: the gradient is upside down |
| wording that tips a judgment | base-pressure VC04 | the result follows the wording, not the evidence |
| anything the solver can validate against | relief-valve's superseded study; base-pressure's worked example; bore-form's four dense twin pairs | a dated wrong answer or a known pair is a self-check |
| noise-driven misses | vav prototype; impeller | reviewers read it as a knife edge |
| physics insight | wafer-chill-recipe 3 of 3 | recognised in the first minute or never; no resting place in between |

## 5. What the survivors have in common

Three mechanisms have stopped low-effort runs for a reason other than a slip.

| | A. Coverage under a zero-slack budget | B. A fault only in unseen inputs | C. A common-mode instrument error |
|---|---|---|---|
| task | hvac, vav, chill-bench 16 | turbine-tool-repair | bore-form |
| official low effort | 0 of 3, 1 of 3, 1 of 3 (opus-5-5) | not captured; xhigh 0 of 8 | not run in final form |
| where the trap lives | in what the run did not buy | in files the run never sees | in no cell; in nine records together |
| the false confirmation | the method checks out to 0.2 per cent | both examples reduce cleanly; own fault tests pass | the plant's report agrees to 0.1 um |
| why effort helps | sorting into classes before spending | it does not | testing one instrument against another |
| irreversible | yes: a spent visit is gone | yes: one program, unseen cases | no: nothing is spent |
| size of a miss | 13 to 25 per cent against 3 to 10 | 0.62 against 0.3 per cent | up to 12 um against 1.2 |
| status at today's gate | 0 of 3 once; 1 of 3 twice, which would now fail; not rerun since the bar moved | too strong: 0 of 8 | open; solved by Fable 5.2 at low effort |
| similarity cost | high: more than ten catalogue tasks use a budget | high: more than ten deliver a program | low |

Four properties are shared by all three and by none of the levers in section 4:

1. **No cell of text names the trap.** It is in numbers across records, in what was not measured, or in inputs
   not shown.
2. **The wrong route validates itself.** The check a careful solver runs on the wrong answer passes.
3. **A low-effort miss is wide and the same in every run:** the same 7 features, the same 8 boxes, the same
   hidden set. Compare flare and base-pressure, where each failing run failed on a different one-line slip.
4. **The trap survives the solver's own tooling.** A fit cannot absorb it and a residual cannot expose it.

A fourth mechanism is weaker and worth knowing: **a wrong record that no fit residual shows**, with a physical
consistency check as its only witness (base-pressure VC01, pump-wear P5). Each catches about one low-effort run
in three, so one of them leaves a task at 2 of 3 solved.

## 6. Advice for the next design

### 6.1 The arithmetic of a 0-of-3 bar

- If a low-effort run solves the task with probability p, the screen passes with probability (1 - p)^3: 0.73 at
  p = 0.1, 0.51 at 0.2, 0.30 at one in three.
- Three local probes cannot show p is small: 0 of 3 only bounds p below 0.63 at 95 per cent, and 0 of 9 below
  0.28.
- The same task must be solved 1 to 7 times in 8 at xhigh. 0 of 8 was accepted once and is not to be counted on.
- So do not aim for "low effort usually slips". Aim for a low-effort failure that is structural: every run fails
  the same way, by a wide margin, for a reason you can name before probing. Then look for that in the probes, not
  for the count.

### 6.2 Choosing the mechanism

- **Decide which of A, B or C carries the difficulty before building anything.** Every other layer is there for
  fairness and realism. Count on none of them.
- **Do not rely on one trap of kind C.** bore-form passes on one discovery. Two independent common-mode faults on
  different instruments, each with its own circular confirmation, would need two discoveries.
- **Kind A needs all of these at once** (each was the missing piece in a design that got solved):
  - many candidate units, with classes the solver must infer and no list of which units are unsettled;
  - a budget equal to the number of classes the records cannot settle;
  - at least one per-unit quantity no sibling predicts;
  - salient duplicates that invite a confirming measurement;
  - every fallback for an uncovered class missing by at least 1.3 times the band;
  - charged before the result, and not refillable.
- **Kind B needs a cue and a way to pass.** The fault must be standard practice for the trade and cued by a
  document's wording, or it is unfair; and some careful run must catch it, or the task goes 0 of 8.
- **Check similarity first.** Budgeted services and hidden-case programs are the two most used shapes in the
  catalogue.

### 6.3 Building a trap of kind C

1. **Write the auditor before the probes.** One script that runs on the agent-visible files and prints every
   check a systematic solver runs: peer ratios, step searches, closures, every pair of instruments on one object,
   pooled and split averages under two or three different significance tests. Whatever it prints as odd is found.
   This is how I found the two holes in 2.6 in a few minutes.
2. **Test the "clean bill" under more than one statistic.** If the pooled test is clean under your reference's
   test and flags the trap under the obvious alternative, the trap has a signature.
3. **List every witness.** For each object, every pair of measurements of it the solver can hold, including ones
   it buys. Decide on purpose which witnesses stay: xhigh needs a path to the answer, low effort must not trip
   over one.
4. **Make the circular confirmation exact.** The plant's own report should reproduce to the last printed digit on
   the wrong route.
5. **State circumstances, never the effect.** The lapsed certificate and the service line are the model.
6. **Then check it is not a wording trap.** Change the cue's wording and re-probe. If the solve rate flips, the
   wording is doing the work, and a reviewer can call it unfair in either direction.

### 6.4 Probing

- Force the probe's model to the screen's and use low effort, the instruction text only, and no working-style
  advice. A weaker probe model misread flare round after round; a stronger one may have misread bore-form.
- Record the model, the minutes, the tool calls and the reason for each failure next to every count.
- Any low-effort solve means not ready. A solve in two or three minutes means far from ready.
- Probe the bare core on three matched runs before building the evidence set, the second solution or the README.
- Verify the sandbox answers before launching probes into it.
- When a redesign and a model change coincide, run old and new bundle on old and new model before concluding
  anything.

### 6.5 Fairness, review and hygiene

- Every premise the answer needs is in an agent-visible document, stated as a circumstance.
- Dates carry enough detail to make every split exact.
- The reader enforces each formatting clause of the instruction literally and nothing else, with tests both ways.
- Every number in README.md and task.toml appears verbatim in the evidence file it cites. Regenerate all evidence
  after any change to the data.
- A requirement the verifier cannot observe is removed by construction, not left in the instruction.
- Within one categorical answer, numeric answers sit more than twice the band apart; the best constant sheet
  reaches one item and no more.
- A second solution written separately passes; the nearest wrong route is at 1.5 times the band or more.
- Run `tools/shipcheck.py` on the zip.

## 7. Actions by session

**bore-form-acceptance**
1. Correct the least-squares claim in README.md and task.toml on main, add a least-squares route to the route
   study, and regenerate the evidence. The claim is false by the sealed module's own numbers (2.6, item 3).
   In the same pass, make the drawing file and the sealed definition agree on the eight form tolerances (2.6,
   item 5).
2. Run three low-effort probes on 20261111d with the model forced to the screen's, and record minutes and
   failure reasons.
   - 0 of 3, each losing the same seven features: the layer holds at the gate as far as three runs can show.
     Then run three at xhigh on the same model. Three solves is the impeller pattern (local 3 of 3, official 8
     of 8); anything less, and 20261111d with the fixes from step 1 is worth Alex submitting, with the official
     screen as the measurement.
   - Any low-effort solve: the layer is dead at the gate. Do not submit; reuse the subject with a second
     independent fault.
3. Decide whether the RJ-44 and CB-22 witness stays. Round 6 closed half of it.
4. Reword "a pooled estimate finds nothing" wherever it appears. It is true of the reference's test only.

**flare-load-study**
- The carried fact is dead and so are stated two-state splits. The booking is not of kind A: every run chose the
  right two tests. Nothing else in the design is of kind A, B or C. A redesign has to add one; more layers will
  not.

**base-pressure-diagnosis**
- Each residual-invisible record catches about a third of runs, and the bar needs nearly all. VC04 follows its
  wording. A common-mode fault only helps if it does not show as a ratio: the 0.88 leak fault was found by all
  six probes because every chamber's test could be compared with its rated speed.

## 8. Corrections to earlier answers from this session

| said | correct |
|---|---|
| "Official 1 of 3 passes" (answers-bore-form, question 4) | True in October. On Nov 11 the screen allowed 0: flare 3 of 3 and base-pressure 1 of 3 were both rejected. |
| The trap "survived low effort, 0 of 3" | On the session's earlier model only. Fable 5.2 solves it at low effort. Unmeasured on the screen's model for the shipped bundle. |
| "No clean re-measurement exists for these features" | Every passing booking scans CB-22 or RJ-44, which both have RT-1 records. |
| "A pooled test says the tester is clean" | Under the reference's component-wise test. A modulus test flags orders 23 and 29 pooled. |
| Least squares and minimum zone "agree to 0.2 um" | They differ by up to 3.86 um; seven roundness features differ by more than the band. |
| "Impeller was refused against flange-torque-spec" | shrink-fit-hubs was. impeller-shrink-fits cleared similarity and failed difficulty. |
| The RT-1 parts "come from eight setups on four machines" | Five setups on three machines. Eight setups and four machines is all fourteen features. |

## 9. Checked by the flare session (Nov 11, 18:00)

Checked against this session's records: sections 0.3, 1, 3.7, the flare rows of section 4, 6.1 and the flare
paragraph of section 7.

**One statement is wrong.** Section 5, property 3: "Compare flare and base-pressure, where each failing run
failed on a different one-line slip." For flare that holds only for the first booking round (one run credited
an instrumented function, one missed the meter). In rounds 2, 3 and 4 every failing run failed on the same
slip, six of six: `docs/difficulty-calibration.md`, "Three iterations on flare-load-study", the table's last
column reads "the feed meter" for both rounds, and the round-4 table has both failing runs at PV-4001 = 52.84
against 54.92. So "the same in every run" does not separate the survivors from flare. What does is the width:
flare's miss was one valve coefficient 3.8 per cent low, 2.2 per cent on a row against a band of 1, three parts
of seven. Property 3 should rest on "wide", and on the miss being something the run did not buy or could not
see, not on its being repeated.

**One addition, in support of property 2.** In flare the check a careful solver runs pointed at the right
answer, not the wrong one: the 24 pre-retrim rows give 61.70 as indicated and 64.13 corrected against a data
sheet of 64.00. The wrong route did not validate itself; two Opus 5 runs asserted that it had without running
the check, and the screen's model ran it.

**Confirmed as written.**
- Section 1, the model dates: this session's last commit with an Opus 5 trailer is 58cf5c1 at 13:53 and its
  first with Fable 5.2 is 7a3061b at 16:01. Every flare probe before the opus-forced ones was launched before
  13:10, so all of them ran on Opus 5.
- Section 1 and 3.7, the matched probes: two completed, 7 of 7 each, 188 s and 188 s; the third left no study.
  Whether `model: "opus"` is opus-5-5 is inference here too; the agreement with the screen is the only evidence.
- Section 3.7, the official trials: 2m58, 2m39 and 3m06, worst departure 0.34 per cent, and each trial's
  analysis names the meter correction or passes instrument-air failure within 0.16 per cent, which a missed
  correction puts at 2.2.
- Section 4, "unstated corrections that are still cells of text": found by all six Opus 5 probes of round 4,
  not three, and by the three official trials and both matched probes.
- Section 6.1: 0.729, 0.512, 0.296; the bounds are 0.632 and 0.283.

**What it does to the three ideas this session proposed at 17:30** (gearbox bench efficiency, shaft alignment
moves, engine cylinder balance). All three were of kind C with one discovery each, and each had a free witness
of a kind section 4 lists as found: a heat balance (a closure), face readings on four trains (a second
instrument on the same object, then a carried fact), fuel-cut traces split by bank (a split the solver makes
unprompted). None should be built as proposed.
