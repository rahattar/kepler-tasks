# Pike Hollow Wind - site description

Verification period 2026-01-01 00:00 to 2026-06-30 23:50 local standard time (UTC-6; the farm's controllers and loggers do not change for daylight saving).

Ground elevation at M1 760 m above sea level; the site is flat to within 15 m. Hub height 90 m.

## Turbines

| turbine | east of M1 (m) | north of M1 (m) | model | rotor diameter (m) | north offset (deg) |
|---|---|---|---|---|---|
| T01 | 205 | 205 | HW116-2.5 | 116 | 0.0 |
| T02 | 471 | -175 | HW116-2.5 | 116 | 0.0 |
| T03 | 737 | -555 | HW116-2.5 | 116 | 0.0 |
| T04 | 1003 | -935 | HW116-2.5 | 116 | 0.0 |
| T05 | 1270 | -1315 | HW116-2.5 | 116 | 0.0 |
| T06 | 1003 | 481 | HW116-2.5 | 116 | 0.0 |
| T07 | 1269 | 101 | HW120-2.5 | 120 | 0.0 |
| T08 | 1536 | -279 | HW120-2.5 | 120 | 0.0 |
| T09 | 1802 | -659 | HW120-2.5 | 120 | 0.0 |
| T10 | 2068 | -1040 | HW120-2.5 | 120 | 0.0 |

North offsets are added to the yaw position to give the wind direction; they were checked against M1 at the last annual service and all set to zero.

Ice detectors: T01, T02, T03.

## Met mast M1

Lattice mast 2.5 rotor diameters upwind of T01 in the prevailing direction. Hub-height cup anemometer (Thies First Class), calibration certificate DWG-25-1187 (MEASNET): wind speed = 0.04580 m/s per Hz x frequency + 0.2310 m/s. Hub-height vane, temperature and humidity; barometer 2 m above ground.

## Nacelle transfer function

Calibration turbine T01, calibration sector 190 to 260 degrees (M1 wind direction). NTF from the commissioning campaign (controller software 3.x):

| nacelle wind speed (m/s) | free-stream wind speed (m/s) |
|---|---|
| 2.0 | 2.41 |
| 3.0 | 3.49 |
| 4.0 | 4.57 |
| 5.0 | 5.65 |
| 6.0 | 6.73 |
| 7.0 | 7.81 |
| 8.0 | 8.89 |
| 9.0 | 9.97 |
| 10.0 | 11.05 |
| 11.0 | 12.13 |
| 12.0 | 13.21 |
| 13.0 | 14.29 |
| 14.0 | 15.37 |
| 15.0 | 16.45 |
| 16.0 | 17.53 |
| 17.0 | 18.61 |
| 18.0 | 19.69 |
| 19.0 | 20.77 |
| 20.0 | 21.85 |
| 21.0 | 22.93 |
| 22.0 | 24.01 |

Linear interpolation between rows.
