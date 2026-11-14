# Pre-mortem: gear tooth film thickness under heavy load (Nov 14, before any build)

The design gate's test, run before building: is the stated version hard? The task would be a timed program for
the minimum film thickness of an isothermal Newtonian EHL line contact (Reynolds with cavitation, elastic
deformation, Roelands viscosity, Dowson-Higginson density, load balance), every equation stated, with the hidden
data shifted to heavier loads and slower speeds than the examples. Verdict: **do not build** the steady version.

## What was measured

`ehl.py`: Newton-Raphson on all nodes and H0, second-order upwind wedge, uniform mesh, continuation in load.
`conv.out`: refinement at two heavy loads. Steel gears, R 10 mm, E' 227 GPa, eta0 0.02 Pa s, alpha 2e-8 1/Pa.

| case | M | L | p_h | uniform N 500 / 1000 / 2000 / 4000 | converged | Dowson-Higginson | Pan-Hamrock |
|---|---|---|---|---|---|---|---|
| w 5e5 N/m, u 5 m/s | 33 | 11.7 | 1.34 GPa | 0.4213 / 0.4235 / - / - um | about 0.424 | 0.4210 (-0.7%) | 0.3911 (-7.8%) |
| w 1.5e6, u 1 m/s | 223 | 7.8 | 2.33 GPa | 0.1075 / 0.1149 / 0.1161 / no convergence | 0.1164 (extrapolated, order 2.3) | 0.1183 (+1.7%) | 0.1112 (-4.4%) |
| w 2e6, u 0.5 m/s | 420 | 6.6 | 2.69 GPa | 0.0525 / 0.0660 / 0.0675 / 0.0679 | 0.0680 (order 2.28) | 0.0701 (+3.2%) | 0.0663 (-2.6%) |
| w 2e6, u 0.2 m/s | 664 | 5.2 | 2.69 GPa | 0.0190 / 0.0316 / 0.0341 / - | not reached | 0.0369 | 0.0351 |

## Reading

- **The numerics are hard, as hoped.** At M 420 to 664 a uniform mesh of 500 nodes is 23 to 45 per cent low; a
  solver checked only at the examples' loads fails the heavy hidden cases badly. My own reference failed to
  converge at 4000 nodes at M 223 and at 2000 nodes at M 33: a robust reference needs a graded, second-order mesh.
- **The formulas are too good.** Dowson-Higginson lands within 0.7 to 3.2 per cent of the converged film at
  M 33 to 420, Pan-Hamrock within 2.6 to 7.8. They are fits to exactly these equations' numerical solutions.
- **So the stated version is a resolution contest.** To fail the formula, the band has to be about 2 per cent;
  a sound Newton solver on 1000 uniform nodes is 3 per cent low at M 420, as wrong as the formula. The gap
  between the worst sound method and the nearest unsound one would be below 1x, against the playbook's 2x, and
  the difficulty would come from tightening the band (rejection-patterns, team lead's items 1 and 5).
- **What would beat the formulas** (none measured): starvation with an Elrod-Adams film content, thermal EHL with
  the energy equation across the film, or transient EHL through the load steps of the gear mesh. Each needs a
  reference far heavier than this one.

## Also dropped tonight, before building: fractional (memory) damping in an elastomer mount

`fractional_mount_premortem.py`. Newmark stepping with the standard Grunwald-Letnikov sum, 1 ms steps: 1.2 to
1.4 per cent from the exact (frequency-domain) response at alpha 0.3, 0.6 and 1.0, and cutting the memory to the
last second changes nothing. What a competent engineer writes first passes.
