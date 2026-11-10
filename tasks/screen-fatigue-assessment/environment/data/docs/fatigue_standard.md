# Plant standard FS-07: fatigue assessment of welded screen structures

Applies to the screen-house vibrating screens. Based on the IIW recommendations for hot-spot stress assessment.

1. Stress: hot-spot structural stress at the weld toe, from strain gauges on the plate surface, aligned across
   the weld toe. Stress = E x strain, E = 207 GPa. The hot-spot stress is the stress extrapolated linearly to the
   weld toe from two gauges in front of it; for gauges at 0.4t and 1.0t from the toe (t = plate thickness) this
   is 1.67 x stress(0.4t) - 0.67 x stress(1.0t). Gauges at other positions are extrapolated linearly from their
   actual positions.
2. Counting: rainflow (ASTM E1049) on the hot-spot stress history; mean stress is not considered (as-welded
   joints).
3. Resistance, hot-spot FAT class (stress range at 2 million cycles):
   | detail | FAT |
   |---|---|
   | exciter-beam gusset rev A (load-carrying fillet welds) | 90 MPa |
   | exciter-beam gusset rev B (redesigned, non-load-carrying) | 100 MPa |
   For plate thicker than 25 mm the FAT class is multiplied by (25/t)^0.3.
4. S-N curve: N = 2e6 (FAT/dS)^3 down to the knee at 1e7 cycles; below the knee slope 5, N = 1e7 (dS_knee/dS)^5,
   with no cut-off (variable amplitude loading).
5. Damage: Miner's sum D = sum n_i/N_i, counted from the date the weld entered service (commissioning, or the
   date the welded part was replaced).
6. The curves are design curves (mean minus two standard deviations): D above 1 marks a weld for inspection and
   repair planning; it does not mean the weld has cracked. The assessment reports the best estimate of D.
