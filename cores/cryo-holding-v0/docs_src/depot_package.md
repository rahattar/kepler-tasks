# Depot package

A depot sends its tanks in for a holding period as one package, a directory of seven files.

## `site.json`
`site`, the depot's name; `tanks`, how many it has; `test_allowance`, the number of tanks the test crew will
test for this package (see "The test crew"); `holding_start`, the date the period starts; `holding_days`, its
length; `close_barg`, the pressure every tank is closed at, in bar gauge.

## `tanks.csv`: the tank register
`tank`; `capacity_m3`; `relief_barg`, the set pressure of the tank's relief valve; `ner_pct_day` and
`ner_t_amb_C`, the NER of the tank's acceptance test by the maker and the ambient temperature of that test;
`ner_date`, the date of that test.

## `depot_log.csv`: the depot's daily log
`date`; `t_amb_C`, the day's mean ambient temperature; `header_barg`, the day's mean recovery header pressure;
`meter_kg`, the recovery meter's total for the day.

## `tank_log.csv`: the tanks' daily log
One row for each tank on each day of `depot_log.csv`: `date`; `tank`; `in_service`, 1 for a tank in service
that day and 0 for one isolated and emptied for work, whose vapour does not reach the header; `gauge_kg`, the
gauge reading at 06:00, blank for a tank out of service; `filled_kg`, the mass ticketed into the tank that day,
0 if none.

## `work_log.csv`
`date`; `tank`; `job`, as the fitters entered it.

## `plan.csv`
`tank`; `close_gauge_kg`, the gauge reading the tank is filled to for the start of the period.

## `holding.csv`
`day`, counted from 1; `t_amb_C`, the mean ambient temperature forecast for the day.

Dates are `YYYY-MM-DD`. The daily logs run over the depot's three most recent logging campaigns, and every
entry in the logs is earlier than the start of the period. A package holds up to 10 tanks and a period up to
45 days.

## The test crew
The crew will make NER tests (CS-4 3.3) of tanks as they stand now, before the period starts. It takes one
order for a package, of at most `test_allowance` tanks:

    nertest PACKAGE_DIR TANK [TANK ...]

It prints `tank,ner_pct_day,t_amb_C` and one row for each tank named: the NER found and the ambient temperature
of the test. An order of more tanks than the allowance, or one that names a tank the depot does not have, is
refused whole and does not count. A second order for the same package in the same run is refused.

## Results
One row for each tank and each day of the period: `record`, as `TANK/DAY`; `tank`; `day`; `p_barg`;
`vented_kg`; `state`, the results of CS-4 section 6.

The two packages under `examples/` each carry one more file, `expected.csv`, their results to CS-4. The package
under `pending/` has not been calculated, and the crew takes no order for it yet.
