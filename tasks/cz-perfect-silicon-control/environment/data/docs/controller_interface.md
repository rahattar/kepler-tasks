# Puller 11 supervisory controller interface

The supervisory computer takes one self-contained Python file, `controller.py`, defining a class `Controller`.
For each body it starts a fresh Python process, constructs `Controller()` (no arguments), and calls `step(obs)`
once a minute, from the end of the crown (length 0) until the body reaches 1500 mm.

`obs` is a dict with the minute-log quantities at that minute:

| key | unit |
|---|---|
| time_min | min since the end of the crown |
| length_mm | body length |
| camera_diameter_mm | bright-ring camera |
| pull_rate_mm_min | actual pull rate |
| heater_power_kw | actual heater power |
| pyrometer_c | melt-surface pyrometer |
| crucible_rpm_set | recipe crucible-rotation setpoint (PS-R07) |

`step` returns `{"pull_rate_mm_min": x, "heater_power_kw": y}`, the setpoints for the next minute (finite numbers).
Setpoints are clipped to the drive limits, and the drives follow at their slew limits (design sheet). The crucible
rotation follows PS-R07 and cannot be changed.

At length 0 the true diameter is about 304 mm, the heater has been steady for over an hour, and the growth rate is on
the PS-R07 program.

Runtime: the file runs alone in an empty directory, with Python 3, numpy and scipy, one CPU core and no network. It
cannot read any other file. The constructor has 120 s, each `step` call has 5 s, and the controller's total time on
one body (constructor included) is limited to 600 s.
