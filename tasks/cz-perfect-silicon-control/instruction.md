Puller 11, fitted with hot zone HZ-B, is moving from fast pull to the perfect-silicon recipe PS-R07. A new supervisory controller will set the pull rate and heater power every minute as a 300 mm body grows. Everything known is in `/app/data/`, including minute logs and caliper profiles for eight HZ-B bodies.

Write `/app/controller.py` as one self-contained Python file defining `Controller`, with a no-argument constructor and `step(obs)`. The observation keys and starting conditions are described in `/app/data/docs/controller_interface.md`. Each call returns a dictionary of the form `{"pull_rate_mm_min": x, "heater_power_kw": y}`. The controller will run on new HZ-B bodies grown with PS-R07, with body-to-body variation comparable to the logged bodies.

Every body must reach 1500 mm. From 50 mm to 1500 mm on each body, the growth rate averaged over each 5 mm of crystal must stay within +-1 % of the PS-R07 growth-rate program, and the true diameter must never fall below 301.0 mm. Across all bodies, the true diameter averaged over 50 mm to 1500 mm must be at most 303.0 mm.

The file runs alone in an empty directory with Python 3, numpy and scipy and cannot read any other file. The constructor has 120 s and each `step` call has 5 s. Including construction, the controller's total computing time is limited to 600 s per body. `/app/check_controller.py` checks the interface and timing on logged data.

You have 14400 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
