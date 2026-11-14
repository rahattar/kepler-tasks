# Network packages

A package is a folder holding the records of one intermediate-pressure network: ten files.

## `network.json`
- `network`: the network's name
- `survey_allowance`: the number of items the field team will survey or prove for this package (see "The
  field team")

## `mains.csv`: the register of mains
`main,from_node,to_node,length_m,diameter_mm,material`: the main's name, the nodes it joins in its direction
(GD-3 section 2), its length, its internal diameter as it stands now and its material.

## `surveys.csv`: the survey campaigns on file
`date,main,p_from_barg,dp_bar,q_m3h`: the day of the campaign, the pressure at the main's `from` node, the
pressure at its `from` node less the pressure at its `to` node, and the flow in the main's direction. A
campaign surveys every main of the network over the hour from 13:00 on a cold weekday, with the network steady
through the hour, and the readings are the means over the hour. A survey reads the pressure within 1 mbar, the
pressure difference within 0.5 per cent of itself and the flow within 1 per cent of itself.

## `work_log.csv`: work on the mains
`date,main,work`, one row for each job. `RENEWED`: a new main was laid in place of the old one, and the
register describes the new main. `RELINED`: the main was lined in place, and the register gives its internal
diameter after lining. `LAID`: the main is new to the network. `INSPECTED`: it was inspected. `REPAIRED`: a
leak on it was repaired.

## `prs.csv`: the pressure-reducing stations
`prs,node,set_point_barg,capacity_m3h`

## `governors.csv`: the district governors
`governor,node`

## `design_day.csv`: the governors' design-day demand
`governor,hour,demand_m3h`: the governor's demand in the hour of the design day that starts at `hour`, 0 to 23
by the clock.

## `customers.csv`: the large customers
`customer,node,meter`: each large customer is supplied from its node through its own meter.

## `customer_meters.csv`: the customers' meter record
`time,meter,q_m3h`: the flow the meter registered in the hour starting at `time`, every hour of the record. A
customer's meter registers the gas through it within 1 per cent.

## `boundary_valves.csv`: the boundary valves
`valve,node,neighbour,neighbour_pressure_barg,state`: the valve, its node, the neighbouring network, the
neighbour's pressure at the valve (GD-3 section 6) and the valve's state, `open` or `closed`.

Every node of the network is named in `mains.csv`. A node carries at most one PRS, governor, customer or
boundary valve. Dates are `YYYY-MM-DD` and times `YYYY-MM-DD HH:MM`. Every survey and every job on file is
earlier than 2026-11-01. A package holds up to 700 mains.

## The field team
The field team surveys the network as it stands now, over the hour from 13:00 on a weekday of November 2026,
with the network steady through the hour. It takes one order for a package, of at most `survey_allowance`
items:

    gdsurvey PACKAGE_DIR ITEM [ITEM ...]

An item is a main, a boundary valve or a customer's meter. A main is read as in `surveys.csv`. At a boundary
valve the team reads the pressure on the network's side, the pressure on the neighbour's side and the flow
through the valve into the network, within the accuracies of `surveys.csv`. A meter is proved: the team gives
the gas the meter registers as a percentage of the gas through it, within 0.1 per cent.

The team prints one CSV block for each kind of item in the order, opened by its header row, with a row for
each item of that kind:

    main,p_from_barg,dp_bar,q_m3h
    valve,p_node_barg,p_neighbour_barg,q_m3h
    meter,registers_pct

A second order for the same package in the same run is refused. Where a program is written, the field team
answers for the two networks in `examples`; it has not been to the network in `pending`.

The two packages in `examples` each carry one more file, `expected.csv`: the results to GD-3 for every
governor, in the columns `governor,min_pressure_barg`. The package in `pending` is as its network sent it in:
the ten files, no results.
