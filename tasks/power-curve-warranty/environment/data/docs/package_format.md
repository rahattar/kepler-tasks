# Farm-period package format

Each package holds one farm's records for one verification period (about six months):

- `site_description.md`: farm, period, local standard time, elevation, turbines (position relative to M1, model,
  rotor diameter, hub height, north offset), the calibration turbine and sector, the farm's NTF table, M1's
  instruments and the anemometer calibration certificate in force at the start of the period;
- `warranted_power_curves.csv`: the warranted curve of each turbine model of the supply agreement (kW against wind speed at
  1.225 kg/m3);
- `noise_permit.md`: the farm's noise permit conditions, where it has one;
- `scada/turbine_<turbine>.csv`: 10-minute SCADA records of each turbine, stamped at the start of the period in the farm's
  local standard time as configured at commissioning: `power_kw` (mean active power), `nacelle_ws_ms` (mean nacelle
  wind speed reported by the controller), `yaw_position_deg` (mean yaw position, degrees from north as the controller
  reports it), `status` (0 running unrestricted, 1 ready below cut-in, 2 fault, 3 maintenance, 5 curtailed by the grid
  operator, 7 manual stop; the status that held for most of the period), `ambient_temp_c` (nacelle air temperature),
  `ambient_pressure_hpa` (air pressure from the controllers' weather feed), and `ice_alarm` on turbines with an ice
  detector;
- `mast/m1_10min.csv`: M1's 10-minute records in local standard time: `ws_hub_hz` (hub-height cup anemometer output
  frequency, Hz), `wd_hub_deg` (hub-height vane, degrees from true north), `temp_hub_c`, `rh_hub_pct`, and
  `pressure_2m_hpa` (barometer 2 m above ground);
- `records/maintenance_log.csv`, `records/mast_service_log.csv`, `records/curtailment_log.csv` and
  `records/monthly_meter_energy.csv` (kWh at each turbine's revenue meter).
