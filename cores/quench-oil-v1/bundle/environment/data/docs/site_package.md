# Site packages

A package is a folder holding the records of one site's hardening shop: six files.

## `site.json`
- `site`: the site's name
- `lab_samples`: the number of oil samples the laboratory will analyse for this package (see "The laboratory")
- `samples_drawn`: the date the laboratory draws those samples

## `tanks.csv`: one row for each quench tank
- `tank`: the tank's tag
- `oil_system`: the quench oil system the tank is connected to in the site register
- `volume_m3`: the tank's working volume

## `oil_systems.csv`: the site register of quench oil systems
- `oil_system`, `kind` (`central` for a system that feeds several tanks from one reservoir, `single` for a tank
  with its own oil), `oil_type`

## `oil_log.csv`: work on the oil
One row for each job: `date,oil_system,work,remarks`. `CHARGE_RENEWED`: the system was drained and refilled.

## `oil_samples.csv`: laboratory analyses on file
One row for each sample: `date,sampled_at,cr_max_K_s,t_crmax_C,cr_300_K_s`. `sampled_at` is the tag of the tank
the sample was drawn from; the figures are CR_max, T_CRmax and CR_300 of HT-5 section 4. The laboratory repeats
a cooling rate within 0.5 per cent. As a charge of quench oil ages in service, its cooling rates rise by less
than 0.5 per cent from one six-monthly sample round to the next.

## `loads.csv`: the loads on record
One row for each load: `load,tank,date,steel,diameter_mm,furnace_C,bath_C`: the tank it was quenched in, the
date, the steel (HT-5 section 3), the bar diameter 2R, the furnace temperature and the bath temperature.

Dates are year-month-day. No load shares a date with a job or a sample.

## The laboratory
The laboratory will analyse samples of the oil in the tanks named, drawn on the package's `samples_drawn`. It
takes one order for a package, of at most `lab_samples` tanks:

    labsample PACKAGE_DIR TANK [TANK ...]

It prints `sampled_at,cr_max_K_s,t_crmax_C,cr_300_K_s` and one row for each tank named. A second order for the
same package in the same run is refused. Where the program is written, the laboratory answers for the two
packages in `examples` only.

The two packages in `examples` each carry one more file, `expected.csv`: the results to HT-5 for every load,
in the columns `load,t85_core_s,cr700_core_K_s,dT_max_K,ts_core500_C,t150_core_s`. The package in `pending` is
as its site sent it in: the six files, no results.
