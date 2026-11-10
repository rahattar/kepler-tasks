# TC-wafer run: procedure and accuracy

An instrumented run uses a full boat with three thermocouple wafers per zone. Corrections are disabled for the
run: the controller holds the raw profile reading of every zone on the step setpoint. A run can include any of
three steps, each held until stable: 600 C soak (nitrogen, isothermal), 850 C and 1050 C. The report gives, per
zone and step, the raw profile reading, the spike reading and the mean of the zone's thermocouple wafers.

Thermocouple-wafer accuracy: +-0.2 K (certificate). Each step keeps a furnace out of production for most of a
shift; this calibration has three steps in total across the bay. The runs are made on 2026-10-12, the morning
after the trend export, and the new corrections are loaded as soon as the runs are reduced.
