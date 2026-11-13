# engine-indicating bare core v3 (Nov 13): low 0 of 3, xhigh 1 of 3. The design the bundle is built on.

v3 has two conditions that the same check answers, and nothing in words that points at either.

- **Index.** The encoder's index mark sits off top dead centre (v0 to v2).
- **Gain.** The transducer gives more or less than the indicating system's scale assumes. After the level is
  set at manifold pressure, a gain error bends the compression line much as an index error does: at cell_13 a
  gain of 1.06 fits as an index error of +1.48 degrees, the same at every point and cylinder to 0.01 degree.
- **Examples exactly sound** (index 0, gain 1), after v2.
- **Two pending packages without results:** cell_11 with the index 1.6 degrees out, cell_13 with a gain of 1.06.
- **Six hidden cells:** one sound, one index (+2.2), two gain (0.95, 1.07), two both (+1.3 with 1.05, -2.4 with
  0.96); three of them compression-ignition engines with compression ratios of 15.5 to 17.5.
- The format document says "the indicating system's angle" and "the indicating system's scale"; IS-2 is
  written for crank angle and cylinder pressure.

## Checks

| program | examples | hidden cells with rows out | by how much |
|---|---|---|---|
| reference (index and gain together, from nil heat release on the compression stroke) | accepted | 0 of 6 | worst 0.48 of a band; 0.8 to 2.0 s a run |
| records taken as the system has them | accepted | 5 of 6, every row | 2 to 17 bands |
| the misfit put down to the index alone | accepted | 4 of 6, every row (the gain cells) | 4 to 16 bands |
| the misfit put down to the gain alone | accepted | 3 of 6, every row (the index cells) | 5 to 22 bands |
| second solution (loops; compression simulated, index and gain fitted in pressure) | accepted on cell_03 | | index within 0.08 degrees, gain within 0.4 per cent on all six |

## Probes (opus = claude-opus-5-5)

| probe | time | hidden | what it did |
|---|---|---|---|
| low 1 | 3.7 min | 5 of 6 cells out | IS-2 as written |
| low 2 | 3.2 min | 5 of 6 cells out | IS-2 as written |
| low 3 | 7.1 min | 5 of 6 cells out | IS-2 as written |
| xhigh 4 | 21 min | 5 of 6 cells out | IS-2 as written; synthetic packages across the scope; never tested the pending records |
| xhigh 5 | 45 min | **accepted**, worst 0.23 of a band | found both: cell_11's valve events 1.6 degrees late, cell_13's compression 6 per cent steep; corrects each cylinder for both |
| xhigh 6 | 17 min | 5 of 6 cells out | IS-2 as written; its own generator for the whole scope |

- **Low effort does not look.** With sound examples and no entry to distrust, all three implemented the
  standard and stopped.
- **One careful run in three examined the two sessions that had not been calculated** and separated the two
  conditions by itself. It took 45 minutes against about 20 for the two that did not.
- **The miss is wide and the same** for every run that takes the records as given: every row of five cells.
- The runs that failed are not slips; they did not ask whether a record is the cylinder's pressure at the
  crank's angle.

## Reading

At the bar: low 0 of 3, xhigh 1 of 3 (band 0 to 5 of 8). v4 measures what one more result column does.
