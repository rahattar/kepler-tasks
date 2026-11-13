# Line package

One directory a line. Text files, comma separated, a header row, decimal points.

## line.json

- `line`: name of the line
- `step_s`: the step of the feed log, s
- `interval_steps`: the number of log steps in an interval of the results
- `flights`: the flights in the order the load passes through them

## flights.csv

- `flight`: name of the flight
- `belt_kg_m`: mass of the belt, kg per metre of belt
- `idlers_carry_kg_m`, `idlers_return_kg_m`: rotating mass of the carrying and of the return idlers, kg per
  metre of flight
- `secondary_factor`: the factor C of BC-3 section 3
- `belt_stiffness_MN`: the belt stiffness K of BC-3 section 4, MN
- `take_up_tension_kN`: the belt tension T_t the take-up holds, kN

## profile.csv

The profile of each flight from tail to head: `flight`, `section` (counted from the tail), `length_m`,
`rise_m`.

## drives.csv

The drive register: one row a drive.

- `flight`, `drive`: the flight and the place of the drive on it (`head1`, `head2` or `tail`)
- `rated_kW`: rated power of the motor
- `gear_ratio`: ratio of the gearbox, input speed over pulley speed
- `pulley_diameter_mm`: diameter of the drive pulley over its lagging, measured when the pulley was lagged
- `efficiency`: the efficiency e of BC-3 section 4

## surveys.csv

The survey campaigns on record, one row a drive in each campaign.

- `campaign`: number of the campaign; a campaign covers the whole line at one steady feed
- `flight`, `feed_t_h`: the flight and the feed during the campaign, t/h
- `belt_speed_m_s`: belt speed of the flight from the weigher's speed wheel, m/s
- `drive`, `input_rpm`, `motor_kW`: the drive, the speed of its gearbox input shaft by hand tachometer, rpm, and
  its motor power, kW

## feed.csv

The feed log: `step` (from 0) and `feed_t_h`, the feed onto the first flight, t/h.

## expected.csv

Only in a package that comes with its results: the results to BC-3 section 7.

- `row`: flight, drive and interval joined by hyphens, the interval counted from 001
- `mean_kW`, `max_kW`, `min_kW`, `traction_peak`
