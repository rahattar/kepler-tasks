# Start prompt for a new session (paste into the other account)

I'm Alex. You will build AfterQuery Kepler eval tasks for me (Harbor format, mechanical engineering). Everything you
need is in the GitHub repo rahattar/kepler-tasks; attach it and clone it.

1. Before anything else, read docs/playbook.md, docs/difficulty-calibration.md, docs/rejection-patterns.md,
   docs/trap-analysis-2026-11-11.md, docs/afterquery-asks-2026-11-11.md, docs/catalogue.md and docs/design-note-impeller-fits.md. The playbook's
   rules are standing rules; follow them exactly.
2. Use tasks/impeller-shrink-fits as the template for the bundle layout, the sealed definition, the lab wrapper,
   the grader, the evidence scripts and preflight. Skim the README.md of the other tasks only as far as you need
   to stay clear of their subjects, deliverable shapes and verification.
3. Propose 5 new task ideas in mechanical engineering, each clearly different from every catalogue entry in
   subject AND deliverable shape and verification. For each give the trap layers (aim for 12-15, several
   data-only). Wait for me to pick one.
4. Then build it end to end:
   - the generator, sealed definition and tune checks;
   - environment, solution and tests;
   - the full evidence set and preflight;
   - local probe rounds: 3 low and 3 xhigh subagents in sandboxes, with the model forced to the official
     screen's, each graded with the task's grader;
   - calibrate until low effort solves 0 of 3, every run failing the same way, and xhigh fails at least
     occasionally. Probe the bare core this way before building the evidence set.
5. Give me an instruction.md draft and a fact sheet; I write the final instruction.md myself. Check my rewrite
   against preflight.
6. Package `<task>-YYYYMMDD.zip`. Deliver it to "/Volumes/AlexB4344665031/Projects/AIWorks/AfterQuery Kepler" if
   this session is linked to my Mac, and verify the md5; otherwise send me the zip.
7. Commit the finished bundle unpacked under tasks/<name>/ and add a design note under docs/. Update
   docs/catalogue.md, and add any new lessons to docs/difficulty-calibration.md or docs/rejection-patterns.md.
   Push to the repo.

Be concise, ASCII only, natural prose. Handle defaults yourself; ask me only about decisions that are really mine.
