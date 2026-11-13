# System packages

A package is a folder holding `system.json`, one JSON object:

- `tag`: the system's tag. `kind`: `tree` or `grid`.
- `nodes`: an object keyed by node id; each `{x, y, z}` in ft, z the elevation above the base of the riser.
- `pipes`: a list; each `{id, from, to, size, schedule, length_ft, fittings, group}`. `size` is the nominal size
  (table 1 of FP-7), `schedule` `40` or `10`, `fittings` a list of table 2 names, `group` a key of `groups`.
  `from` and `to` fix the sign convention only; flow may run either way.
- `groups`: an object keyed by group; each `{installed, service, C}`: the year the group's pipe was installed,
  its service, and the C the site register carries for it (FP-7 section 3), null where the register carries
  none.
- `lines`: a list; each `{number, heads}`, `heads` the line's sprinkler nodes in column order from cross main A.
- `heads`: a list; each `{node, K, line, column}`.
- `riser_base`: the node at the base of the riser, where the results are given.
- `hazard`: `{density_gpm_ft2, area_ft2, hose_gpm, spacing_branch_ft, spacing_lines_ft}`.
- `supply`: the supply curve at the base of the riser, `{static_psi, residual_psi, flow_gpm}`.
- `outlets`: the test outlets; each `{id, node, K, description}`.
- `gauge_ports`: the nodes where a test gauge can be fitted.
- `valves_unverified`: the valves not verified open; each `{pipe, fitting}`.
- `tests_on_file`: the flow tests made on the system before this re-rating and kept on file, oldest first. Each
  is a report in the form of `field_test_protocol.md` with the `date` it was made. Every valve was verified
  open for a test on file.

The package in `pending` is a system not yet re-rated: it is `system.json` alone.

The three packages in `examples` each carry two more files:
- `expected.json`: the results to FP-7, `{area, pressure_psi, flow_gpm}`, `area` the most demanding placement as
  `[first line, first column]`;
- `survey.json`: the groups' C and the valves' factors found for that system by an earlier investigation,
  `{C: {group: value}, valves: {pipe: factor}}`. They are what that system's field test would establish.
