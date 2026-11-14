# Boiler package

A boiler's package is a directory of five files covering one calendar year. Every file is plain text, and the
CSV files have a header row and comma-separated fields. Times are hours of the plant's clock as
`YYYY-MM-DD HH:MM`, dates as `YYYY-MM-DD`.

## boiler.json
- `boiler`: the boiler's name.
- `rated_output_MW`: its rated heat output.
- `bottom_ash_loi`: the bottom ash LOI, as a mass fraction.
- `radiation_loss`: the radiation and unaccounted loss curve, a list of points with `load_fraction` and
  `loss_pct` (per cent of the heat input), in increasing load fraction.

## hourly.csv
One row for each hour the boiler ran, in time order. A boiler that was off for a time has no rows for it.

| column | meaning |
|---|---|
| `hour` | the start of the hour |
| `heat_output_MW` | heat output |
| `co2_pct` | CO2 at the air heater gas inlet, per cent by volume, dry |
| `o2_a_pct`, `o2_b_pct` | O2 at the air heater gas inlet from probes A and B, per cent by volume, dry |
| `o2_outlet_pct` | O2 at the air heater gas outlet, per cent by volume, dry |
| `co_ppm` | CO at the air heater gas inlet, ppm by volume, dry |
| `gas_outlet_C` | gas temperature at the air heater outlet |
| `air_inlet_C` | temperature of the air entering the air heater |
| `humidity_kg_kg` | specific humidity of that air, kg of water per kg of dry air |

## deliveries.csv
One row for each delivery of coal, in order of receipt: `delivery` (its name), `received` (date), the mass
fractions `C`, `H`, `O`, `N`, `S`, `ash` and `moisture`, and `hhv_kJ_kg`. The file includes the deliveries
received before the year opened whose coal was fired in it.

## bunker_log.csv
One row for each filling of the bunkers, in time order: `hour`, from which the burners fire the filling, and
`delivery`, the delivery it was taken from. The first row is at the year's first hour.

## fly_ash.csv
One row for each date the boiler ran: `date` and `loi`, the fly ash LOI as a mass fraction.

## expected.csv
Only in the examples: the BE-3 results, with the header `date,efficiency_pct,coal_t` and one row for every date
in `hourly.csv`.
