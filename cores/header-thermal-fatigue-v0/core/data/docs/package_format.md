# Header packages

A package is a folder with two files.

`header.json`, one JSON object: `header` (the tag), `inner_radius_mm`, `wall_mm`, `material` (`grade`,
`diffusivity_mm2_s`, `E_MPa`, `alpha_per_K`, `poisson`), `k_pressure` and `k_thermal` (k_p and k_t of HF-3
section 3), and `sn_curve` (`N_ref`, `range_ref_MPa`, `m`, `cutoff_MPa`, HF-3 section 5).

`record.csv`: the header's start-ups, shut-downs and upsets from the plant historian, one row a second. Steady
running between them is left out, and each event begins from steady running. Columns: `event` (its number),
`t_s` (seconds from the event's start), `fluid_C` (the reading of the header's fluid temperature thermocouple),
`pressure_bar` (gauge), `outer_C` (the reading of the thermocouple on the header's outer surface, under the
insulation).

The two packages in `examples` also hold `expected.csv`, their results to HF-3 in the columns
`event,range_max_MPa,damage`. The package in `pending` is a header not yet assessed: it has no results.
