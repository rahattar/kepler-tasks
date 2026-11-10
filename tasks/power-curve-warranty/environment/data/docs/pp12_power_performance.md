# PP-12 Power performance verification (warranty)

Owner's procedure PP-12, revision 3 (2025-11-20), for the power curve warranty of the supply agreement covering the
Halden turbines at the owner's wind farms. It is applied to one farm-period package at a time.

## 1. Basis

Power performance is verified with nacelle anemometry after IEC 61400-12-2:2022, against the warranted power curve of
each turbine's model (supply agreement appendix C, the package's `warranted_power_curves.csv`). The verification period
is the package's period, in the farm's local standard time.

## 2. Data

- Turbine data: the 10-minute SCADA records of each turbine (`scada/turbine_<turbine>.csv`).
- Site meteorology: the farm's met mast M1 (`mast/m1_10min.csv`).
- Air density for each 10-minute period: from M1's hub-height temperature and relative humidity and its barometer,
  the pressure reduced to hub height with the barometric formula at the measured temperature, by IEC 61400-12-1:2022
  formula (12): rho = (1/T) (B/R0 - phi Pw (1/R0 - 1/Rw)), R0 = 287.05 J/(kg K), Rw = 461.5 J/(kg K),
  Pw = 0.0000205 exp(0.0631846 T) Pa, T in K, B in Pa, phi the relative humidity (0 to 1).
- Power: the turbine's SCADA active power. The revenue meters at the turbines' step-up transformers
  (`records/monthly_meter_energy.csv`) are the farm's reference for turbine energy.
- Record checks: every record is checked against the farm's other records and against the physics before it is
  used. A record found in error is corrected where the other records fix the right value; otherwise the periods it
  affects are left out.

## 3. Free-stream wind speed

The free-stream wind speed of a period is the turbine's nacelle wind speed through the farm's nacelle transfer
function (NTF), given in the site description, established from the calibration turbine and M1 in the calibration
sector (M1 wind direction). An NTF applies only to the configuration it was established for (IEC 61400-12-2); where it
no longer applies, it is re-established from the calibration turbine and M1 in the calibration sector, with M1's wind
speed from its anemometer calibration.

## 4. Data selection

A 10-minute period of a turbine is used only when all of the following hold:
- the turbine's status is 0 (running, unrestricted);
- no power limitation applies: neither a grid operator curtailment (`records/curtailment_log.csv`) nor an operating
  mode of the farm's noise permit (`noise_permit.md`, where the farm has one);
- no icing: M1 temperature at or above 2 C or relative humidity at or below 85 percent, and no ice alarm where the
  turbine has an ice detector;
- the turbine's wind direction is outside every disturbed sector (IEC 61400-12-1:2022 Annex A) of the neighbouring
  turbines within 20 of their rotor diameters, whether or not they were running. The disturbed sector of a neighbour
  at distance L with rotor diameter Dn is centred on the bearing from the turbine to the neighbour and is
  1.3 arctan(2.5 Dn/L + 0.15) + 10 degrees wide. The turbine's wind direction is its yaw position corrected by its
  north offset (site description).

## 5. Measured power curve

Normalise each period's free-stream wind speed to the reference density 1.225 kg/m3: V_n = V (rho/1.225)^(1/3).
Bin the periods in 0.5 m/s bins centred on 3.0, 3.5, ... 25.0 m/s; a bin's point is the mean normalised wind speed
and the mean power of its periods, and bins with fewer than 3 periods are left out. The measured power curve is the
bin points joined by straight lines and held constant beyond the first and last points.

## 6. Annual energy ratio and claim

Evaluate the measured and the warranted curve at 3.0, 3.5, ... 25.0 m/s and compute each one's annual energy for a
Rayleigh distribution of mean 7.5 m/s: AEP = 8760 h x sum over intervals of [F(V_i) - F(V_i-1)] (P_i-1 + P_i)/2,
F(V) = 1 - exp(-(pi/4)(V/7.5)^2). The annual energy ratio is measured AEP over warranted AEP. A turbine whose ratio is
below 0.97 is claimed under the power curve warranty.
