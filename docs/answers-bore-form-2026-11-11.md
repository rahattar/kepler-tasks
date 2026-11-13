# Answers on bore-form-acceptance (20261111c, commit 3de1906), Nov 11

> **Corrected on main.** Question 4's "0 of 3 isn't the bar" and "Only official 8 of 8 fails" no longer hold:
> the bar as of Nov 13 is 0 of 3 on the easiness probe and a pass band of 0 to 5 of 8 on the difficulty probe.

## Where the evidence comes from
- **Seen by me:**
  - impeller-shrink-fits 20261109b: the review text, with security and verification-explanation blocking and the
    prefix and fields advisory;
  - its official difficulty JSON, 8 of 8 solved and rejected as too easy;
  - shrink-fit-hubs's similarity rejection message.
- **Read in the claude.ai project docs:** earlier sessions on this account copied official pipeline pages into
  these (claude/kepler-spec.md, next-task-handoff.md, vav-official-run-oct19.md,
  kepler-difficulty-calibration-oct24.md, design-note-trap-task.md, design-note-cz-fleet-conversion.md,
  team-lead-rejection-patterns-oct18.md, review-postmortem-oct11.md). I did not see those pages, but the notes
  record them stage by stage.
- **"21 tasks through validation":** I can't confirm that count. These are the tasks the records show passing
  every automated stage. "Accepted" below means that; the human-review outcome is recorded only for chill-bench
  ("the approved task").

| task | when | easiness | difficulty |
|---|---|---|---|
| chill-bench-commissioning (approved) | Oct 2 | 1/3 | 1/8 |
| hvac-submittal-review | Oct 15, submission 4 | not captured | not captured |
| slab-cooling-dispatch | Oct 16 | | |
| puller-fleet-conversion f | Oct 18 | | |
| vav-airflow-calibration | Oct 19 | 1/3 | 7/8 |
| superheater-tube-life | Oct 25 | | 7/8 |
| turbine-tool-repair | | | 0/8, accepted |

## 1. Similarity: leave the harness alone, and don't let a sibling with the same harness go in at the same time
**(a) Where the gate sits.** The pipeline order, from kepler-spec.md:
1. structural checks;
2. AI check on instruction.md;
3. similarity;
4. reference verification (oracle 1, nop 0);
5. quality review;
6. anti-cheat;
7. easiness;
8. difficulty;
9. run audit;
10. human review.

hvac submission 4 logged its passes in exactly that order. shrink-fit-hubs's similarity verdict came back alone,
with nothing after it (seen).

So reaching quality review means that submission cleared similarity, but only that submission. The check runs
again on every submission, against a pool that changes. The rejection message names the pool: tasks "still in
validation or review, or already approved", and adds "if that task fails validation or is rejected, you can
resubmit this one".

impeller-shrink-fits was rejected at difficulty on Nov 9, before bore-form's first submission. By that wording it
left the pool. That is why 0.99 against it has never bitten. *Inference from the message wording; not tested.*

**The neighbour that matters now.** With impeller-shrink-fits and shrink-fit-hubs excluded (tools/similarity.py),
the nearest files are:
- skid-noise-guarantee: environment/Dockerfile 0.912, tests/Dockerfile 0.992, instruction 0.441;
- recip-cylinder-limits: grade_form.py 0.578;
- skid-noise-guarantee again: test.sh 0.998;
- flange-torque-spec: test_form.py 0.855, solve.sh 0.749.

flange-torque-spec is the one neighbour known to be in the pool: shrink-fit-hubs was refused against it as "still
in validation or review, or already approved" (seen). bore-form has cleared similarity five times with test_form.py
at 0.855 and solve.sh at 0.749 against it. So the gate is not refusing on harness files at these levels; what it
refused shrink-fit-hubs for was the whole task, which shared the subject and the deliverable as well. *Inference.*

If skid-noise-guarantee or recip-cylinder-limits is submitted while bore-form is in validation or review, the
second one to arrive is the one at risk. *Inference from the shrink-fit-hubs message.*

**(b) Leave it.** Five clean passes are direct evidence that the gate isn't matching bore-form against anything
live. A rewrite risks the structure literals again, which is the Nov 10 relief-valve lesson. Rewrite the
*siblings* before they are submitted, not bore-form.

**(c) The literal list and the script.**
- The list in playbook.md covers both codes we have seen, `artifact-parent-not-created` and `reward-txt-missing`.
- The spec page adds `COPY . /tests/` and the two pytest pins, which the list already has.
- I know of no other literal. shipcheck.py now checks the two coded ones on the zip.
- Committed tools/similarity.py:
  - it measures difflib ratio (whitespace-normalised) and token 5-gram Jaccard, by file role;
  - `--exclude` drops tasks out of the pool;
  - it reproduces your numbers exactly with no exclusions;
  - it is a proxy: the platform's measure isn't published.

## 2. The advisory: ignore it; no toml satisfies both
Accepted tasks got the same advisory and passed with it:
- chill-bench-commissioning, Oct 2: "name prefix and metadata fields", it "stayed advisory and every blocking
  criterion passed" (kepler-spec.md). That task was approved.
- puller-fleet-conversion, submission 2: "Advisory (ignored per spec): name prefix and metadata fields". It then
  passed every automated stage at revision f.
- impeller-shrink-fits 20261109b: the same advisory (seen).

On the schema itself:
- kepler-spec.md records the live template: all five fields are in it and the metadata block is required.
- Your own structure bounce (seven errors) confirms the structure check enforces them.
- The advisory and the structure check contradict each other, and only the structure check blocks.

**Leave it.**

## 3. Test-instruction alignment
**(a) Not copied from an accepted task.** I have no accepted task whose reader was checked against a stated
decimal-places clause, so "literal on stated, open on unstated" is our reading of the 20261111b finding.

What an accepted task does show is the other half, credited: vav-airflow-calibration's reviewer wrote "The
verifier has no hidden formatting convention: columns can be in any order and extra columns are ignored", under a
passing specification_completeness check. That instruction fixed neither.

**(b) Flagging risk.**
- **Your latitude (row order, CRLF, final newline, blank lines after the header, quoted fields):** I'd expect no
  flag. These are the same kind of freedom vav was credited for. *Inference.*
- **Your strictness:**
  - Every refusal traces to "exact header", "two decimal places" or "one of". The one I'd look at is ".50".
    It has two decimal places and the clause doesn't say a leading digit is required. A reviewer could call
    refusing it "checks what the instruction does not state". It's low risk, but accepting `\.[0-9]{2}` with an
    optional integer part removes it. *Inference.*
  - The real caution is variance. kepler-spec.md records a criterion passing twice on a near-identical file and
    failing on the third under a different reviewer model. Neither direction is safe for good, so prove both
    directions in verifier_checks, as you do.

**(c) The three trimming readers.**
- **impeller-shrink-fits:** leave it alone. It is rejected and out of the pool. Its one quality review
  (20261109c, seen) didn't raise alignment. Its decimals clause is "no more than three", which its reader does
  enforce, so it was only lenient on whitespace.
- **recip-cylinder-limits and skid-noise-guarantee:** fix both before submission. Neither has a quality review on
  record. The bore-form 20261111b finding applies to them word for word. *Inference from bore-form, not from their
  own reviews.*
  - skid's instruction says "one decimal place" and "in that order", but grade_power.py strips fields, takes any
    decimal from 40 to 160, and ignores the row order.
  - recip says "two decimal places", but grade_limits.py strips fields and takes any Decimal.

## 4. Gate order and the easiness screen
**Order.** As in 1(a). **Every resubmission runs the whole chain again**, easiness included:
- hvac submission 4 re-ran all ten stages;
- slab-cooling-dispatch's identical-zip resubmission ran anti-cheat, easiness, difficulty and run audit again.

**Local low against official low.** There is no clean mapping, and the rig has been wrong both ways
(review-postmortem-oct11.md).

| task | local low | official low | outcome |
|---|---|---|---|
| chill-bench 12 | 1/3 | 3/3 | failed |
| chill-bench 16 | 2/3 | 1/3 | passed |
| superheater-tube-life | 1/3 | passed (count not captured) | passed |
| hvac-submittal-review | 0/3 | passed (count not captured) | passed |
| impeller-shrink-fits | 0/3 | reached difficulty | so easiness passed; *inference* |
| bore-form, round 2 | 0/3 | 1/3 | design-note-bore-form.md, round 3 |

- I have no record of an official 0 of 3 with a local count beside it. Official 1 of 3 passes, as vav and
  chill-bench did, so 0 of 3 isn't the bar.
- What has mattered is how wide the low-effort gap is, not the count. Three runs at 7 of 14, each failing seven
  features, is a wide gap. That is the better shape. The worse one is runs failing by one feature.
- **Check:** your design note doesn't record what followed the official 1 of 3 at round 3. If that bundle reached
  the difficulty stage, its 8-trial result is the best calibration you have. Look it up on the platform page.

**Does a passing xhigh count against a task?** Only official 8 of 8 fails: impeller-shrink-fits (seen). 7 of 8
has passed twice (vav, superheater) and 0 of 8 once (turbine-tool-repair).

A single local 14 of 14 isn't disqualifying:
- superheater went local xhigh 2/2 and passed at official 7/8;
- but impeller went local xhigh 3/3 and came true as official 8/8.

**Do:** run two more local xhigh probes.
- If both solve, you are at impeller's 3/3 and should expect a difficulty rejection.
- If either fails, ship.

## 5. Graded instances discriminate: "best constant 1 of 14, none 2" should stand; leave it
- No accepted task's review quotes this criterion. It appears in our records only on bore-form 20261110d.
- The closest precedent: turbine-tool-repair, accepted at official 0 of 8, shipped constant_null.txt showing the
  best constant program getting 1 of 8 hidden sets right ("7 of 8 sets fail"). That bundle was reviewed with
  1-of-N free.
- vav and superheater showed discrimination as the distance from the nearest shortcut to the bound:
  - vav's nearest shortcut misses at 13.6% against a 10% band;
  - the Oct 25 note says quality review wants "the nearest trap at 1.5x the bound or more".

You have both: the constant sweep at 1 of 14, and the nearest wrong route at 2.88 against 1.2. Say the floor
argument in the verification text in one sentence, as rejection-patterns.md already does.

*Inference that the reviewer accepts it; not seen on this criterion.*

## 6. Evidence through the verifier: what you have exceeds the accepted tasks; leave it
- None of vav, superheater, turbine-tool-repair, hvac, slab or chill-bench runs pytest or test.sh in its evidence
  (grep of their authoring/evidence: only preflight mentions either, as text).
- What reviewers have actually demanded:
  - comparators structurally independent of the reference (puller-fleet submission 2, superheater);
  - verifier_checks built from the current reference, with nothing UNEXPECTED (impeller 20261109b, seen);
  - studies scored by the verifier's own module, and fresh evidence files (bore-form 20261110d).
- Running test.sh itself was my own addition on relief-valve, after its reward-txt-missing bounce. No reviewer
  asked for it.

grade_form plus pytest in a subprocess on 29 sheets covers everything on record. Adding a test.sh run is cheap
insurance, not a requirement.

## 7. Editing Alex's instruction: propose it and get his OK; don't ship it silently
This is Alex's rule, not a platform finding. The platform's AI check on instruction.md is gate 2. A one-filename
insertion is very unlikely to move that verdict. *Inference.*

The precedent is to propose and let him accept:
- hvac revision g shipped "Alex's revision-f text with the clarity fixes and new fields, for him to accept or
  rewrite". He used it as it was.
- puller-fleet's note records "paragraph breaks restored, prose untouched".

Send him the one-line diff and ship on his yes.

## 8. Every criterion and code on record
**Structure check (intake):**
- `compose-not-supported` (hvac, Oct 15);
- the eval-set marker word, matched literally even inside a checker that tests for it (hvac, Oct 15);
- a `cheat/` folder (spec page);
- `artifact-parent-not-created` and `reward-txt-missing` (relief-valve, Nov 10);
- `metadata-missing` x5, `subcategory-missing` and `fixed-category` (bore-form, Nov 11);
- blocked internal terms (reported in repo docs; I haven't seen the code);
- the verifier timeout cap of 13500 and the agent timeout range of 9000 to 28800 (spec page; not seen bounced).

**AI check on instruction.md:** "AI-generated instruction text is detected and rejected" (spec page).

**Similarity:** "Task is too similar to your own task X, which is still in validation or review, or already
approved" (shrink-fit-hubs, seen). Records-forensic and service-plus-budget skeletons failed it in October
(superheater and turbine notes).

**Quality review, blocking:**
- task security: encoded strings in preflight (impeller 20261109b, seen);
- verification explanation quality:
  - stale or UNEXPECTED evidence (impeller b, seen);
  - comparators that are the reference with a knob turned (puller submission 2);
  - proxy grading and stale numbers (bore-form d);
- difficulty explanation quality: the practitioner must be named, and agent-performance arguments are refused
  (chill-bench);
- instruction clarity: narration, comma splices, redundant contrastives, first person, a closing that restates
  criteria (chill-bench);
- "instruction quality: does not reflect genuine solving" (reported in repo docs; not seen by me);
- graded instances discriminate, typos, well specified (bore-form d);
- test-instruction alignment (bore-form b).

**Quality review, other requirements (superheater, Oct 25):**
- the solution text matches the code exactly;
- an independent second implementation;
- the nearest trap at 1.5x the bound;
- the load-bearing document named by absolute path;
- no narration.

**Advisory:** task readme, and the task toml schema (prefix and the five fields).

**Per-trial checks (easiness and difficulty analysis):**
- specification_completeness;
- solution_discoverability;
- verifier_correctness;
- boundary_fairness;
- policy_refusal;
- execution_blocked;
- unearned_credit;
- meaningful_difficulty.

**Infra, never counted against you:**
- `UnknownApiError` at a probe;
- an anti-cheat adversary that declines, followed by "missing result file: analysis.json" (slab and puller).

Resubmit the identical zip.

### shipcheck.py now checks, on the zip
1. **Contents.**
2. **task.toml.**
3. **The task's own preflight**, run inside the unzipped bundle. Two fixes here:
   - unzipping now keeps file modes, so the exec-bit checks stop failing falsely;
   - the folder is now named after the task, so name checks stop failing falsely.
4. **Structure literals:**
   - `RUN mkdir -p <artifact parent>` on a line of its own;
   - both reward.txt echo lines;
   - pytest and ctrf pins, plus numpy, scipy and pandas at the standard versions where installed;
   - verifier timeout 600.
5. **Spec-page limits:**
   - no compose file, no cheat/, no marker word;
   - no `FROM --platform`; the environment Dockerfile ends as root;
   - every pip install pinned with `==`, and no apt pins;
   - timeouts in range;
   - `environment_mode` separate, and the network modes;
   - no `allow_internet`;
   - cpus, memory and storage within the allowed sets;
   - a kebab-case task name;
   - keywords equal to tags;
   - conflicts_of_interest filled in;
   - the instruction ends with a blank line and the closing sentence, with no heading and no grading words.
6. **Hygiene:**
   - no decoding in code, checked by AST, so a preflight that only lists decoder names as strings passes;
   - exec and eval reported as a note;
   - ASCII only;
   - no all-uppercase names;
   - at most three words in the name;
   - no evidence .txt reporting a nonzero UNEXPECTED, a Traceback or PROBLEM;
   - no evidence .txt older than the newest provenance, solution or test code by more than 120 s.
7. **Every /app/data document named by absolute path.** This is a note rather than a failure when only the folder
   is named, as cooler-fouling did and still reached easiness.

**Tested:**
- bore-form-acceptance 20261111c: clean.
- Two mutated copies: every planted fault caught (compose, platform pin, unpinned pip, final USER, a grading
  word, a base64 import, non-ASCII text, an uppercase name, a folded mkdir, failing evidence, stale evidence, an
  unnamed document).
- impeller-shrink-fits and relief-valve-adequacy: clean.
- milling-chatter-limit: correctly refused. It has the real base64 strings in its preflight and a 4800 s verifier.
