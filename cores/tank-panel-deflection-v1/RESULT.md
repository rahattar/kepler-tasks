# tank-panel-deflection v1 (Nov 13): not built. The physics does not give the window the idea needs

**The idea.** All three v0 probes solved the plate on one quadrant, so they compute symmetric equilibria only.
A panel with an initial bow, under pressure on its convex side, can leave the symmetric path by a mode that is
odd across the panel before the symmetric path reaches its own limit. A symmetric program then reports an
equilibrium that is converged, matches every check it can run, and is unstable. The rows between the two loads
would be decided by a stability check that nothing prompts.

**What was checked before building** (`shell.py`, `explore.py`): the v0 plate with a stress-free bow of H
thicknesses in the shape (1 - xi^2)^2 (1 - eta^2)^2, pressure against the bow raised along the symmetric path,
and the lowest eigenvalue of the tangent stiffness followed in each of the four symmetry classes. Poisson's
ratio 0.3. Loads are Q = p b^4 / (E t^4).

| side ratio | bow H | symmetric limit | first odd-mode loss (odd across the short side) | window |
|---|---|---|---|---|
| 1.0 | 1.5 to 8 | 111 to 1255 | none before the limit | none |
| 1.5 | 4, 6, 8 | 283.9, 468.1, 661.6 | 281.9, 466.0, 661.1 | 0.1 to 0.7 per cent |
| 2.0 | 4, 6, 8 | 239.1, 383.9, 527.7 | 234.2, 375.8, 520.0 | 1.5 to 2.1 per cent |
| 3.0 | 4, 6, 8 | 221.5, 354.2, 480.7 | 212.9, 335.9, 455.2 | 3.9 to 5.3 per cent |

Below a bow of 4 thicknesses no odd mode comes first at any side ratio.

**Reading.** The window is at most 5 per cent of the load and exists only for long panels with a deep bow. Rows
inside it sit next to a loss of stability, where the answer moves faster than the 1.5 per cent band, so they
could not be graded fairly, and there would be few of them. The idea needs a wide range of loads over which
the symmetric answer is wrong; this configuration does not have one. Heated flat walls were considered and not
computed: their first buckling mode is the symmetric one at every side ratio, and what follows it is a set of
competing stable patterns whose choice depends on how the state was reached, which no standard could fix.

Nothing was probed.
