# Bearing case files

A case is a folder with two files.

`bearing.json`
- `tag`: the bearing's tag
- `diameter_mm`: journal diameter, 2R
- `length_mm`: bearing length, L
- `radial_clearance_um`: radial clearance, c
- `groove_angles_deg`: the angles theta of the axial oil grooves (LS-3 section 2)
- `oil`: `grade`; `nu40_cSt` and `nu100_cSt`, the kinematic viscosity in mm2/s at 40 C and 100 C;
  `rho15_kg_m3`, the density at 15 C
- `oil_flow_L_min`: oil flow to the bearing, Q

`points.csv`, one row for each operating point
- `point`: the point's name
- `speed_rpm`: journal speed
- `load_N`: load on the journal, W
- `load_angle_deg`: load angle, beta (LS-3 section 2)
- `inlet_C`: oil inlet temperature, T_in

The three cases in `examples` each carry a third file, `expected.csv`: the results to LS-3 for every point of
the case, in the columns `point,h_min_um,attitude_deg,power_kW,t_eff_C,p_max_MPa`.
