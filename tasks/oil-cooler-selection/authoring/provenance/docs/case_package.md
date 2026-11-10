# Cooler case packages

One directory per cooler:
- case.json: the cooler, its service, the period of record, the cooling water allotment (kg/s) and the limits: oil
  outlet temperature (degC), oil side and water side pressure drop (kPa), tube velocity range (m/s).
- trend.csv: 10-minute averages over the period from the plant historian, one column per instrument tag. The
  historian stores what the transmitters sent.
- instruments.csv: tag, measurement, unit and location of each trended instrument.
- calibration.csv: calibrations of those instruments. as_found_error is the reading minus the true value when found
  (in percent of reading, or in K); adjusted = yes means the instrument was corrected at that calibration, so its
  readings before then carry the as-found error and its readings after it are correct.
- maintenance.csv: maintenance and operations log.
- oil_analysis.csv: laboratory analyses of the oil in service (oil grade, density at 15 degC, kinematic viscosity at
  40 and 100 degC).

The example, examples/e410-k400-lube, also holds the plant engineer's selection for that cooler (selection.json),
with the design case it was made for.
