# The audit records

Every file below is in `/app/data`. All of them were written before the audit date, 2026-11-02.

## chamber_register.csv

One row per chamber, as the register was issued: `chamber`, `volume_l`, `turbo`, `c_port_l_s` (the high-vacuum port
conductance as built), `seal_material`, `seal_length_cm`, `surface_area_m2` and `surface` (the chamber's internal
surfaces; a chamber with more than one surface has more than one row), and `p_spec_mbar`, its specified base
pressure.

## base_pressure_log.csv

The pressure reached at the end of each of the chamber's recent pumpdowns. One row per gauge read, so a pumpdown on
which two gauges were read has two rows with the same `pumpdown`: `date`, `chamber`, `pumpdown`, `vent_gas`,
`pumpdown_h` (hours from the start of roughing to the reading), `wall_temp_c`, `gauge`, `reading_mbar`, `load` (the
fixture in the chamber during that pumpdown, blank if none) and `note`.

## speed_tests.csv

The throughput tests by which the shop measures a chamber's effective pumping speed: a known flow of dry nitrogen is
admitted through a calibrated leak and the pressure rise is read. A test is run on the empty chamber at the end of
a pumpdown after an air vent. `date`, `chamber`, `pumping_time_h` (from the start of roughing to the test),
`wall_temp_c`, `flow_mbarl_s`, `p_with_flow_mbar`, `p_without_flow_mbar` (the chamber's own base pressure, read on
the gauge before the flow is admitted), `gauge`, `s_eff_l_s` (the speed the contractor reported, the flow divided by
the pressure rise).

Each `reading_mbar` repeats to 0.6 per cent (one standard deviation) between pumpdowns at the same condition, and
each pressure of a speed test to 0.5 per cent.

## turbo_controller.csv

What each chamber's turbo controller reported at the weekly check: `date`, `chamber`, `rotor_hz`,
`drive_power_w`, `bearing_temp_c`.

## maintenance_log.csv

The chamber maintenance log: `date`, `chamber`, `entry`.

## shop_climate.csv

The shop's daily air temperature and relative humidity: `date`, `air_temp_c`, `relative_humidity_pct`.

## docs/

`ms_bp_audit.md` is the standard, `vacuum_data.md` the shop's vacuum data, `audit_note.md` the engineer's note from
the previous audit, `vacwork.md` the audit test order, and this file.

## example/

The records of chamber VC00, a chamber of the same shop audited in an earlier quarter, in the same format, so
that the format and the units are plain, with `about_this_chamber.md` describing them. MS-BP defines what the
audit reports, so no audited result is given for it.
