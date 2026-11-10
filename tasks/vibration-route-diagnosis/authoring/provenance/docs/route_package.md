# Route packages

The plant's vibration routes are collected monthly with a portable two-channel data collector and ICP
accelerometers on magnetic bases. Each route visit is exported as one directory, a route package. The line
frequency is 60 Hz.

## Files

- route.json: the route name and date and one entry per capture: machine, point, capture, direction, sample rate,
  number of samples, scale (g per count) and file. The route file holds the set-up the route planned for each
  capture; the collector stores what it acquired and does not check it.
- <machine>_<point>.npz (machine and point in lower case): one int16 array per capture, named as in route.json.
  Multiply by g_per_count for g.
- <machine>_tach.csv (lower case): optical tach pulse times in seconds from the start of that machine's first low capture,
  for machines with tach = yes in the register. The tach reads reflective tape on the coupling.
- register.csv: the machine register (kind, location, motor poles, nameplate speed, drive, impeller vanes, fan
  blades, compressor lobes, bearings at the motor and at the driven machine, gearbox tooth counts, sheaves and belt,
  points, tach).
- bearing_data.csv: rolling-element bearing geometry for the bearing designations the plant stocks.
- maintenance_log.csv: work orders on the route's machines. Every entry is dated before the survey date, so the work it records was done before the measurements were taken.
- process_snapshot.csv: pump flows and NPSH at the time of the survey.
- <machine>_impact_test.csv (lower case): impact (bump) test of a vertical pump's motor top, machine stopped: relative response
  in the two radial directions.

## Points and captures

- MOT: motor drive-end bearing housing. PMP, FAN, CMP: the driven machine's bearing housing nearest the coupling
  or sheave. GBX: gearbox input bearing housing. A vertical turbine pump has one point, MOT, at the motor top
  bearing, measured in two radial directions (x and y).
- low_r and low_a (low_x and low_y on a vertical pump): 16 s at 2560 Hz, radial horizontal and axial.
- high_r (high_x on a vertical pump): 1 s at 25600 Hz, radial horizontal, for rolling-element bearing and gear
  defects.
- Each machine runs steadily while it is measured. Belt-driven fans on a VFD run at whatever speed their control
  loop sets; the speed is not noted.

## Example

examples/u2-2026-10-20 is route U-2 of 2026-10-20 with the analyst's report, diagnosis_report.csv.
