# GT-1 performance test record set - format

One directory per test day, holding four CSV files. Times are the end of each 1-minute averaging interval, plant
local time, "YYYY-MM-DD HH:MM".

## test_das_1min.csv (test data acquisition)

| column | content | unit |
|---|---|---|
| time | interval end | |
| gen_mw_jt001 | generator active power, test wattmeter JT-001 | MW |
| gen_mvar_jt001 | generator reactive power, JT-001 (positive lagging, negative leading) | Mvar |
| freq_hz | generator frequency | Hz |
| speed_pct | rotor speed, ST-001 | % of rated |
| cit_1_c ... cit_8_c | compressor inlet temperature, RTDs 1-8 of the inlet plenum array | degC |
| pdt101_filter_dp_kpa | differential pressure across the inlet filter stages | kPa |
| pt102_inlet_total_kpa_abs | compressor inlet (bellmouth) total pressure | kPa abs |
| pdt201_exhaust_kpa_g | exhaust diffuser exit static pressure above atmosphere | kPa g |
| fuel_coriolis_kg_s | fuel mass flow, FT-301 | kg/s |
| te301_fuel_meter_c | fuel temperature at FT-301 | degC |
| te305_fuel_skid_c | fuel temperature at the turbine fuel skid inlet, after the fuel heater | degC |
| igv_deg | inlet guide vane angle | deg |
| texh_avg_c | exhaust temperature, average of the control thermocouples | degC |
| ttrf_c | exhaust temperature control reference | degC |

- Record sets exported from the older acquisition system give the fuel flow as fuel_coriolis_kg_h (kg/h) instead of
  fuel_coriolis_kg_s.
- An RTD channel that the acquisition system detects as failed (open or short circuit) or that is switched out of
  service reads -999.0.
- When the acquisition network drops out, the minutes it missed are absent from the file (no row).

## dcs_1min.csv (unit DCS)

| column | content | unit |
|---|---|---|
| time | interval end | |
| gen_mw_dcs | generator active power, DCS transducer (operational, not for test use) | MW |
| met_dry_bulb_c | met station dry bulb temperature | degC |
| met_rh_pct | met station relative humidity | % |
| met_baro_hpa | met station barometric pressure (station pressure) | hPa |

- From the met station upgrade in late 2024 some exports give the barometer as met_baro_kpa (kPa) instead of
  met_baro_hpa.

## gas_analysis.csv (laboratory gas chromatograph)

One row per sample: sample_time, then the mole percentages of the components found, then gross_cv_mj_m3_15_15 (gross
volumetric calorific value at 15 degC / 15 degC, MJ/m3). A component that was not found has no column. Component
columns: CH4, C2H6, C3H8, iC4H10, nC4H10, neoC5H12, iC5H12, nC5H12, nC6H14 (C6 and heavier, reported as n-hexane), H2,
He, N2, CO2, O2.

## test_log.csv

time, entry. Run entries read "Run <name> start", "Run <name> end" or, when a run is abandoned, "Run <name> aborted".
The other entries are the operators' notes (unit starts, trips, gas samples and the like) in free text.
