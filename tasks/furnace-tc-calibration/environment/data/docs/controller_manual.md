# Furnace temperature controller: profile thermocouple corrections (excerpt)

Each zone is controlled in cascade: the profile thermocouple (inside the tube, beside the boat) sets the zone
temperature and the spike thermocouple (at the heater element) is the inner loop.

Corrected profile reading:

    corrected = raw + correction(T)

`correction(T)` is entered per zone at two points, 850 C and 1050 C. Between them the controller interpolates
linearly; below 850 C it uses the 850 C value and above 1050 C the 1050 C value. The controller holds the
corrected reading at the setpoint.

Trends log the raw profile readings (`profile_raw_z1` ... `profile_raw_z5`, before correction) and the spike
readings (`spike_z1` ... `spike_z5`) every 15 minutes, with the controller state, the setpoint and the number of
product wafers in the boat (`boat_wafers`, of 150 slots; 0 with no load). The spike runs above the profile reading
by the heater-to-load difference, which grows with the heat the load absorbs: a boat run without fill dummies
shows a smaller difference than a full boat.

States: `process` (recipe hold), `ramp`, `standby` (600 C soak, boat in, nitrogen purge, no load), `hold`
(operator hold at the current setpoint, boat in, door closed) and `boat_out` (750 C with the door open between
loads). With the boat in, the door closed and nitrogen flowing, a 600 C soak is isothermal along each zone,
whichever state it is logged under; a door-open or process state is not.
