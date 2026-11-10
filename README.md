# Kepler tasks

Alex's AfterQuery Kepler task bundles (Harbor format, mechanical engineering) and the working method behind them.

- `docs/playbook.md`: how tasks are built, packaged and delivered. Read this first.
- `docs/difficulty-calibration.md`: what makes official runs fail, and what did not work.
- `docs/rejection-patterns.md`: reasons for rejection and the validation failures so far.
- `docs/catalogue.md`: every task built so far. A new task must differ from all of them.
- `docs/design-note-impeller-fits.md`: the latest task and its calibration history.
- `tasks/<name>/`: the latest bundle of each task, unpacked. `.source_zip` names the zip it came from.
  `tasks/impeller-shrink-fits` is the most complete template.
- `tools/`: mkprobe.sh (sandbox for local probe agents), brief.txt (probe brief), write_meta_example.py (writes
  task.toml and README explanation texts).
