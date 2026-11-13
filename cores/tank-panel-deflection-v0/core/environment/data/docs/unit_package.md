# Unit package

A unit sends the flat-walled tanks, casings and ducts on its register in as one package, a directory of four
files.

| file | columns |
|---|---|
| `unit.json` | `unit`, the unit's name; `panels` and `rows`, the number of panels and of rows in the package |
| `materials.csv` | `material`; `E_GPa`, its modulus of elasticity in GPa; `poisson`, its Poisson's ratio |
| `panels.csv` | `panel`; `item`, the tank, casing or duct the panel belongs to; `a_mm` and `b_mm`, the panel's longer and shorter side in mm (PS-4 2.1); `t_mm`, its thickness in mm; `material`, as named in `materials.csv` |
| `conditions.csv` | `row`; `panel`; `condition`, the number of the condition in the item's list; `pressure_kPa`, the pressure difference across the wall in that condition, in kPa (PS-4 section 3) |

The results of a package are one row for each row of `conditions.csv`: `row`, `deflection_mm` and
`edge_stress_MPa`, the two results of PS-4 section 4.

The packages under `examples/` have been calculated: each holds `expected.csv`, its results to PS-4, written
to five significant figures. The package under `pending/` has not been calculated yet.
