# Strain loggers: settings and records

- Loggers DL-500, one per screen, quarter-bridge input, gauge factor setting 2.00 on every channel, output in
  microstrain, 500 samples per second. Spare in stores: DL-200 (same input, 200 samples per second).
- Steady records: 8 s, taken on a schedule while the screen runs; the record index carries the belt-scale feed
  rate at the time (0 when the screen runs empty).
- Event records: triggered by the drive's start and stop signals; a start record runs 10 s, a stop record 14 s.
- The record index (records/index.csv) lists every record with its screen, time, kind, feed and sample rate.
- Noise about 0.2 microstrain rms.
