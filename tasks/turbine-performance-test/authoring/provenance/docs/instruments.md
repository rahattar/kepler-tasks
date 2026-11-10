# GT-1 performance test instrumentation

| tag | instrument | notes |
|---|---|---|
| JT-001 | three-phase test wattmeter, class 0.1, on the metering PT and CT secondaries | primary scaling set in the meter; calibration certificate 2026-08 |
| CIT-1..8 | 4-wire Pt100 RTDs, 8-point array across the inlet plenum downstream of the silencer | |
| PDT-101 | differential pressure transmitter across the inlet filter stages | |
| PT-102 | absolute pressure transmitter, bellmouth total-pressure rake | |
| PDT-201 | pressure transmitter, exhaust diffuser exit static to atmosphere | |
| FT-301 | Coriolis mass flowmeter, fuel gas, upstream of the fuel heater | calibrated on gas 2026-06, certificate within 0.15 % |
| TE-301 | RTD at FT-301 | |
| TE-305 | RTD at the turbine fuel skid inlet, after the fuel heater | |

The met mast barometer is a digital precision barometer, calibrated 2026-07 against the metering contractor's transfer
standard (within 0.03 kPa); its output is logged by the met mast data logger.

The DCS records (dcs_1min.csv) are the unit's operating values: gen_mw_dcs from the generator protection CTs and PTs
through a 0.5-class transducer, unit_net_mw after the unit auxiliary transformer, and the met mast readings
(met_dry_bulb_c, met_rh_pct, met_baro_hpa).

Gas samples (gas_analysis.csv) are analysed by the plant laboratory's gas chromatograph; the report gives mole
percentages and the gross volumetric calorific value at 15 degC / 15 degC.
