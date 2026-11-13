# engine-indicating bare core v1 (Nov 13): low effort 3 of 3 accepted, seven to ten minutes

v1 is v0 without the motored points: a package holds fired points only and the results table has a row for
each point and cylinder. Under the sheet's index the pending package's output is ordinary in every row (IMEP
7 per cent high, angles 1.6 degrees late). The index error shows only in the compression strokes of the fired
cycles, where IS-2's gross heat release must be nil before combustion starts.

## Checks

| program | examples | hidden cells with rows out | by how much |
|---|---|---|---|
| reference (index error from nil heat release on the compression strokes) | accepted | 0 of 6 | worst 0.25 of a band; index within 0.01 degrees; 1.1 to 2.1 s a run |
| index taken from the sheet | accepted | 5 of 6, every row | 1.8 to 17 bands |
| second solution (loops; compression simulated, fitted in pressure) | accepted on cell_03, 31 s | | index within 0.01 degrees on all six |

## Probes (opus, low effort)

| probe | time | hidden | what it did |
|---|---|---|---|
| low 1 | 7.1 min | **accepted** | checks every cylinder's top dead centre: heat release from -100 to -30 degrees must be nil; median shift applied when over 0.15 degrees |
| low 2 | 10.4 min | **accepted** | "cell_package.md says only how and when the index mark was set, so I don't trust it blindly"; the same check from -90 to -25 degrees |
| low 3 | 7.8 min | **accepted** | the same check on all points and cylinders together |

- **All three checked the index against the records without any impossible output to prompt them.** Each report
  cites the package's `encoder_index` entry (how and when the mark was set). A field the calculation does not
  use is a signpost, as journal-bearing v2 found for a column.
- **Each validated its correction on examples it had shifted itself**, by 0.7 to 2.5 degrees, and all three
  corrections are sound: worst 0.58 of a band on the hidden cells.
- Asked afterwards what had first raised the question, two probes were stopped by the model's safeguards
  (`reasoning_extraction`). Do not put that question to a probe; read its report and its files.
- The error message names the model the probes ran on: claude-opus-5-5. `model: "opus"` is the screen's model.

## Reading

Checking the phasing of a pressure record against its own compression line is this model's first move in this
subject once anything points at the index. v2 removes what pointed at it.

The packages are not committed (147 MB); `python3 gen.py core` with `ei.py` of v0 makes them again.
