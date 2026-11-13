# Kepler tasks

Alex's AfterQuery Kepler task bundles (Harbor format, mechanical engineering) and the working method behind them.

- `docs/playbook.md`: how tasks are built, packaged and delivered. Read this first.
- `docs/afterquery-asks-2026-11-11.md`: what AfterQuery wants now. Top priority (Nov 11, repeated Nov 13): tests
  that re-run the agent's program under a stated per-run time limit on deliberately shifted hidden data. The bar
  (Nov 13): easiness probe 0 of 3, difficulty probe pass band 0-5 of 8.
- `docs/difficulty-calibration.md`: what makes official runs fail, and what did not work.
- `docs/rejection-patterns.md`: reasons for rejection and the validation failures so far.
- `docs/catalogue.md`: every task built so far. A new task must differ from all of them.
- `docs/design-note-vacuum-pumpdown.md`: the latest task and its calibration history.
- `docs/design-note-impeller-fits.md`: the previous task.
- `tasks/<name>/`: the latest bundle of each task, unpacked. `.source_zip` names the zip it came from.
  `tasks/impeller-shrink-fits` is the most complete template.
- `tools/`: mkprobe.sh (sandbox for local probe agents), brief.txt (probe brief), write_meta_example.py (writes
  task.toml and README explanation texts).
