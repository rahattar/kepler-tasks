# Puller 11 - operations notes since the HZ-B install

- 2026-08-18: HZ-B installed. Re-qualified on the fast-pull product, recipe FP-R31 (recipes/fast_pull_r31.csv).
- Bodies B2411-B2418 were grown on HZ-B with FP-R31 under the standard fast-pull loops:
  - pull rate: PI on the camera diameter, setpoint 304.0 mm;
  - heater: slow PI that brings the 30 min average of the pull rate onto the recipe's growth-rate program.
  Each body has a minute log (logs/B24xx_minute.csv) and a post-growth caliper profile every 10 mm
  (logs/B24xx_caliper.csv, +-0.05 mm).
- B2415: approved heater response test. At 700 mm the heater loop was put in manual. The heater was held 2.5 kW
  above its value at that moment for 150 min, then returned to automatic (bumpless). The pull-rate loop stayed in
  automatic throughout.
- Minute log columns:
  - time_min, length_mm;
  - camera_diameter_mm (bright ring);
  - pull_rate_mm_min, heater_power_kw (actual values);
  - pyrometer_c (melt surface);
  - crucible_rpm_set (recipe setpoint; the drive follows within a minute).
- Each body starts at the end of the crown (length 0). Diameter is about 304 mm, the heater is steady, and the
  growth rate is on the program.
- Next: Puller 11 moves to perfect silicon, recipe PS-R07 (recipes/perfect_si_r07.csv). PS-R07 has a lower growth
  rate program and larger crucible-rotation steps (oxygen specification).
