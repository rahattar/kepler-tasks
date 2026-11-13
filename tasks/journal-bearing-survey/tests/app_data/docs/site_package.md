# Site packages

A package is a folder holding the records of one site's journal bearings: six files.

## `site.json`
- `site`: the site's name
- `lab_samples`: the number of oil samples the laboratory will analyse for this package (see "The laboratory")

## `bearings.csv`: one row for each bearing
- `tag`: the bearing's tag
- `machine`: the machine the bearing belongs to. A machine's bearings share one oil supply.
- `oil_system`: the lube oil system the machine is connected to in the site register
- `journal_diameter_mm`, `length_mm`, `radial_clearance_um`: 2R, L and c
- `groove_angles_deg`: the angles theta of the axial oil grooves (LS-3 section 2), separated by `;`
- `oil_flow_L_min`: oil flow to the bearing, Q

## `oil_systems.csv`: the site register of lube oil systems
- `oil_system`, `kind` (`console` for a system that feeds several machines, `self-contained` for a machine with
  its own sump), `oil_grade`

## `oil_log.csv`: work on the oil
One row for each job: `date,oil_system,work,remarks`. `CHARGE_RENEWED`: the system was drained and refilled.

## `oil_samples.csv`: laboratory analyses on file
One row for each sample: `date,sampled_at,nu40_cSt,nu100_cSt,rho15_kg_m3`. `sampled_at` is the tag of the bearing
at whose supply line the sample was drawn; the figures are the kinematic viscosity in mm2/s at 40 C and 100 C
and the density at 15 C. The laboratory repeats a viscosity within 0.5 per cent.

## `points.csv`: the operating points on record
One row for each point: `point,tag,date,speed_rpm,load_N,load_angle_deg,inlet_C`: the bearing, the date, the
journal speed, the load W and its angle beta (LS-3 section 2) and the oil inlet temperature T_in.

Dates are year-month-day. No operating point shares a date with a job or a sample.

## The laboratory
The laboratory will analyse samples of the oil now in the bearings' supplies, drawn at the bearings named. It
takes one order for a package, of at most `lab_samples` bearings:

    labsample PACKAGE_DIR TAG [TAG ...]

It prints `sampled_at,nu40_cSt,nu100_cSt,rho15_kg_m3` and one row for each bearing named. A second order for the
same package in the same run is refused.

The two packages in `examples` each carry one more file, `expected.csv`: the results to LS-3 for every point,
in the columns `point,h_min_um,attitude_deg,power_kW,t_eff_C,p_max_MPa`. The package in `pending` is as its
site sent it in: the six files, no results.
