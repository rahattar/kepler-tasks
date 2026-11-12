# journal-bearing bare core v2 (Nov 12): low 3 of 3, xhigh 3 of 3, easier than v1

v2 is v1 plus a drain RTD at every operating point, with supply RTDs that read 4 to 5 K out for a period in
four hidden packages and one stuck in a fifth. Only the heat balance tells which supply RTD is right: all the
power loss leaves with the oil, so the right inlet temperature reproduces the drain reading.

| probe (opus) | result | what it did with the drain |
|---|---|---|
| low 1 | accepted | "takes the one whose calculated outlet temperature best matches the drain reading" |
| low 2 | accepted, 22 min | the same, above a 1.5 K disagreement |
| low 3 | accepted | the same, above 1 K; checked first that the examples' drain matches its outlet within 0.25 K |

All three xhigh probes were accepted too, by the same check, with 600 points in 2.8 to 5.2 s.

- **A column with no stated use is a signpost.** All three low-effort runs saw `drain_C`, connected it to the
  outlet temperature the standard defines, and used it as the arbiter. The trap analysis says the same of
  cells of text; it holds for a column of numbers too.
- **The fault that needed physics was easier than the fault that needed a guess.** v1's stuck sensor had no
  witness and one low run in three guessed the right screen. v2 gave the witness and all three used it.
- **The three programs accepted on v1 all fail v2**, so the faults themselves are not weak: what is weak is
  hiding a determinate fault from a solver that is handed its witness.

What is left that has not been tried: the time limit. Every program so far runs 600 points in 9 to 50 s
against 60. v3 keeps v2's records and faults and makes the record long (hourly, about 12 000 points) with a
limit a point-by-point solver cannot meet.
