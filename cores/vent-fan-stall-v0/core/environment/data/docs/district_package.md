# District packages

A package is a folder holding the records of one ventilation district: eight files.

## `district.json`
- `district`: the district's name

## `branches.csv`: one row for each branch
- `branch`: the branch's name
- `from_node`, `to_node`: the nodes it joins; its direction is from the first to the second (VS-4 section 2).
  The surface is the node `ATM`.
- `kind`: `airway`, `regulator`, `door` or `fan`
- `resistance_Ns2_m8`: the resistance R of an airway; for a fan branch, the resistance of the fan's ducting;
  empty for a regulator or a door, whose resistance follows from its setting
- `item`: the regulator, door or fan standing in the branch; empty for an airway

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

Times are `YYYY-MM-DD HH:MM`. No survey point shares a time with a log entry. A package holds up to 2,000
branches, 1,600 log rows and 4,500 survey points.

The two packages in `examples` each carry one more file, `expected.csv`: the results to VS-4 for every survey
point, in the columns `point,flow_m3_s`. The package in `pending` is as its district sent it in: the eight
files, no results.
