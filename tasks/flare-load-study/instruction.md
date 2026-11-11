Unit 400 is a natural gas liquids recovery train. Its flare system has not been restudied since the unit's capacity increase in 2024, and a load study to the current issue of the plant standard is now due. The contingencies to be studied are the ones RP-7 names.

For each contingency, establish which of the unit's relief devices discharge at the same time, the total mass flow they put into the flare header, and the pressure that flow raises at the header's inlet. Plant standard RP-7 in `/app/data/docs/standard.md` governs the study.

The records are `/app/data/relief_valve_register.csv`, `/app/data/valve_history.csv`, `/app/data/fire_zones.csv`, `/app/data/flare_tie_ins.csv`, `/app/data/drive_schedule.csv`, `/app/data/control_valve_data.csv`, `/app/data/control_valve_trend.csv`, `/app/data/operating_record.csv`, `/app/data/instrument_schedule.csv`, `/app/data/sis_register.csv`, `/app/data/exchanger_data.csv`, `/app/data/pump_data.csv`, `/app/data/pump_test_record.csv`, `/app/data/gas_analysis.csv`, `/app/data/component_properties.csv`, `/app/data/fluid_properties.csv`, `/app/data/gas_properties.csv`, `/app/data/liquid_properties.csv`, `/app/data/modification_register.csv` and `/app/data/maintenance_log.csv`. The unit is described in `/app/data/docs/unit_400.md`, its vessels in `/app/data/docs/vessel_data.md`, the flare header and stack tip in `/app/data/docs/flare_system.md`, and the load study of 2019 in `/app/data/docs/flare_load_study_2019.md`.

The unit's test crew is on site for one shift and will run field tests for you. What it will run, and how to place the booking, are in `/app/data/docs/field_testing.md`. The booking is two tests, and the crew takes both names in a single order and will take no other, so each test has to be chosen on what the records already tell you rather than on the result of the other. The crew writes a report for each test to `/app/field_reports`.

RP-7 also asks for the stack tip to be re-rated where the tip as installed leaves a device standing against too much built-up back pressure. Carry out that duty as well, on the bores the flare system note says the vendor supplies.

Write the study to `/app/output/flare_load.csv` with the header `contingency,devices,load_kg_per_h,header_inlet_barg`. Include one row for each contingency RP-7 names. Give the devices as their tags separated by semicolons, the load in kg/h and the header inlet pressure in barg, each to at least three significant figures, except that a pressure too small to matter may be given as 0. Report the load study for the tip as installed.

Write the re-rating to `/app/output/tip_sizing.csv` with the header `tip_bore_mm,binding_device,back_pressure_pct` and one row: the bore the duty calls for in mm, the tag of the conventional device left standing against the largest share of its own set pressure at that bore, and that share as a percentage of set pressure to at least three significant figures.

Commit to one set of devices and one figure for each contingency, and to one bore.

You have 28800 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
