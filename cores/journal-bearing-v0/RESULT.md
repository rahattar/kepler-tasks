# journal-bearing bare core v0 (Nov 12): solved at low effort

A program, `bearing.py`, that computes a grooved journal bearing's operating points to a plant standard (Reynolds
equation with rupture, heat balance, laminar or turbulent film), run on eight hidden cases under 60 s a run. The
hidden cases shift the regime: load toward a groove, eccentricity to 0.96, L/D 0.35, a turbulent film, a tilted
split, a very light load, oil at 12 to 82 C, and a 600-point survey across the transition.

| what was run | result |
|---|---|
| the reference (banded lands, one Newton for position and temperature) | accepted; 22 s on the 600-point case |
| a correct, unoptimised program (general sparse solves, nested loops) | right on every 60-point case; times out on the survey |
| low 1 (opus) | accepted; 11.8 s on the survey; 37 min of work |
| low 2 (opus) | accepted; 31 s on the survey (machine busy) |
| xhigh 6 (opus) | accepted; 10.5 s on the survey |

Low 3 and xhigh 4 and 5 were still running when v1 was started.

**Why it fell.** Everything the hidden cases need is in the standard's scope section and its formulas. Each run
generated its own cases across the whole stated scope (30 to 90 of them: other groove layouts, load angles,
turbulent points, eccentricity to 0.98), checked them against its own finer grids, and timed 600-point cases.
A stated scope is a test plan. A shifted regime that the documents describe is not a shift for the solver.

**What it leaves.** The time limit was met with room by every run, so compute alone is not the difficulty
either. Two runs found that near the transition both film states can satisfy the standard; the generator
already excludes such points, and v1's standard now says the laminar one is taken.

v1 keeps the physics and the cases and puts the difficulty where weld-preheat-temperature had it: the examples'
records are sound, and the hidden packages carry what plant records carry.
