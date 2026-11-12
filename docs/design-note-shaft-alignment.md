# Design note: shaft-alignment-moves (Nov 11)

Built from the bare core `cores/shaft-alignment-v7` after seven rounds of probing on the screen's model
(`docs/difficulty-calibration.md`, the shaft alignment sections). The agent-visible records are byte for byte
the ones v7 was probed on; the task statement is v7's brief with the container's paths.

**Mechanism.** Kind A of `docs/trap-analysis-2026-11-11.md`: coverage under a zero-slack budget, where the
class left uncovered is one the solver never counted.

- Seventeen of 36 trains cannot be worked out from the records after the revamp: two turbines whose hot checks
  were ended by exhaust work, five lagged pumps, ten pumps whose pedestal cooling was blanked.
- The laser contractor measures six trains, all named in one order. No second order.
- The legible count is five (two turbines, three constructions of changed pump), which leaves a spare.
- The salient place for the spare is settled: three criticality A compressors with vibration work orders,
  whose records are complete and whose gearbox figure is the maker's.
- The sixth need is in numbers only: HSC-250 and HSC-400 are listed alike and ran at 0.38 and 0.47 of the
  pumped temperature in the 2019 survey. They now run at 0.80 and 0.66.

**What the bare rounds settled, and must not be changed without re-probing.**
- The close-out says what work was done and does not say it was done alike (v7). With that reassurance in,
  xhigh fell to 1 of 6.
- One order for all six visits (v6). One visit at a time let low effort read three reports first.
- Two model names for the split class (v2). With one name nobody asked, at any effort.
- The gearbox lateral figure's direction is in the column name (v5). Unstated, it gave a real reason to visit
  a compressor.

**Local rates on `model: "opus"`, bare core v7:** low 1 of 6, xhigh 3 of 6. v6, which differs only in the
close-out sentences: low 1 of 12, xhigh 1 of 6. The bundle itself has not been probed; nothing the agent sees
differs from v7 except the output format clause (exactly three decimal places).

**Known risks at the gates.**
- Easiness allows 0 of 3. At a low-effort rate of 1 in 6 that passes about 58 per cent of the time; at the
  pooled 2 in 18, about 70.
- A quality reviewer may ask where the transfer of one pump's measured ratio to its group is stated. It is not
  stated, by design: stating the groups is v0, which low effort solved 3 of 3 in 80 seconds. The README argues
  it from the survey (a fixed fraction by model) and the budget; three of six xhigh runs made the argument
  unprompted. If this is bounced as under-specified, the fix that keeps the trap is a general sentence in AP-12
  that a support's rise follows the pumped temperature by a fraction that belongs to the pump's construction,
  with no word on which constructions differ.
- The kit lookup is not a graded layer: the wrong kit moves the sag by at most 0.03 mm on these sheets. The
  README says so.
- Similarity: budget-shaped siblings in the catalogue are vav-airflow-calibration (40 boxes, five visits),
  chill-bench-commissioning and cooler-fouling-assessment. The subject, deliverable and verifier differ; the
  harness files were written fresh and measured with `tools/similarity.py`.
