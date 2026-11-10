# Audit package format

Each audit is stored as a folder with these files.

## site.json

- `site`: site name.
- `atmospheric_pressure_bar_a`: atmospheric pressure, bar(a).
- `storage_volume_m3`: the volume of the receiver and the distribution piping that the pressure logger reads.
- `pressure_drop_receiver_to_compressors_bar`: the pressure drop from the receiver back to the compressors'
  discharge, across the dryer and filters.
- `pressure_logger`: path of the receiver pressure log.
- `non_production_hours`: the hours of each day, `[from, to)` in local time, when production is stopped.
- `compressors`: one entry per compressor, with these fields:
  - `tag`;
  - `control`: `load/unload` or `variable speed`;
  - `logger`: path of its power log;
  - `performance` (load/unload): free air delivery and full-load power against discharge pressure;
  - `performance_at_set_point` (variable speed): power against free air delivery.

## loggers/

- `power_<tag>.csv` (`time`, `kw`): a three-phase power analyser on the compressor's supply. Each row is the mean
  electrical power over the 10 seconds ending at `time`.
- `pressure.csv` (`time`, `bar_g`): the receiver pressure at `time`, every 10 seconds.

Each logger stamps its readings with its own clock. The power analysers are synchronised to the plant's clock, which is local time.

## Example

`examples/s-201/` is a past audit. `audit_result.json` in it holds the results the plant's energy engineer
reported.
