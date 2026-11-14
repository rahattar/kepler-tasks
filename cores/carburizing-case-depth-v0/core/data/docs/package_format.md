# Furnace packages

A package is a folder with three files, covering one furnace over some months.

`furnace.json`, one JSON object: `furnace` (the tag), `mass_transfer_mm_s` (beta of CD-2 section 3),
`probe_calibrated_day` (the day the furnace's oxygen probe was last calibrated against shim stock, in the days
of `loads.csv`), and `grades`: for each steel grade the furnace carburizes, `core_C_pct` and `alloy_factor` (f of
CD-2 section 3).

`loads.csv`, one row a load: `load`, `day` (when the load was charged, in days from the start of the record),
`grade`, `area_m2` (the surface area of the load's parts), `section_mm`.

`record.csv`: the furnace's record of every load from charging to quench, one row a minute: `load`, `t_min`
(minutes from charging), `furnace_C` (the control thermocouple), `cp_probe_pct` (the carbon potential the
furnace's oxygen probe gives), `cp_setpoint_pct` (the controller's setpoint), `enrichment_m3h` (the natural gas
the carbon potential controller adds to the carrier gas, m^3/h).

The two packages in `examples` also hold `expected.csv`, their results to CD-2 in the columns
`load,surface_C_pct,case_depth_mm`. The package in `pending` is a furnace not yet assessed: it has no results.
