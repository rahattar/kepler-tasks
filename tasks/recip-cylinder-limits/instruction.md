K-4101 is a six-throw, three-stage reciprocating gas booster. The field it takes suction from is declining, so the
suction pressure of every stage falls year by year, and the plant needs to know how far each cylinder can be taken
before it has to be re-wheeled or de-staged.

Work out, for each of the six cylinders 1A, 1B, 2A, 2B, 3A and 3B, the lowest suction pressure at which that
cylinder may be run, and which requirement of plant standard RC-4 governs it.

The standard is at `/app/data/docs/standard.md`. It gives the requirements, the figures each is checked against, and
what the lowest allowable suction pressure and its governing requirement mean. Follow it as written.

The machine is to be taken as it now stands, not as it was supplied. The records are in `/app/data`:

- `/app/data/docs/machine_data_sheet.md` - the machine as it was supplied
- `/app/data/docs/overhaul_register.md` - the register of work closed out
- `/app/data/docs/service_bulletin.md` - a service bulletin filed against the machine
- `/app/data/cylinder_schedule.csv` - the cylinders and their ratings
- `/app/data/liner_records.csv` - bore measurements
- `/app/data/operating_record.csv` - what each stage runs at
- `/app/data/instrument_schedule.csv` - the instruments and where they sit
- `/app/data/temperature_trend.csv` - monthly temperatures
- `/app/data/drive_record.csv` - the drive's record
- `/app/data/gas_analysis_feed.csv` - a gas analysis
- `/app/data/component_properties.csv` - component properties
- `/app/data/maintenance_log.csv` - the work orders

Two services can be called on, described in `/app/data/docs/laboratory.md`:

    gc <stage>
    weigh <cylinder>

The allowance is 2 readings in all, across both services together, and it does not refill. Each reading is reported
back and a copy is written to `/app/lab_reports`. Plan the allowance before you spend any of it.

Write your answer to `/app/output/cylinder_limits.csv`, with the header

    cylinder,suction_pressure_bar,governing_limit

and one row for each of 1A, 1B, 2A, 2B, 3A, 3B: the lowest suction pressure in bar absolute to two decimal places,
and the name of the governing requirement exactly as the standard writes it.

You have 28800 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
