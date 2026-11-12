# System packages

A package is a folder holding two files.

## system.json

One JSON object, the system as the site's records describe it:

- `tag`: the system's tag. `kind`: `tree` or `grid`.
- `nodes`: an object keyed by node id; each `{x, y, z}` in ft, z the elevation above the base of the riser.
- `pipes`: a list; each `{id, from, to, size, schedule, length_ft, fittings, group}`. `size` is the nominal size
  (table 1 of FP-7), `schedule` `40` or `10`, `fittings` a list of table 2 names, `group` a key of `groups`.
  `from` and `to` fix the sign convention only; flow may run either way.
- `groups`: an object keyed by group; each `{installed, service, C}`, `C` the pipe register's figure, null where
  the register has none.
- `lines`: a list; each `{number, heads}`, `heads` the line's sprinkler nodes in column order from cross main A.
- `heads`: a list; each `{node, K, line, column}`.
- `riser_base`: the node at the base of the riser, where the results are given.
- `hazard`: `{density_gpm_ft2, area_ft2, hose_gpm, spacing_branch_ft, spacing_lines_ft}`.
- `outlets`: the test outlets; each `{id, node, K, description}`.
- `gauge_ports`: the nodes with a port where a test gauge is fitted for a campaign. The base of the riser has
  one as well.

## campaign.csv

The sheet of the system's re-rating campaign (FP-7 section 6), one row for each reading:

- `run`: the run's number, in the order the runs were made.
- `outlet`: the id of the test outlet the run drew water at; empty for a static run.
- `flow_gpm`: the run's flow; 0 for a static run.
- `port`: the node the gauge was on, a node of `gauge_ports` or the base of the riser.
- `reading_psi`: the gauge's reading.

## The examples

Each package in `examples` carries one more file, `expected.json`: the system's results to FP-7,
`{area, pressure_psi, flow_gpm}`, with `area` the most demanding placement as `[first line, first column]`.
