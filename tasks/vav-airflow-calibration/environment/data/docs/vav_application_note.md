# Series 3100 pressure-independent terminals: application note AN-31-04

## Flow sensor and K-factor

The inlet carries a multi-point averaging cross. Its differential pressure is the velocity pressure (VP) times the
sensor's amplification. The controller reports flow as K x sqrt(VP), with K in cfm per sqrt(in. w.c.).

| inlet (in) | K (cfm per sqrt(in. w.c.)) | max flow at 2000 fpm (cfm) |
|---|---|---|
| 6 | 478 | 390 |
| 8 | 850 | 700 |
| 10 | 1328 | 1090 |
| 12 | 1912 | 1570 |
| 14 | 2603 | 2140 |

Published K-factors are measured in the laboratory with a straight inlet duct at least three inlet diameters
long. Hard elbows, flex connectors and transitions closer to the inlet than that change the velocity profile
across the cross and with it the sensor's amplification. On sound installations field results range from a few
percent to about 25 percent; the sign and size depend on the fitting and on its orientation relative to the
cross. A flex connector that is bent, sagging or compressed at the inlet is the worst case and can exceed that.
Field calibration at both minimum and maximum airflow is required on every installation.

## Transducer

0 to 1.5 in. w.c. differential transducer. Zero drift up to 0.03 in. w.c. per year. Controllers with firmware 3.x
zero the transducer automatically every hour; firmware 2.4 controllers have no auto-zero.
