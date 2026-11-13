# Kepler task playbook

How Alex and Claude build AfterQuery Kepler tasks (Harbor format, mechanical engineering, under Engineering
Sciences). Follow this exactly unless Alex says otherwise.

## Division of work
- Claude designs, builds, calibrates and packages each task.
- Alex writes or rewrites `instruction.md` himself; it must be human-written. Claude gives him a draft plus a fact
  sheet: the input paths, the command and booking, the output path and header, and the phrases preflight checks.
  Then Claude checks his rewrite against preflight.
- Alex prefers maximum conciseness, ASCII-only text and natural prose. He handles decisions; don't ask him what a
  sensible default answers.

## Hard rules
- **Bundle contents:** `README.md`, `instruction.md`, `task.toml`, `authoring/`, `environment/`, `solution/`,
  `tests/`. Nothing else: no fact sheets, notes, caches or jobs.
- **Zip name:** `<task>-YYYYMMDD[b|c...].zip`. Task names have at most 3 hyphenated words.
- **Names:** no all-uppercase file or folder names except README.md and Dockerfile. ASCII only, everywhere.
- **No obfuscation:** no base64, rot13 or encoded strings anywhere in the bundle. A security review rejected one.
- **instruction.md:**
  - no heading, and no grading words (grader, verifier, reward, score, pass, fail, tested, graded, partial credit);
  - no role ("You are the ... engineer"), no first or second person; it opens on the physical situation, and states
    the requirement as a physical condition with its number where an agent-visible document gives one
    (shaft-alignment-moves, Nov 11);
  - every input file named by absolute path;
  - for a timed task, the per-run limit in the announcement's words, "Each run of <program> must finish within N
    seconds on 1 CPU.", with the same N as `tests/`;
  - no hint at any trap or mechanism;
  - the last paragraph exactly: "You have 28800 seconds to complete this task. Do not cheat by using online
    solutions or hints specific to this task."
- **task.toml:**
  - agent timeout 28800 s; verifier timeout 600 s; the verifier in a separate environment with no network;
  - the agent runs as user `agent`;
  - domain engineering-sciences, field mechanical-engineering;
  - the name is `<prefix>/<task-name>` with the prefix every task here already uses, and that is the required
    form (settled by the relief-valve-adequacy structure rejection, Nov 10). Quality reviews print the prefix
    redacted as "the benchmark/..." and flag it as an advisory on every pass; it is not a request to change it.
    The prefix may appear nowhere else in a bundle - `tools/shipcheck.py` checks that on the zip;
  - `[metadata]` carries the full block, and the intake's structure check rejects the bundle without it:
    author_name, author_email, author_organization, author_profile, research_advisor, referred_by,
    conflicts_of_interest, domain, field, subfield, category (must be "Science"), subcategory (non-empty), tags,
    expert_time_estimate_hours, relevant_experience, difficulty_explanation, solution_explanation,
    verification_explanation. A quality review may describe some of these as unrecognised in an advisory note.
    Leave them where they are: the structure check is blocking and the advisory is not (bore-form, Nov 11);
  - difficulty_explanation says the data is synthetic and realistic, names the practitioner and the research
    analogue, and contains no agent-performance numbers. It never calls the work routine: one sentence on who does
    it, then the physical mechanisms with the figures that make each bind, then the measurement problem.
- **README.md:** carries `## Difficulty`, `## Reference solution` and `## Verification`, each containing the
  task.toml explanation field word for word. Edit the README, then copy the section into task.toml; preflight
  fails when the two disagree.
- **Verifier pins:** numpy 2.1.3, scipy 1.14.1, pandas 2.2.3, pytest 8.4.1, pytest-json-ctrf 0.3.5. test.sh writes
  0 to the reward file first, then 1 only if pytest exits 0 and the ctrf report shows exactly 1 test, 1 passed.
- **Literals the structure validator looks for.** It reads the files as text, so these have to appear verbatim
  however the rest of the file is written. Found the hard way, twice, on relief-valve-adequacy:
  - `tests/Dockerfile`: `RUN mkdir -p /app/output` on a line of its own (error code
    `artifact-parent-not-created`), the five pins as `pkg==version`, `COPY . /tests/`, `WORKDIR /tests`,
    `ENV PYTHONUNBUFFERED=1`;
  - `tests/test.sh`: `echo -n "0" > /logs/verifier/reward.txt` and `echo -n "1" > /logs/verifier/reward.txt`
    with the path written out in full, not through a shell variable (error code `reward-txt-missing`);
    each of them on a line of its own with nothing before it, so not in a `case` arm or after `&&`
    (shaft-alignment-moves, Nov 11);
    `mkdir -p /logs/verifier`; `--ctrf=/logs/verifier/ctrf.json`; `-p no:cacheprovider`.
  Originality has to be built *around* these, never by replacing them. See `docs/rejection-patterns.md` for how.
- **Truth:** comes from a sealed definition, never from running the reference. The agent can't read it: it sits
  in a root- or lab-owned 700 directory, reached only through a sudo wrapper that validates arguments and enforces
  the booking.

## Current intake priority (AfterQuery, Nov 11; sent again as a reminder Nov 13)
- Top priority, and the kind to propose and build first: Science tasks whose tests re-run the agent's program on
  hidden inputs under a per-run time limit stated in instruction.md (about 2-3x the reference's runtime, so a
  naive correct version times out; a timeout fails the task), on hidden data deliberately shifted from the
  visible data (new regime, injected faults, out-of-range values, unseen categories, edge cases; not a reseed),
  and 0-5 of 8 on the difficulty probe. Full checklist, the self-check to run before packaging and the verbatim
  messages: `docs/afterquery-asks-2026-11-11.md`.
- Nov 11-12 tips (same doc): every deciding fault or condition shows at least once in the visible data; docs and
  labels unambiguous; a correct standard method passes; the tolerance is checked by an independent solution; all
  probes failing the same check the same way means something is hidden or unclear; 0 of 8 is reviewed on the same
  rubric, and the difficulty must come from the science.

## Design rules (Alex's standing rule, Nov 5)
- Give no hints in the prompt or the files. Hide the trap in the analysis layer: the general approach must look
  right at first glance, and only checking the files or very fine, non-obvious details exposes it. This holds
  inside the tips above: unhinted is not hidden. Whatever decides a result shows at least once in the visible
  data, and every document and label means one thing.
- Each new task must differ from the whole catalogue (`docs/catalogue.md`) in subject AND in deliverable shape and
  verification. No more variants of "a program scored on ~8 hidden cases". The intake priority above is the
  exception AfterQuery asks for (Nov 11, repeated Nov 13): a program re-run under a stated time limit on
  deliberately shifted hidden data is the wanted shape. There the subject, the physics and what decides a
  hidden case must be new.
- Stay in mechanical engineering. The deliverable must be a measured or inferred engineering result.
- Aim for 12-15 independent layers, several of them data-only (`docs/difficulty-calibration.md`).

## Evidence set (authoring/evidence) that every task ships
- **Provenance:** a generator; the sealed definition; a tune/check script for the design rules; a seed screen.
- **route_study:** defective routes, each fails on the shipped seed, with counts on lab seeds 5301-5320. Every
  graded item must be failed by at least 3 routes.
- **method_spread:** sound variations, all of which pass on the shipped seed.
- **independent:** a structurally separate second solution that passes.
- **null_baselines:** naive answers, with per-item free passes listed.
- **hedge_study:** whether one answer can be right under both readings of a choice.
- **verifier_checks:** malformed and edge-case outputs, built from the current reference at run time. None may be
  UNEXPECTED.
- **reference_run:** the reference run through the real lab program.
- **For a timed task, also:** the naive but correct version run through the verifier and timing out; the
  reference's runtime beside the limit (the limit is about 2-3x of it); what the hidden-data shift is and where
  it is built, in the README as well, for the submission notes.
- **preflight:** all of the rules above, checked mechanically. Rerun every evidence script and preflight after any
  change.

`tasks/impeller-shrink-fits/` is the most recent complete example to copy from.

## Before any zip goes to Alex
- `python3 tools/shipcheck.py <new.zip> <previous.zip>` clean. It checks the zip itself, not the working tree.
- `python3 tools/similarity.py tasks/<task> --exclude <tasks out of the pool>` read, not obeyed: it is a proxy
  for a gate whose measure is not published (see the bore-form entry in `docs/rejection-patterns.md`).
- preflight clean, on the tree the zip is made from.
- The task.toml compared key for key, section by section and type for type, with a task that has passed
  intake. Never change the schema to satisfy an advisory comment; if an advisory and a rule in this playbook
  disagree, keep the rule and put the question to Alex.
- Every intake rule that has bounced a bundle is a preflight check: the metadata block, category "Science",
  non-empty subcategory, the three explanations, the 28800 s agent timeout, the instruction's closing sentence.
- The reference run end to end from the unzipped bundle, through `tests/test.sh` itself and not pytest alone,
  with the reward file read afterwards (journal-bearing-survey, Nov 13: test.sh's umask 077 broke a checker
  that every direct pytest run passed). On a machine with Docker, `tools/run_oracle.sh <zip>`.
- When a check in preflight has to be rewritten to let a change through, stop: that is the check doing its job.

## The verifier's reader is the instruction's formatting contract, literally
- For every formatting clause in instruction.md ("exact header", "two decimal places", "one of ..."), the
  reader enforces that clause as written: no trimming, no coercion, no accepting fewer decimals. A sheet with
  correct answers in a format the instruction does not state must fail (bore-form, Nov 11: the reader trimmed
  the header and took zero or one decimal).
- And nothing more: what the instruction leaves open stays open - row order, LF or CRLF (Python's csv module
  writes CRLF), a final terminator, empty lines, CSV quoting of a row's fields.
- verifier_checks carries the proof both ways: correct answers in each disallowed format, all refused; the
  correct sheet in each unconstrained variation, all accepted. preflight runs a few of each.
- After editing README.md, run `python3 tools/sync_explanations.py tasks/<task>`.

## Discrimination
- Every graded item must require the work, not just the sheet as a whole. Within each possible answer to the
  categorical part, no two items' numeric answers may lie within twice the grading band of each other.
- The null study sweeps constant sheets across the whole plausible range of the numeric answer crossed with
  every categorical answer, scored by the verifier. One item hit is the floor; two means an item is free.

## Evidence must go through the verifier
- Studies write a complete submission file and score it with the verifier's own grading module, never with a
  comparison of their own. One study runs the whole pytest verifier in a subprocess on complete sheets,
  including the reference, the second solution, every defective route and the best null sheets.
- Regenerate every committed evidence .txt after any change to the data. A stale figure in a committed file is
  read as a false claim.

## Premises the solver cannot infer
- If the answer depends on a fact that is not standard knowledge of the field and not derivable from the
  shipped records, it goes in an agent-visible document. Author's background knowledge is not specification.
- Probe reports are the detector: when a probe tests a load-bearing premise and concludes it does not hold, the
  documents are missing it.

## Calibration targets
- **The bar (Alex, Nov 13): easiness probe 0 of 3; difficulty probe pass band 0 to 5 of 8.**
- Easiness: 3 low-effort runs on claude-opus-5-5, none solved. Any solve is a rejection: flare-load-study
  20261111e (3 of 3) and an earlier base-pressure-diagnosis bundle (1 of 3) on Nov 11, cooler-fouling-assessment
  (2 of 3) on Nov 9. The 1 of 3 passes of October (vav-airflow-calibration, chill-bench-commissioning) are
  history, not a precedent.
- Difficulty: 8 official xhigh runs, 0 to 5 solved. 6, 7 and 8 of 8 are outside the band: impeller-shrink-fits
  failed at 8 of 8 (Nov 9), base-pressure-diagnosis at 8 of 8 (Nov 10) and again at 6 of 8 (20261111b, Nov 11).
  The 7 of 8 passes of October (vav-airflow-calibration, superheater-tube-life) are history, not a precedent.
  0 of 8 is inside the band (turbine-tool-repair) and is reviewed on the same rubric as any other count. At an
  xhigh solve rate of 1 in 3 the band is met 98 per cent of the time; at 1 in 2, 86 per cent; at 2 in 3, 53 per
  cent.
- Locally, run probe subagents (general-purpose, effort xhigh, and low for easiness) in sandboxes built by
  `tools/mkprobe.sh`, with the brief in `tools/brief.txt`. Probes must not read anything outside their sandbox.
  **Force the probe's model to the screen's** (`model: "opus"` on the Agent call): a probe on the session's own
  model read flare-load-study 1 of 3 for three rounds while the screen solved it 3 of 3, and the matched probe
  reproduced the screen exactly. Probe the bare core of a design this way before building anything around it.
  Grade each with the task's own grader.
- The local rig is not calibrated, and it has been wrong in both directions (chill-bench 12: local low 1/3,
  official 3/3; chill-bench 16: local 2/3, official 1/3). Do not assume official runs are weaker: local xhigh
  3/3 on impeller-shrink-fits came true as official 8/8. Treat local xhigh 3/3 as too easy;
  superheater-tube-life went local xhigh 2/2 and official 7/8, which is outside today's band.

## Packaging and delivery
- Zip in the cloud: `zip -qr -X <task>-YYYYMMDD.zip README.md instruction.md task.toml authoring environment solution tests`.
- Deliver to Alex's Mac folder "/Volumes/AlexB4344665031/Projects/AIWorks/AfterQuery Kepler":
  1. stage the zip under /mnt/user-data/outputs;
  2. write it with the remote-devices device_commit_files tool;
  3. verify the md5 with device_bash at `$HOME/mnt/AfterQuery Kepler/`.
- If the desktop bridge isn't available, send the zip with SendUserFile.
- Then report to Alex briefly: what changed, the local probe results, and the instruction facts.
