# Tallow Creek Wind - site description

Verification period 2026-01-01 00:00 to 2026-06-30 23:50 local standard time (UTC-6; the farm's controllers and loggers do not change for daylight saving).

Ground elevation at M1 910 m above sea level; the site is flat to within 15 m. Hub height 80 m.

## Turbines

| turbine | east of M1 (m) | north of M1 (m) | model | rotor diameter (m) | north offset (deg) |
|---|---|---|---|---|---|
| T01 | 182 | 182 | HW103-2.0 | 103 | 0.0 |
| T02 | 398 | -193 | HW103-2.0 | 103 | 0.0 |
| T03 | 615 | -567 | HW103-2.0 | 103 | 0.0 |
| T04 | 831 | -942 | HW103-2.0 | 103 | 0.0 |
| T05 | 1047 | -1316 | HW103-2.0 | 103 | 0.0 |
| T06 | 1264 | -1691 | HW103-2.0 | 103 | 0.0 |
| T07 | 1480 | -2066 | HW103-2.0 | 103 | 0.0 |
| T08 | 1696 | -2440 | HW103-2.0 | 103 | 0.0 |
| T09 | 1912 | -2815 | HW103-2.0 | 103 | 0.0 |

Controller software 4.2.1 has run on all turbines since 2025-12-10 (OEM service bulletin SB-2026-03).

North offsets are added to the yaw position to give the wind direction; they were checked against M1 at the last annual service and all set to zero.

Ice detectors: none.

## Met mast M1

Lattice mast 2.5 rotor diameters upwind of T01 in the prevailing direction. Hub-height cup anemometer (Thies First Class), calibration certificate DWG-25-1187 (MEASNET): wind speed = 0.04580 m/s per Hz x frequency + 0.2310 m/s. Hub-height vane, temperature and humidity; barometer 2 m above ground.

## Nacelle transfer function

Calibration turbine T01, calibration sector 190 to 260 degrees (M1 wind direction). NTF from the commissioning campaign (controller software 3.x):

| nacelle wind speed (m/s) | free-stream wind speed (m/s) |
|---|---|
| 2.0 | 2.43 |
| 3.0 | 3.49 |
| 4.0 | 4.56 |
| 5.0 | 5.62 |
| 6.0 | 6.69 |
| 7.0 | 7.75 |
| 8.0 | 8.82 |
| 9.0 | 9.88 |
| 10.0 | 10.95 |
| 11.0 | 12.02 |
| 12.0 | 13.08 |
| 13.0 | 14.14 |
| 14.0 | 15.21 |
| 15.0 | 16.27 |
| 16.0 | 17.34 |
| 17.0 | 18.41 |
| 18.0 | 19.47 |
| 19.0 | 20.54 |
| 20.0 | 21.60 |
| 21.0 | 22.66 |
| 22.0 | 23.73 |

Linear interpolation between rows.
