# HP-2 Results of a hydraulic power unit log

Plant procedure for reducing a logger record of a press's hydraulic power unit (unit.json and log.csv) to the
results used in the pump-retrofit study. All pressures in the records are gauge; the gas law uses absolute
pressure, gauge plus 1.013 bar.

## Definitions

- The pump is loaded when its outlet pressure is above 20 bar, unloaded otherwise.
- Motor speed while loaded: n = n_sync - (n_sync - n_rated) P_shaft / P_rated, with P_shaft = eta_motor x P_el, the
  motor's efficiency times the logged input power.
- Pump flow while loaded: Q_p = Vg n eta_v(p_pump), with Vg the displacement, and eta_v the volumetric efficiency
  interpolated in the pump's table at the pump outlet pressure. Q_p = 0 when unloaded.
- Accumulator gas volume at each sample: V_gas = V0 (p_0 / p_m) (p_m / p_sys)^(1/1.40), with V0 the accumulator
  volume, p_0 the precharge pressure, p_m the mean system pressure over the record and p_sys the system pressure
  (all absolute). Over a cycle the gas returns to the oil temperature, so its mean state follows the isothermal
  law from the precharge; its swings about that state within the cycle are adiabatic (nitrogen, 1.40).
- Oil demand of the press at sample i: Q_d(i) = Q_p(i) + (V_gas(i+1) - V_gas(i-1)) / (2 dt), with dt the sample
  interval (the accumulator gives oil when its gas expands). At the first and last samples the one-sided difference
  is used. Pressures are used as logged; no filtering.
- A cycle runs from one reloading of the pump (the pump outlet pressure rising above 20 bar) to the next. Results
  are computed for each complete cycle and reported as the mean over the complete cycles in the record.

## Results

- `oil_delivered_l`: the integral of Q_d over the cycle, litres.
- `peak_flow_l_min`: the highest mean of Q_d over any 1.0 s window in the cycle, litres per minute.
- `hydraulic_energy_kj`: the integral of p_sys Q_d over the cycle (p_sys absolute), kJ.
- `electrical_energy_kj`: the integral of the motor input power over the cycle, kJ.
- `unit_efficiency`: hydraulic_energy_kj / electrical_energy_kj.

Results are written as one JSON object with these five keys.
