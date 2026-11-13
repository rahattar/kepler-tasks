# engine-indicating bare core v0 (Nov 13): low effort finds it in four to eight minutes, 1 of 3 accepted

A timed program on shifted hidden data. `indicate.py` reduces a test cell's cylinder pressure records to the
group's standard IS-2: gross IMEP, peak pressure and its angle, the 10 and 50 per cent burn angles and the gross
heat released, for every point and cylinder. Six hidden cells, 5 s a run, angles within 0.25 degrees, IMEP
within 1.5 per cent.

**What was meant to decide.** Where the encoder's index mark really sits against top dead centre. The package
says, truthfully, how it was set. In five of six hidden cells it is 0.9 to 2.4 degrees out, either way. The two
examples with results are sound (0.02 and -0.03 degrees); the pending package, without results, is 1.6 degrees
out. v0 packages hold motored points as well as fired ones, and the results table has a row for each.

## Checks

| program | examples | hidden cells with rows out | by how much |
|---|---|---|---|
| reference (index error from zero motored heat release) | accepted | 0 of 6 | worst 0.15 of a band; 0.9 to 1.9 s a run |
| index taken from the sheet | accepted | 5 of 6, every row | 3 to 26 bands |
| motored peak put on top dead centre | not accepted (1.6 bands on angle) | 6 of 6 | 1.6 to 5.7 bands |
| second solution (loops; index error from a simulated motored compression) | accepted, 31 s | | finds the same index errors |

## Probes (opus, low effort)

| probe | time | hidden | what it did |
|---|---|---|---|
| low 1 | 6.6 min | **accepted, 6 of 6** | saw the pending package's motored peak at +1.1 degrees and motored IMEP positive; models the motored peak with IS-2's own heat transfer and shifts by the gap |
| low 2 | 7.5 min | 3 of 6 | the same finding; zero motored heat release; then rounds the shift to a whole encoder pulse when within 0.15 degrees |
| low 3 | 4.0 min | 3 of 6 | the same finding and the same rounding |

- **All three found the index error from the pending package's own output.** Each ran its program on the package
  without results, read the motored rows and set them beside the examples' motored rows: a peak after top dead
  centre and positive work from a motored cycle. None needed more than that.
- **A result row that can come out impossible is a signpost.** The motored rows put the condition into the
  output table. Low effort checks the output of every visible package for plausibility against the examples,
  with or without expected results.
- **The two failures are a slip of their own making** (rounding to the encoder pitch), on 8 to 41 rows of three
  cells, not the designed miss.
- The limit was met by every program (0.3 to 0.7 s a run against a reference of 0.9 to 1.9 s).

## Reading

Too visible: the screen allows 0 low solves. v1 takes the motored points out, so that the wrong reading's
output is ordinary in every row and the index error shows only in the compression strokes of the fired cycles.

## Files

- `ei.py` truth physics and the sealed definition of results; `gen.py` the nine cells and their shift
- `ref_indicate.py` reference; `route_sheet.py`, `route_peak.py` the programs that stop short
- `second_indicate.py` the second solution, in plain loops
- `grade.py` runs a program on the hidden cells at the limit; `brief.txt`; `docs/` what the probes read
- The packages are not committed (147 MB); `python3 gen.py core` makes them again.
