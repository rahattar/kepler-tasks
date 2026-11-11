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
  - every input file named by absolute path;
  - no hint at any trap or mechanism;
  - the last paragraph exactly: "You have 28800 seconds to complete this task. Do not cheat by using online
    solutions or hints specific to this task."
- **task.toml:**
  - agent timeout 28800 s; verifier timeout 600 s; the verifier in a separate environment with no network;
  - the agent runs as user `agent`;
  - domain engineering-sciences, field mechanical-engineering;
  - the name prefix has so far been `afterquery/` (a reviewer flagged this as advisory; ask Alex for the required
    prefix);
  - difficulty_explanation says the data is synthetic and realistic, names the practitioner and the research
    analogue, and contains no agent-performance numbers.
- **README.md:** carries `## Difficulty`, `## Reference solution` and `## Verification`, each with the same text
  as the task.toml explanation fields.
- **Verifier pins:** numpy 2.1.3, scipy 1.14.1, pandas 2.2.3, pytest 8.4.1, pytest-json-ctrf 0.3.5. test.sh writes
  0 to the reward file first, then 1 only if pytest exits 0 and the ctrf report shows exactly 1 test, 1 passed.
- **Literals the structure validator looks for.** It reads the files as text, so these have to appear verbatim
  however the rest of the file is written. Found the hard way, twice, on relief-valve-adequacy:
  - `tests/Dockerfile`: `RUN mkdir -p /app/output` on a line of its own (error code
    `artifact-parent-not-created`), the five pins as `pkg==version`, `COPY . /tests/`, `WORKDIR /tests`,
    `ENV PYTHONUNBUFFERED=1`;
  - `tests/test.sh`: `echo -n "0" > /logs/verifier/reward.txt` and `echo -n "1" > /logs/verifier/reward.txt`
    with the path written out in full, not through a shell variable (error code `reward-txt-missing`);
    `mkdir -p /logs/verifier`; `--ctrf=/logs/verifier/ctrf.json`; `-p no:cacheprovider`.
  Originality has to be built *around* these, never by replacing them. See `docs/rejection-patterns.md` for how.
- **Truth:** comes from a sealed definition, never from running the reference. The agent can't read it: it sits
  in a root- or lab-owned 700 directory, reached only through a sudo wrapper that validates arguments and enforces
  the booking.

## Design rules (Alex's standing rule, Nov 5)
- Give no hints in the prompt or the files. Hide the trap in the analysis layer: the general approach must look
  right at first glance, and only checking the files or very fine, non-obvious details exposes it.
- Each new task must differ from the whole catalogue (`docs/catalogue.md`) in subject AND in deliverable shape and
  verification. No more variants of "a program scored on ~8 hidden cases".
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
- **preflight:** all of the rules above, checked mechanically. Rerun every evidence script and preflight after any
  change.

`tasks/impeller-shrink-fits/` is the most recent complete example to copy from.

## Calibration targets
- Easiness: 3 low-effort runs, at most 1 solved.
- Difficulty: 8 official xhigh runs, 1 to 5 solved.
- Locally, run probe subagents (general-purpose, effort xhigh, and low for easiness) in sandboxes built by
  `tools/mkprobe.sh`, with the brief in `tools/brief.txt`. Probes must not read anything outside their sandbox.
  Grade each with the task's own grader.
- Local xhigh runs stronger than official.

## Packaging and delivery
- Zip in the cloud: `zip -qr -X <task>-YYYYMMDD.zip README.md instruction.md task.toml authoring environment solution tests`.
- Deliver to Alex's Mac folder "/Volumes/AlexB4344665031/Projects/AIWorks/AfterQuery Kepler":
  1. stage the zip under /mnt/user-data/outputs;
  2. write it with the remote-devices device_commit_files tool;
  3. verify the md5 with device_bash at `$HOME/mnt/AfterQuery Kepler/`.
- If the desktop bridge isn't available, send the zip with SendUserFile.
- Then report to Alex briefly: what changed, the local probe results, and the instruction facts.
