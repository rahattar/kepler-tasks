Perfect-silicon wafers need the crystal's growth rate at the interface to follow the V/G program of recipe PS-R07 closely. Puller 11 has so far grown only fast-pull bodies, and its supervisory program for PS-R07 still has to be written. Everything known about the puller is in `/app/data/`, including minute logs and caliper profiles of eight bodies.

Write the program as `/app/supervisor.py`, following `/app/data/docs/supervisor_interface.md`: a class `Supervisor` whose `update(meas)` is called once a minute and returns the pull-rate and heater-power setpoints. It will grow new bodies on PS-R07 that vary from one to the next about as much as the logged ones.

On each body, between 50 mm and 1500 mm of length, the growth rate averaged over every 5 mm stretch of crystal (a sliding 5 mm window) has to stay within +-1 % of the PS-R07 program, and the true diameter may not drop below the 301.0 mm grind minimum. Ground-away silicon has to stay small too: over all bodies together, the true diameter from 50 mm to 1500 mm averages no more than 303.0 mm. Each body has to reach 1500 mm.

The interface document lists the computing limits, and `/app/check_interface.py` tries a program against them on logged data.

You have 14400 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
