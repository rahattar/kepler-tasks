# Press hydraulic power units: records for the pump-retrofit study

The plant is studying whether to replace the fixed-displacement pumps of its press hydraulic power units with
variable-speed drives. For each press, the unit was logged through a run of cycles, and the log is reduced by HP-2.

## Power unit

Each unit is a fixed-displacement axial piston pump driven directly by an induction motor, an unloading valve, a
check valve and a bladder accumulator on the system line that feeds the press. The pump charges the accumulator
until the system pressure reaches the unloading valve's upper setting; the pump then unloads to tank (its outlet
pressure falls to a few bar) while the check valve holds the accumulator; it reloads when the system pressure falls
to the lower setting. The press takes its oil from the system line through its own valve block.

## Package

Each press's package holds:

- `unit.json`: the pump (displacement, efficiency table against outlet pressure), the motor (rating, synchronous
  and rated speeds, efficiency, unloaded input power), the accumulator (volume, precharge pressure at the last
  check, gas at ambient temperature) and the logger.
- `log.csv`: columns `time_s`, `system_pressure_bar` (gauge, on the accumulator line), `pump_pressure_bar` (gauge,
  at the pump outlet, before the check valve) and `motor_power_kw` (three-phase input power), 20 samples per
  second, over about ten press cycles.
- In the example package only, `results.json` with the results the plant's engineer reported (HP-2 keys).

The logger's pressure channels come from the units' pressure transmitters; the power channel comes from a
three-phase power analyser on the motor supply.
