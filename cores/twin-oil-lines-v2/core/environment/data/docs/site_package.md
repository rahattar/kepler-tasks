# Site package

A site sends the heated oil lines on its register in as one package, a directory of six files.

## `site.json`
- `site`: the site's name; `lines` and `records`: how many of each the package holds;
- `survey_allowance`: the number of pipes the survey crew will survey for this package (see "The survey crew").

## `oils.csv`
`oil`; `density_kg_m3`; `cp_J_kgK`, the specific heat; `k_W_mK`, the thermal conductivity; `nu50_cSt` and
`nu100_cSt`, the kinematic viscosity at 50 C and at 100 C (TS-2 section 2).

## `lines.csv`: the lines register
`line`; `pipes`, 1 for a single pipe and 2 for a pair (TS-2 section 4); `bore_mm` and `length_m` of a pipe as
laid (TS-2 5.1); `oil`, as named in `oils.csv`. The pipes of a line are named after it: `FL-214-A`, and for a
pair `FL-214-A` and `FL-214-B`.

## `surveys.csv`: the heat-loss surveys on file
One row for each survey of a pipe (TS-2 5.2): `date`; `pipe`; `line_flow_t_h`, the oil delivered to the line's
inlet manifold during the survey, in t/h; `flow_t_h`, the flow through the pipe; `t_in_C` and `t_out_C`, the
temperature of the oil where it enters and where it leaves the pipe; `t_amb_C`, the temperature of the
surroundings. Every pipe was surveyed in each of the site's three campaigns.

## `work_log.csv`: work done on the lines
`date`; `pipe`; `job`, as the fitters entered it.

## `records.csv`: the hourly records
`record`; `line`; `hour`, counted from the start of the line's run of records; `flow_t_h`, the oil delivered
to the line's inlet manifold in t/h; `t_in_C`, its temperature there; `t_amb_C`, the temperature of the line's
surroundings. The records of a line are an unbroken run of hourly readings in time order, taken with the line
in service throughout and its conditions steady at each reading.

Dates are `YYYY-MM-DD`. Every survey on file and every job is earlier than the first record. A package holds
up to 60 pipes and 1,500 records.

## The survey crew
The crew will make heat-loss surveys of pipes as they stand now, after the last record, each with its line at
its survey rating. It takes one order for a package, of at most `survey_allowance` pipes:

    heatsurvey PACKAGE_DIR PIPE [PIPE ...]

It prints `pipe,line_flow_t_h,flow_t_h,t_in_C,t_out_C,t_amb_C` and one row for each pipe named, read as in
`surveys.csv`. An order of more pipes than the allowance, or one that names a pipe the site does not have, is
refused whole and does not count. A second order for the same package in the same run is refused.

## Results
One row for each row of `records.csv`: `record`, `dp_kPa` and `t_out_C`, the two results of TS-2 section 6.

The two packages under `examples/` each carry one more file, `expected.csv`, their results to TS-2. The package
under `pending/` has not been calculated, and the crew takes no order for it yet.
