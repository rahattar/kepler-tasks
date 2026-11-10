# Cooler bank DCS instruments: service notes

- Cooling-water flow: magnetic flowmeters, one per unit, calibrated each outage; +-0.5 %.
- Glycol flow: magnetic flowmeters on each unit's glycol branch; +-0.5 %.
- Temperatures: RTDs in thermowells at the cooling-water inlet and the glycol inlet and outlet of each unit. The
  cooling water from all units leaves into one common return header, so there is no per-unit water-outlet
  transmitter. The glycol-outlet RTDs sit in deep wells in a dead zone of the outlet nozzle and read off the
  true outlet temperature by up to about 2 K, high or low, differently on each unit; the offset is steady. The
  other two stay within 0.1 K.
- Tube-side differential pressure: one transmitter per unit across the water box nozzles; +-1 %.
- Standby: when a unit is not needed, its cooling-water valves are shut and glycol keeps circulating through the
  shell. With no water flowing nothing is removed, and the glycol leaves at the temperature it entered; the trend
  logs these hours as `standby`. E8 cools the reactor jacket glycol and runs continuously.
- Trends: hourly averages, 2026-08-24 00:00 to 2026-10-11 23:00, one file per unit.
