# journal-bearing bare core v3 (Nov 12): low 2 of 3, xhigh 2 of 3, no gradient

v3 is v2 plus two hourly records of about 30 500 operating points each, and a limit of 30 s a run. Solving
point by point cannot meet it: the fastest v2 program takes 90 s on a long package (`jd4_big.log`). The
reference takes 9 to 13 s by working the laminar film out once for each geometry on a grid of journal
positions and solving every point from that table at once.

| probe (opus) | result | long packages | how it met the limit |
|---|---|---|---|
| low 1 | accepted, 20 min of work | 4.0 and 4.9 s | film tabulated over eccentricity and position, plus a Reynolds axis |
| low 2 | 1 point of 60 out on one small package | 1.6 and 1.9 s | the same, computed lazily; peak pressure stored for each land |
| low 3 | accepted | 6.7 and 7.5 s | a coarse table to find the points, a fine one where they lie |
| xhigh 4 | accepted | 1.0 and 3.1 s | tables for each geometry and load direction |
| xhigh 5 | accepted | 1.6 and 1.8 s | tables computed in advance (70 min) and embedded in the program, 1.6 MB |
| xhigh 6 | 7 points of 60 out on the lightly loaded package (peak pressure 2 to 11 per cent) | 3.0 and 3.5 s | tables refined near the grooves; not fine enough near zero eccentricity |

- **Every run found the tabulation**, at either effort, most of them faster than the reference. A stated limit
  that the obvious method misses by a factor of three or more is read as an instruction to find the better
  method, and the better method here follows from the equation's own dimensionless form.
- **The two failures are slips of interpolation in peak pressure** at the edges of the tabulated range, on
  different packages. They are not the same miss, they are narrow, and they do not follow effort. This is the
  kind of failure the trap analysis calls noise.
- **The time limit did not separate anything.** It changed what the programs look like, not who passes.
