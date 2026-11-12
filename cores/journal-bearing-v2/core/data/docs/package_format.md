# Bearing packages

A package is a folder holding the records of one bearing: four files.

## `datasheet.json`: the bearing as built
- `tag`, `machine`: the bearing's tag and its machine
- `position`: which of the machine's two bearings this is, `DE` (drive end) or `NDE` (non-drive end)
- `journal_diameter_mm`: journal diameter, 2R
- `length_mm`: bearing length, L
- `radial_clearance_um`: radial clearance, c
- `groove_angles_deg`: the angles theta of the axial oil grooves (LS-3 section 2), with the housing's split line
  horizontal. The grooves lie in the split line.
- `oil_grade`: the grade of the oil charge the machine's system was first filled with
- `oil_flow_L_min`: oil flow to the bearing, Q

## `history.csv`: the machine's maintenance history
One row for each job: `date,position,work,value,remarks`. `position` is `DE` or `NDE` for a job on one bearing
and `-` for a job on the machine as a whole.

| work | what was done | value |
|---|---|---|
| `SHELL_FITTED` | a new or re-metalled shell was fitted | diametral clearance measured at the fitting, mm |
| `JOURNAL_GROUND` | the journal was ground | journal diameter after grinding, mm |
| `SPLIT_SET` | the housing was rebuilt with its split line away from horizontal | angle of the split line from horizontal, degrees, positive in the direction of rotation |
| `OIL_CHANGED` | the oil charge of the machine's system was renewed | ISO VG grade of the new charge |
| `ORIFICE_CHANGED` | the bearing's supply orifice was changed | oil flow to the bearing after the change, L/min |
| `INSPECTED`, `ALIGNED`, `SEAL_REPLACED`, `PROBE_REPLACED` | routine work | none |

## `oil_samples.csv`: laboratory analyses of the oil
One row for each sample drawn from the machine's system: `date,nu40_cSt,nu100_cSt,rho15_kg_m3,remarks`, the
kinematic viscosity in mm2/s at 40 C and 100 C and the density at 15 C.

## `points.csv`: the operating points on record
One row for each point: `point,date,speed_rpm,load_N,load_angle_deg,inlet_a_C,inlet_b_C,drain_C`.
- `speed_rpm`: journal speed
- `load_N`, `load_angle_deg`: the load on the journal, W, and its angle, beta (LS-3 section 2)
- `inlet_a_C`, `inlet_b_C`: the readings of the two RTDs in the oil supply to the bearing
- `drain_C`: the reading of the RTD in the oil drain from the bearing

A reading the control system marked bad is recorded as -999. The control system marks only the failures it
detects.

Dates are year-month-day. No job, sample or operating point of a package shares a date with another kind of record.

The three packages in `examples` each carry a fifth file, `expected.csv`: the results to LS-3 for every point,
in the columns `point,h_min_um,attitude_deg,power_kW,t_eff_C,p_max_MPa`.
