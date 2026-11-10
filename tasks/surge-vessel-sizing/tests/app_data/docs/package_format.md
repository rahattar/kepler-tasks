# Main package format

Each main's package holds:
- `system_description.md`: the pump station, the rising main (pipe, wave speed, design friction, longitudinal
  profile from the drawings), its chambers and transmitters, and the receiving reservoir;
- `pump_datasheets.md`: the new pump sets;
- `scada.csv`: 15-minute SCADA values for a month with the existing pumps: number of pumps running, FT201 flow
  (L/s), PT201 (pump station header) and the chamber transmitter's gauge pressures (bar), LT501 reservoir level
  (m AOD);
- `records/maintenance_log.csv`: work on the pump station and the main during the month.
