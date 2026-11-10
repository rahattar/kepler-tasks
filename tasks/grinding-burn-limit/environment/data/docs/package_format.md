# Job package format

Each job's package holds:
- `job_sheet.md`: the machine, the wheel (specification, size when new), the part (material, lot and the ground
  face, as `ground width W mm` or as `ground face W mm wide: two lands of L mm each side of a G mm relief groove`),
  the programmed work speed, the coolant and its temperature, and the dressing interval of the operation (as
  `dressing interval V mm3/mm` or as `dressing every N parts (stock S mm over a L mm long face)`);
- `heat_treatment.md`: the heat treatment certificates of the part lots on the job;
- `machine_log.csv`: work on the machine: `date`, `work_order`, `description` (wheel changes, dressing with the
  wheel diameter after it, coolant and chiller work, spindle and table work);
- `power_log.csv`: the machine's spindle power records: `date`, `pass` (`air` with the wheel running and not in
  contact, or `grind`), `width_mm`, `depth_um`, `work_speed_mm_s`, `volume_since_dressing_mm3_mm`, `spindle_power_w`.
