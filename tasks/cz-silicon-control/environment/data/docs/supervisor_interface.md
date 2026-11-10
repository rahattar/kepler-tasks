# Puller 11 supervisory computer: program interface

The supervisory program is one Python file, `supervisor.py`, with a class `Supervisor`. Every body is run in a new
Python process: `Supervisor()` is created without arguments at the end of the crown (length 0), then
`update(meas)` is called once per minute until the crystal is 1500 mm long. Each call returns a pair
`(pull_rate, heater_power)`: the pull-rate setpoint in mm/min and the heater-power setpoint in kW for the coming
minute. A tuple, a list or a length-2 numpy array is accepted; both values must be finite numbers. An exception, a
reply in another form, a non-finite value or a call over its time limit stops the body. The drives clip them to their limits and move toward them no faster than
their slew limits (design sheet). Crucible rotation is set by PS-R07 and is not under the program's control.

`meas` holds the same quantities as the minute logs:

| key | meaning |
|---|---|
| time_min | minutes since the end of the crown |
| length_mm | crystal body length |
| camera_diameter_mm | bright-ring camera reading |
| pull_rate_mm_min | actual pull rate |
| heater_power_kw | actual heater power |
| pyrometer_c | melt-surface pyrometer |
| crucible_rpm_set | PS-R07 crucible-rotation setpoint |

Start of a body: true diameter about 304 mm, heater power steady for more than an hour, growth rate on the PS-R07
program.

The computer gives the program numpy and scipy (Python 3), one core and no network, and starts it in an empty
directory: it has no other files. Limits: 120 s to create `Supervisor()`, 5 s per `update` call, 600 s of program
time per body including creation; 4 GB of address space and 64 processes.

Growth-rate averages for the V/G window are taken over every 5 mm stretch of crystal, a 5 mm window moved along the
body in 1 mm steps (from 50 mm to the end of the body).
