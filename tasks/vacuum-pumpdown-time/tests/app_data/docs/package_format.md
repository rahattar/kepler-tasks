# Chamber package format

Each chamber's package holds:
- `chamber_sheet.md`: the chamber as issued: its volume, roughing pump, roughing line (bore and length), turbo pump,
  high-vacuum port conductance, the controller's crossover pressure and the chamber's gauges.
- `job_sheet.md`: the job: its date, its load (items, material and area) and its process pressure.
- `equipment_log.csv`: the chamber's equipment log: `date`, `entry`. Besides routine entries, entries use the shop's
  standard texts:
  - `Turbo pump sent for service; exchange unit fitted.`
  - `Roughing line rerouted: <bore> mm bore, <length> m long.`
  - `Spool piece fitted between the chamber and the gate valve: <bore> mm bore, <length> mm long, stainless steel,
    as machined.`
  - `Internals rebuilt: <what>; chamber volume now <volume> L.`
  - `Door seal replaced.`
  - `Load lock merged into the chamber: inner door removed.`
- `gauge_certificates.md`: the calibration certificates of the shop's gauges: serial number, date and calibration
  factor.
- `pumpdown_records/`: the chamber's past pump-down records, one file each. The header lines (`#`) give the date, the
  vent (gas and time open), the load in the chamber (or `empty`), the gauges by serial number, and the pumps and the
  crossover pressure. The columns are `time_s` from the start of roughing, `stage` (`rough` or `high`), and
  the indicated pressures `pirani_mbar` and `cold_cathode_mbar` (blank when the gauge is off or out of range).
