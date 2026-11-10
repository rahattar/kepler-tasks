# Kepler tasks

Alex's AfterQuery Kepler task bundles (Harbor format, mechanical engineering) and the working method behind them.

- `docs/playbook.md`: how tasks are built, packaged and delivered. Read this first.
- `docs/difficulty-calibration.md`: what makes official runs fail, and what did not work.
- `docs/rejection-patterns.md`: reasons for rejection and the validation failures so far.
- `docs/catalogue.md`: every task built so far. A new task must differ from all of them.
- `docs/design-note-base-pressure.md`: the latest task and its calibration history.
- `docs/fact-sheet-base-pressure.md`: what its instruction has to carry (not part of the bundle).
- `docs/design-note-vacuum-pumpdown.md`: the task it replaces, withdrawn on similarity.
- `docs/design-note-impeller-fits.md`: an earlier task.
- `tasks/<name>/`: the latest bundle of each task, unpacked. `.source_zip` names the zip it came from.
  `tasks/impeller-shrink-fits` is the most complete template.
- `tools/`: mkprobe.sh (sandbox for probe agents of a task with a per-test lab), mkprobe-vacwork.sh (the same
  for a task whose rig is a submit-once order program), gradeprobe.sh (grades probe sheets with a task's own
  grader), brief.txt and brief-bpd.txt (probe briefs), write_meta_example.py (writes task.toml and README
  explanation texts).
