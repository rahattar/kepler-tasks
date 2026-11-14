# Line package

The records of one works, in one directory: four comma separated files with a header row.

## materials.csv

One row for each material used in the works. `material`; `E_MPa`; `alpha_per_K`; `k0_MPa`; `C1_MPa`, `gamma1`,
`C2_MPa`, `gamma2`, `C3_MPa`, `gamma3`; `Q_MPa`; `b`. These are the constants of PW-5 section 2.

## lines.csv

One row for each pipe line. `line`, its name; `material`; `mean_radius_mm`, R; `wall_mm`, t.

## history.csv

The plant history of every line, one row for each state, the states of a line numbered from 0 in the order
they followed each other. `line`; `state`; `pressure_MPa`, p; `dT_K`, the bore temperature less the outside
temperature; `checkpoint`, 1 at a state whose ratchet strain is asked for, else 0. State 0 of every line is
p = 0, dT = 0.

## expected.csv

In a works that comes with its results. `row`, the line and the state number in five digits joined by a
hyphen (`KI-3-00419`), for every checkpoint of every line; `ratchet_pct`, the ratchet strain of PW-5
section 4 in per cent.
