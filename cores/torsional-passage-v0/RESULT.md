# torsional-passage v0 (Nov 13 night): genset shaft lines through speed sequences, everything stated

A timed program (`peaks.py`) for the peak crankshaft, coupling and generator shaft torques of each run of a
generating set's sequence of speed changes, and the coupling's rubber temperature at the end of each run, to a
standard (`ts4_torsional.md`) that states the whole model: a four-inertia line, an order-by-order engine
excitation, the speed schedule, and a rubber coupling that softens as the power it dissipates heats it. No
condition is left unstated. The hard part is computing the stated physics within the limit.

- **Truth** (`shaftline.py`): RK4 over the whole sequence at 30 steps to the shortest period, rubber
  temperature integrated with it. About 3.5 minutes for a hidden set.
- **Reference** (`peaks.py`): each order's state envelope in the line's state-space modes,
  X' = (A - i k w I) X + B F, exact and first order, stepped by exponentials in slow time; temperatures carried
  in slow time through the sequence; peaks rebuilt only where an amplitude bound allows. Hidden sets: accepted,
  widest 0.13 of a band, 0.6 to 2.4 s. Limit 6 s.
- Two dead ends on the way, kept out of the core: a cubic-stiffening coupling (harmonic balance in slow time is
  2 to 5 per cent out on fast passages), and a displacement-only slow-flow that drops Q'' (diverges on a 3 s
  ramp through the lightly damped crankshaft mode, and carries a spurious undamped rigid-mode oscillation).

## Routes on the core data (graded by `check_program.py`)

| route | hidden sets out | worst miss |
|---|---|---|
| the coupling's stiffness held at its reference value | 6 of 6 | 1.7 to 22 bands, rubber to 9 K |
| each run from the set's starting state | 6 of 6 | rubber 6 to 21 K |
| the steady response at each instant's speed | 6 of 6 | crankshaft 4 to 10 bands |
| direct time integration, correct | times out | about 210 s a set against 6 |

## Probes

(pending)
