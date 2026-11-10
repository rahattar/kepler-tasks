# Plant standard ST-9: shrink-fitted hubs

Hubs are fitted to steel shafts by heating the hub in an oven and sliding it on; the joint carries the torque by
friction alone (no key).

1. Torque: at the least interference the tolerances allow, at rest and in steady running, the joint carries 1.5 times
   the peak torque without slipping.
2. Hub stress: at the greatest interference the tolerances allow, at rest and in steady running, the equivalent
   (von Mises) stress at the hub bore does not exceed the hub material's yield strength divided by 1.2.
3. Assembly: at the heating temperature the hub bore clears the shaft by at least 0.001 x the shaft diameter at the
   greatest interference, and the heating temperature does not exceed the hub's heating limit.

The interference that acts in the joint is the geometric interference less the smoothing of the surfaces on fitting,
0.8 x (Rz of the bore + Rz of the shaft).

The drawing specifies the mean diametral interference in whole micrometres. The shaft is ground to IT5 and the bore
to IT6 about it, so the interference lies within the mean -/+ (IT5 + IT6) / 2:

| Diameter (mm) | IT5 (um) | IT6 (um) |
|---|---|---|
| up to 50 | 11 | 16 |
| up to 80 | 13 | 19 |
| up to 120 | 15 | 22 |
| up to 180 | 18 | 25 |
| up to 250 | 20 | 29 |

Records: `joint_register.csv`, `hub_certificates.csv`, `assembly_sheets.csv` (surface finish and preparation),
`duty.csv` (peak torques), `thermography.csv` (hub and shaft temperatures in steady running), `materials.csv`,
`maintenance_log.csv`.
