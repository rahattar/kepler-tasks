# Fan package format

Each fan's package holds:
- `fan_datasheet.md`: the OEM datasheet of the fan as built: shaft drawing (sections from the coupling end of the
  shaft), bearings and their stiffness, pedestals, coupling hub, impeller, speed range;
- `rotor_changes.csv`: the asset register's record of changes to the rotor since it was built, one row per changed
  property: `entered` (the date the register entry was made), `work_order`, `part` (`impeller`, `coupling hub`, or
  `shaft section FROM-TO mm` with the positions of the shaft drawing), `property` (`mass_kg`,
  `transverse_inertia_kg_m2`, `polar_inertia_kg_m2` or `diameter_mm`) and `value`, the new value;
- `maintenance_log.csv`: work on the fan since it was built: `date` (of the work), `work_order`, `description`;
- `impact_tests/`: the standstill impact test reports, one file per test;
- `new_impeller.md`: the impeller to be fitted.
