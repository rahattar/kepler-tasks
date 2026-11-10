# GT-1 performance test procedure (plant procedure TP-GT-07, rev 3)

This procedure determines the corrected gross output and the corrected heat rate (LHV) of gas turbine generator GT-1
at the contract reference conditions. It follows ASME PTC 22 practice with the OEM's correction curves. A test is run
with the unit as found and again after maintenance (as left), and the two sets of corrected results are compared.

## Reference conditions (contract)

| quantity | reference |
|---|---|
| compressor inlet temperature (CIT) | 15.0 degC |
| ambient (barometric) pressure | 101.325 kPa |
| ambient relative humidity | 60 % (specific humidity {W_REF} kg/kg dry air) |
| inlet loss | 1.00 kPa |
| exhaust loss | 3.00 kPa |
| generator power factor | 0.85 lagging |
| frequency | 60.0 Hz |
| fuel | natural gas, heat input on the lower heating value at 15 degC |

## Measured quantities

- Gross output, P: active power at the generator terminals, from the test wattmeter JT-001.
- Power factor: from JT-001's active and reactive power.
- Heat input, Q = m_f (LHV + 2.20 (T_f - 15)) in kW, with m_f the fuel mass flow (FT-301, kg/s), T_f the fuel temperature
  at the turbine fuel skid inlet (TE-305, degC), and LHV in kJ/kg.
- LHV: from the gas samples of the test day. The net molar heating value of each sample is the mole-fraction-weighted
  sum of the component values at 15 degC in the table below (ISO 6976); divide by the sample's molar mass to obtain
  the value per unit mass. The test day's LHV is the mean over that day's samples.
- CIT: the mean of the inlet RTD array.
- Ambient pressure: the barometric pressure at the elevation of the compressor inlet (plant datum, 310 m above sea
  level).
- Inlet loss: ambient pressure minus the compressor inlet total pressure (PT-102).
- Exhaust loss: PDT-201.
- Specific humidity: from the met station's dry bulb temperature and relative humidity at the ambient pressure.

| component | net molar heating value at 15 degC (kJ/mol) | molar mass (g/mol) |
|---|---|---|
| methane | 802.69 | 16.043 |
| ethane | 1428.84 | 30.069 |
| propane | 2043.37 | 44.096 |
| i-butane | 2648.42 | 58.122 |
| n-butane | 2657.60 | 58.122 |
| i-pentane | 3265.08 | 72.149 |
| n-pentane | 3272.00 | 72.149 |
| n-hexane (C6+) | 3887.21 | 86.175 |
| nitrogen | 0 | 28.0135 |
| carbon dioxide | 0 | 44.010 |
| oxygen | 0 | 31.9988 |

## Runs

Each run is logged in the test log with its start and end. A run's result is computed from 30 consecutive 1-minute
averages within the logged run during which the unit is steady at base load (on exhaust temperature control with the
inlet guide vanes fully open). Measurements are averaged over those 30 minutes, then corrected. A run that has no such
period is not valid. The result for a test condition (as found, as left) is the arithmetic mean of its valid runs.

## Corrections

1. Power factor: P_pf = P + L(P, PF) - L(P, 0.85), with L the generator losses from the generator data sheet.
2. Corrected output: P_corr = P_pf / (f_CIT x f_p x f_hum x f_in x f_ex), where f_p = p_amb / 101.325 and the other
   factors are read from the OEM correction curves (linear interpolation).
3. Heat rate: HR = 3600 Q / P_pf (kJ/kWh), and HR_corr = HR / (g_CIT x g_hum x g_in x g_ex) from the same curves
   (ambient pressure has no effect on heat rate).
