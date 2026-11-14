# engine-indicating v7 (Nov 13 night): stated layers

After v6 (the index and gain stated, low 2 of 3 solved), Alex chose a redesign with harder physics, every
condition stated in IS-2. `is2_indicating.md` here is issue 5 of the standard. It states six layers:

| layer | IS-2 | visible | hidden cells it decides (reference with it left out, core data) |
|---|---|---|---|
| converter-range spikes | 3 | cell_03, cell_08, cell_11 | crashes on 7 of 8 |
| encoder index, one per cell | 3, 9 | cell_11 (-1.57) | 3 cells, 6 to 18 bands |
| a gain per transducer | 3, 9 | cell_11 (0.955 to 1.048) | 5 cells, 3 to 7 bands |
| thermal shock, a coefficient per transducer | 3, 9 | cell_13 (0.044 to 0.071) | 5 cells, 1.1 to 2.9 bands |
| misfires left out | 10 | cell_03 (with results), cell_13 | 4 cells, and cell_03 |
| knock: the peak on a 2.5 kHz Butterworth, both ways | 11 | cell_03, cell_08 (with results) | 2 cells, and both examples |

The reference (`indicate.py`) fits the index, every gain and every shock coefficient together, on the
compression stretch (Q nil) and the expansion stretch (Q constant), in the mean cycles of the cycles that
fired. It recovers every value: index within 0.01 degrees, gains within 0.002, shock within about 10 per cent.
Core data: 60 cycles a point in the examples, 120 elsewhere. Widest departure 0.35 of a band; 0.6 to 1.3 s a
cell.

`build.py` makes cells (`python3 build.py OUT CYCLES CELL...`); `grade.py` grades a program on a tree.

## Probes (opus = claude-opus-5-5), graded with the bundle's checker on the core data

| probe | time | hidden | what it did |
|---|---|---|---|
| low 1 | 21 min | accepted, widest 0.39 of a band | every layer; fit from three starting indices; filter in the frequency domain; numpy only |
| low 2 | 17 min | accepted, widest 0.61 | every layer; its own least-squares solver; filter as one matrix product; numpy only |
| low 3 | 10 min | accepted, widest 0.43 | every layer; refits when the misfire set changes; filter by FFT; numpy only |

Low 3 of 3. xhigh not run.

All three implemented the six layers as written, recovered the pending packages' index, gains and shock
coefficients to the values the generator used, and checked themselves on synthetic packages built from the
examples with known conditions. All three were faster than the reference (0.4 to 0.7 s a cell), having
dropped scipy to save its import time.

## What it shows

More stated layers did not slow low effort down enough to matter: six layers took 10 to 21 minutes against
v6's one fit in 7 to 11. With the whole standard written down, each layer is a paragraph to implement, and
the stated ranges let a solver build its own test packages, which all three did.
