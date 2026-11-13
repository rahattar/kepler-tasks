# The records

All dates and times are local standard time; the site's clocks and the utility's are not put forward in summer.
Pressures are in psi and flows in gpm.

## riser_register.csv

One row for each riser.

- `riser`, `building`
- `lead_in_material`, `lead_in_size_in`: as the pipe table of the site data
- `lead_in_equiv_length_ft`: the equivalent length L of FP-12 clause 3.3
- `laid`: the year the lead-in was laid
- `lead_in_check`: the model of the lead-in's check valve, empty where it has none
- `wall_hydrant`, `wall_hydrant_at_equiv_ft`: the wall hydrant on the lead-in, if it has one, and the equivalent
  length of lead-in from the yard main to the hydrant's tee
- `valve_supervision`: `switch` for a control valve with a supervisory switch, `lock` for one chained and locked
- `main_drain`: the drain valve's pattern
- `supply_gauge_serial`, `supply_gauge_height_ft`: the gauge on the riser and its height above the site datum
- `placard_flow_gpm`, `placard_pressure_psi`: the riser's hydraulic placard, at the base of the riser

## main_drain_log.csv

The monthly round. The tester goes from riser to riser, and at each one reads the supply gauge, opens the main
drain fully, reads the gauge again once it is steady, and closes the drain. The order of the round changes from
month to month.

- `riser`, `date`, `time`: the riser and when its residual was read
- `gauge_serial`: the serial of the gauge read
- `static_psi`: the supply gauge before the drain was opened
- `residual_psi`: the supply gauge with the drain fully open

## utility_pressure.csv

The utility's record of transmitter PT-0, one reading every 30 minutes.

- `timestamp`, `pressure_psi`

## utility_flow_tests.csv

The utility's flow tests of the city main. The pressures are read at the residual hydrant, first with no hydrant
flowing and then with the flow hydrant's outlets discharging.

- `date`, `time`
- `residual_hydrant`, `flow_hydrant`
- `outlets_flowing`: the number of outlets of the flow hydrant that were open
- `static_psi`, `residual_psi`: at the residual hydrant
- `pitot_psi`: the pitot pressure in the stream of each open outlet

## yard_flow_tests.csv

The site's yearly flow tests of its own hydrants: a hydrant is flowed, and the pressures are read on the supply
gauge of a riser that is not flowing. For a wall hydrant the gauge read is that of the riser whose lead-in the
hydrant stands on.

- `date`, `time`
- `flow_hydrant`, `outlets_flowing`, `pitot_psi`: as above
- `gauge_riser`: the riser whose supply gauge was read
- `static_psi`: that gauge before the hydrant was opened
- `residual_psi`: that gauge with the hydrant flowing

## maintenance_log.csv

- `date`, `item` (a riser, or `connection`), `work`

## gauge_certificates.md

One certificate for each gauge serial.
