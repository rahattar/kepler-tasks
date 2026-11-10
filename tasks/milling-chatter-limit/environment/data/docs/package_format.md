# Job package format

Each job's package holds:
- `setup_sheet.md`: the machine, the tool assembly (tool, teeth, holder, stickout), the material and the operation
  (milling direction, feed axis, radial depth of cut in mm or as a stepover percentage of the tool diameter,
  programmed spindle speed);
- `tap_tests/`: the tap test files of tool assemblies on the job's machine, one file per test and axis. Each file
  starts with `#` lines giving the machine, the assembly, its stickout, the date, the axis, where the hammer and the
  accelerometer were, the accelerometer's mass and whether the data are corrected for it, and the quantity measured
  (receptance in m/N, mobility in (m/s)/N or accelerance in (m/s^2)/N), then the columns `freq_hz`, `real`, `imag`
  and `coherence`;
- `machine_log.csv`: work on the machine: `date`, `work_order`, `description`.
