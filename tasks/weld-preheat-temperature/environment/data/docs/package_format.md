# Joint package format

Each joint's package holds:
- `joint_sheet.md`: the joint (number, type, length, station and arc monitor, date), its two plates (mark, grade, heat,
  thickness) and the welding procedure: for the root, fill and capping runs, the process, the consumable (designation
  and batch) and the nominal current, voltage and travel speed. A process may be marked `pulsed`.
- `mill_certificates.md`: the inspection certificates of the plate heats in the shop's stock for the job: for each
  heat, the grade, the plates of the heat, the cast analysis and the CEV; for some plates, a product analysis of the
  plate itself, `Product analysis of plate <mark>`.
- `consumables.md`: the inspection certificates of the consumable batches for the job, with the diffusible hydrogen.
- `monitor_runs.csv`: the station's arc monitor's record of each run it recorded that day: `joint`, `run` (numbered
  within the joint), `kind` (`root`, `fill` or `cap`), `start` (date and time), `process`, `arc_time_s`, `length_mm`,
  `mean_current_a`, `mean_voltage_v` (at the monitor's voltage sensing point), and `waveform`, the file of the run's
  waveform record when one was taken.
- `waveforms/`: waveform records, `t_ms`, `current_a`, `voltage_v`, sampled at 10 kHz.
- `electrode_log.csv`: the electrode oven log of the shop: `time`, `station`, `batch`, `event` (`issued to heated
  quiver`, `issued to unheated quiver`, `returned to oven`).
- `climate_log.csv`: the shop air, hourly, from the climate loggers of the shop's bays: `time`, `logger`, `temp_c`,
  `rh_pct`.
- `shop_log.csv`: the shop's work log: `time`, `station`, `entry`. Besides routine entries (fit-up, inspection,
  gas, grinding discs), entries use the shop's standard texts:
  - `<joint>: plate <mark> (heat <heat>) rejected at UT for a lamination; replaced by plate <mark>, heat <heat>,
    <thickness> mm.`
  - `Arc monitor <monitor> checked against the reference shunt: current reading <x> percent high; recalibrated
    (last check <date>).` (or `low`)
  - `Wire spool changed: batch <batch> used up, <designation> batch <batch> fitted.`
