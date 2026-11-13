# tank-panel-deflection bare core v0 (Nov 13): low 3 of 3 solved, in 13 to 29 minutes

A timed program on shifted hidden data. `panels.py` reads a unit's package (panels, materials, pressure
conditions) and writes the centre deflection and the edge stress of every flat wall panel at every condition, to
a plant standard PS-4 that states the physical situation and no method: a thin elastic plate welded to stiff
members, so its edges do not deflect, rotate or move in the plane of the wall. 20 s of CPU a run, both results
within 1.5 per cent.

**What was meant to carry it.** The validity limit of the working model. Small-deflection plate theory is right
on both examples with results (plate walls, deflection up to 0.04 of the thickness) and wrong on the sheet walls
of five of the six hidden units (deflection 0.3 to 4.1 thicknesses, where the middle surface stretches). The
regime is in the visible data twice: the package without results (dryer_hall, up to 3.7 thicknesses), and a
drift on the example results that stays inside the band (edge stress up to 0.5 per cent, deflection 0.07).

| what was run | examples | hidden units | cpu a run |
|---|---|---|---|
| reference (`ref_panels.py`: von Karman plate, Ritz, table over side ratio and load for each Poisson's ratio) | accepted, worst 0.04 of the band | accepted, worst 0.04 | 4.5 to 6.6 s |
| small-deflection program (`lin_panels.py`) | accepted, worst 0.34 of the band | 5 of 6 fail, 550 to 1227 rows each, every row above 0.3 thickness | 2 s |
| unoptimised version (`naive_panels.py`, every row from scratch) | | right on every 40th row (0.015 per cent) | 0.1 s a row: 54 to 205 s a unit |
| low L1 (opus), 13 min | within 0.06 per cent | **accepted**, worst 0.04 of the band | 1.0 to 2.2 s |
| low L2 (opus), 29 min | within 0.13 per cent | **accepted**, worst 0.08 | 0.6 to 2.2 s |
| low L3 (opus), 18 min | within 0.02 per cent | **accepted**, worst 0.01 | 0.4 s (table worked out beforehand and embedded) |

No xhigh probe was run: the screen allows no low-effort solve.

**Why it fell.** None of the three ever wrote the small-deflection program. Each chose the large-deflection
model before it had run anything, from the standard's own description of the panel. L3: the membrane effects
are included "because those held edges bring them in". L1 named three things: the edges that cannot move in
the plane, the example edge stress per unit pressure that "climbs slowly with load", and a dimensionless load
of about 1,560 in the pending package against 1.5 in the examples. All three then wrote the same method as the
reference (a polynomial Ritz solution on one quadrant, Newton, a table in the dimensionless load) and checked
it against the small-deflection limit and their own finer solutions.

- **The validity limit of a working model is not a lever when the standard has to state the circumstance that
  breaks it.** Fairness needs the in-plane edge condition written down, because the answer depends on it; and
  written down it selects the model. The solver did not hold the assumption the design counted on.
- **A model with nothing to check it against in its own regime was implemented correctly three times out of
  three.** The limit case and a refinement study were validation enough.
- **The drift on the examples and the pending package were both read**, at low effort, in the first minutes.
- **The time limit decided nothing**: every program ran in a sixth of it or less.
- L3 found a defect of the core: some pending panels have a short side up to 620 thicknesses, outside the
  standard's stated scope of 25 to 500. The generator sizes the side from the thickness without checking it:
  the short side runs from 16 to 620 thicknesses over the nine units, with 38 panels above 500. It did not
  touch the grading, which follows the thin-plate definition at any ratio.

**Checks on the sealed definition (`plate.py`).** The linear limit reproduces the clamped square plate's
coefficients (0.013816 against 0.013817 for the deflection, 0.3080 for the edge moment). A second solution
written apart from it (`fd_check.py`, finite differences and bilinear cells, extrapolated) gives the centre
deflection within 0.05 per cent at loads to 2,000; its edge stress converges at first order and is not a check
yet. Levy's clamped square plate, as tabulated, lies 0.4 to 2.4 per cent above it.

## Files
- `plate.py` sealed definition; `gen.py` the nine units; `core/` the agent's data and the hidden units with truth
- `ref_panels.py`, `lin_panels.py` (imports the reference), `naive_panels.py`; `grade.py` (20 s of CPU a run)
- `fd_check.py` the second solution; `brief.txt`, `mk.sh` probe brief and sandbox builder (through tools/mkprobe.sh)
- `L1.log`, `L2.log`, `L3.log` the graded runs; `probes/` the three programs as delivered
