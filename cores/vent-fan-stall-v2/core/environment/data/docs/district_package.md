# District packages

A package is a folder holding the records of one ventilation district: ten files.

## `district.json`
- `district`: the district's name
- `survey_allowance`: the number of branches the survey crew will survey for this package (see "The survey
  crew")

## `branches.csv`: the register, one row for each branch
- `branch`: the branch's name
- `from_node`, `to_node`: the nodes it joins; its direction is from the first to the second (VS-4 section 2).
  The surface is the node `ATM`.
- `kind`: `airway`, `stopping`, `regulator`, `door` or `fan`
- `resistance_Ns2_m8`: for a stopping, the resistance it was built to; for a fan branch, the resistance of the
  fan's ducting; empty for the other kinds
- `item`: the regulator, door or fan standing in the branch; empty for an airway or a stopping

## `surveys.csv`: the pressure-quantity surveys on file
One row for each survey of an airway: `date,branch,dp_Pa,q_m3_s`: the day, the pressure at the airway's `from`
node less the pressure at its `to` node, and the airflow in the branch's direction, read together. A campaign
takes every airway of the district over a few days, the shafts and mains on the first and each panel on a day
of its own, and the district's regulators and doors are left as they stand while it lasts. A survey reads the
pressure difference and the airflow each within 0.3 per cent.

## `work_log.csv`: work on the airways
One row for each job: `date,branch,work`. `RESUPPORTED`: the airway was re-supported. `ENLARGED`: it was
enlarged. `INSPECTED`: it was inspected.

## `regulators.csv`: the resistance of every regulator at every setting
`regulator,setting,resistance_Ns2_m8`. Settings run from 0 (shut down as far as it goes) to 10 (full open).

## `doors.csv`: the resistance of every door
`door,resistance_closed_Ns2_m8,resistance_open_Ns2_m8`

## `fans.csv`: the fans
`fan,branch,model,blade_setting`: the fan, the branch it stands in, its catalogue model and the blade setting
it runs at.

## `fan_curves.csv`: the catalogue sheet of the fans' model
`model,blade_setting,flow_m3_s,pressure_Pa`: the tabulated characteristic at each blade setting of the
catalogue (VS-4 section 4), in order of airflow from shutoff to free delivery.

## `log.csv`: the settings of the regulators and doors
`time,item,setting`. The rows at the first time of the log give the setting of every regulator and door as
the record opens. Each later row is a change: the item and its new setting, a number for a regulator, `open`
or `closed` for a door, at the time the change was made.

## `points.csv`: the survey points
`point,time,branch`: the airflow in this branch at this time is wanted.

Dates are `YYYY-MM-DD` and times `YYYY-MM-DD HH:MM`. Every survey on file and every job is earlier than the
log. No survey point shares a time with a log entry. A package holds up to 200 branches, 150 log rows and
800 survey points.

## The survey crew
The crew will make pressure-quantity surveys in the district as it stands now, after the last entry of the
log, with every regulator and door at its last setting. It takes one order for a package, of at most
`survey_allowance` branches:

    pqsurvey PACKAGE_DIR BRANCH [BRANCH ...]

It prints `branch,dp_Pa,q_m3_s` and one row for each branch named, read as in `surveys.csv`. A second order
for the same package in the same run is refused. Where a program is written the crew answers for the two
districts in `examples`; it has not been to the district in `pending`.

The two packages in `examples` each carry one more file, `expected.csv`: the results to VS-4 for every survey
point, in the columns `point,flow_m3_s`. The package in `pending` is as its district sent it in: the ten
files, no results.
