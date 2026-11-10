# GT-1 performance test procedure (plant procedure TP-GT-07, rev 4)

This procedure determines the corrected gross output and the corrected heat rate (LHV) of gas turbine generator GT-1
at the contract reference conditions from one test day's records, by ASME PTC 22 practice with the OEM's correction
curves. The record set of a test day is described in gt1_record_format.md and the test instrumentation in
gt1_instruments.md.

## Reference conditions (contract)

| quantity | reference |
|---|---|
| compressor inlet temperature (CIT) | 15.0 degC |
| ambient (barometric) pressure | 101.325 kPa |
| ambient relative humidity | 60 % (specific humidity {W_REF} kg/kg dry air) |
| inlet pressure loss | 1.00 kPa |
| exhaust pressure loss | 3.00 kPa |
| generator power factor | 0.85 lagging |
| frequency | 60.0 Hz |
| fuel | natural gas; heat input on the lower (net) heating value with 15 degC as the reference temperature |

## Quantities

- Gross output: active power at the generator terminals, from the test wattmeter.
- Heat input: fuel mass flow times the fuel's lower heating value per unit mass, plus the fuel's sensible heat above
  15 degC as it enters the gas turbine (specific heat 2.20 kJ/kg K).
- Lower heating value: from the composition of each gas sample taken on the test day, by ISO 6976 (2016) with ideal-gas
  net molar heating values at a 15 degC combustion reference temperature, on a mass basis; the test day's value is the
  mean over its samples. The laboratory's volumetric gross value is for information only.
- Compressor inlet temperature: the mean of the inlet temperature array channels in service.
- Ambient pressure: the met station barometer (station pressure at the plant datum).
- Inlet pressure loss: the total-pressure loss of the inlet system, from ambient to the compressor inlet.
- Exhaust pressure loss: the static pressure at the exhaust diffuser exit above ambient.
- Specific humidity: from the met station's dry bulb temperature and relative humidity at the ambient pressure.

## Instrument verification

The inlet and fuel instruments are checked against the plant references on the test day, from the records taken while
GT-1 is at rest: shut down on its turning gear, with no air flow and no fuel flow. At rest, PT-102 reads the met
station barometer, each inlet RTD reads the met station dry bulb, and FT-301 reads zero flow. An instrument's steady
difference from its reference at rest is its error for that day and is removed from all of its readings before the
reduction. If GT-1 was not at rest at any time in the record, the instruments are used as read.

## Runs

Each run is logged in the test log with its start and end; a run that was abandoned is not valid. A run's result comes
from 30 successive 1-minute averages (none missing) within the logged run during which the unit is steady at base
load: on exhaust temperature control with the inlet guide vanes fully open. Use the first such period of the run.
Measurements are averaged over the 30 minutes and then corrected. A run without such a period is not valid. The test
result is the arithmetic mean of the valid runs.

## Corrections

The OEM curves give, for each parameter, the ratio of gross output (at the reference power factor) and of heat rate at
a value of that parameter to their values at the reference, all other parameters at reference. Ambient pressure acts
on output in direct proportion and not on heat rate. Read the curves linearly between tabulated points and, beyond the
tabulated range, linearly from the two end points.

1. Refer the measured output to the reference power factor: the generator output that the same shaft power would give
   at 0.85 power factor, with the generator losses of generator_data.md.
2. Refer that output, and the heat rate based on it, to the reference conditions with the OEM curves.
