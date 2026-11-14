# Start prompt for a new session (paste into the other account)

I'm Alex. You will build AfterQuery Kepler eval tasks for me (Harbor format, mechanical engineering). Everything you
need is in the GitHub repo rahattar/kepler-tasks; attach it and clone it.

1. Before anything else, read docs/playbook.md (its design gate first), docs/review-2026-11-13-five-cores.md,
   docs/difficulty-calibration.md, docs/rejection-patterns.md, docs/trap-analysis-2026-11-11.md,
   docs/afterquery-asks-2026-11-11.md, docs/catalogue.md and docs/design-note-impeller-fits.md. The playbook's rules
   are standing rules; follow them exactly. Before each later build, read what was added to rejection-patterns.md
   and difficulty-calibration.md since your last read: other sessions push to main all day.
2. Use tasks/impeller-shrink-fits as the template for the bundle layout, the sealed definition, the lab wrapper,
   the grader, the evidence scripts and preflight. Skim the README.md of the other tasks only as far as you need
   to stay clear of their subjects, deliverable shapes and verification. For a timed program task, tasks/journal-bearing-survey
   is the complete example: a per-run limit in tests/ and in instruction.md, pinned threads, a timeout failing
   the task, the naive version shown timing out, the hidden shift in a manifest.
3. Propose 5 new task ideas in mechanical engineering. AfterQuery's top priority (Nov 11, repeated Nov 13) is the
   kind in docs/afterquery-asks-2026-11-11.md, so propose that kind first: the tests re-run the agent's program
   on hidden inputs under a per-run time limit stated in instruction.md, and the hidden data is deliberately
   shifted from the visible data. Each idea must differ from every catalogue entry in subject and physics, and
   in what decides a hidden case. For each give: everything that decides a hidden case, written as the
   documents will state it (what may differ and the criterion that settles it); the pre-mortem (what a careful
   engineer holding those documents does in the first ten minutes, and why that does not pass); where the
   difficulty sits once all of it is stated; the shift; and why the first program a competent solver writes
   misses the time limit. Drop any idea whose stated version a careful engineer passes. Wait for me to pick one.
4. Then build it end to end:
   - the generator, sealed definition and tune checks;
   - environment, solution and tests;
   - the full evidence set and preflight;
   - local probe rounds: 3 low and 3 xhigh subagents in sandboxes, with the model forced to the official
     screen's, each graded with the task's grader;
   - calibrate to the bar: the easiness probe solves 0 of 3 at low effort, and the difficulty probe lands in
     its pass band of 0 to 5 of 8 at xhigh. If every probe fails the same check with the same wrong answer,
     read their reasoning for something hidden or unclear before calling it difficulty. Probe the bare core
     this way, with every deciding condition already stated, before building the evidence set;
   - for a timed task, run the self-check in docs/afterquery-asks-2026-11-11.md before packaging.
5. Give me an instruction.md draft and a fact sheet; I write the final instruction.md myself. Check my rewrite
   against preflight.
6. Package `<task>-YYYYMMDD.zip`. Deliver it to "/Volumes/AlexB4344665031/Projects/AIWorks/AfterQuery Kepler" if
   this session is linked to my Mac, and verify the md5; otherwise send me the zip.
7. Commit the finished bundle unpacked under tasks/<name>/ and add a design note under docs/. Update
   docs/catalogue.md, and add any new lessons to docs/difficulty-calibration.md or docs/rejection-patterns.md.
   Push to the repo.

Be concise, ASCII only, natural prose. Handle defaults yourself; ask me only about decisions that are really mine.
