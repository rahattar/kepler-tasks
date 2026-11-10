# CT-2 thermal capability from operating data (plant procedure TP-31)

This procedure rates each cell of cooling tower CT-2 from its own operating records, as a percentage of the design fill characteristic. It follows the Merkel method used for acceptance tests, applied hour by hour to operating data instead of to a single test run.

## Quantities

- Water mass flow on the fill, L (kg/s): the riser flow that actually reaches the fill, at a water density of 994 kg/m3.
- Air mass flow, G (kg/s, dry air basis taken as the moist-air mass flow): from the fan laws, G = G_d x (P / P_d)^(1/3) x (rho / rho_d)^(2/3), where P is the fan motor input power, P_d = 160 kW, G_d = G_DESIGN kg/s and rho_d = RHO_DESIGN kg/m3 are the design values, and rho is the density of the entering air.
- Entering air: the met station's ambient air, unless a cell's inlet air is known to differ (see the 2025 recirculation survey). Its wet bulb is computed from the dry bulb, relative humidity and the barometric pressure at the hour; its enthalpy is the saturated-air enthalpy at that wet bulb.
- Psychrometric properties at the measured barometric pressure (the site is about 800 m above sea level): saturation pressure over water, humidity ratio W = 0.621945 pw / (p - pw), enthalpy h = 1.006 t + W (2501 + 1.86 t) kJ/kg dry air.

## Merkel number and capability

For each valid hour, the tower characteristic is

KaV/L = integral from t_cold to t_hot of cp dt / (h_s(t) - h_a(t)),

with cp = 4.186 kJ/kg K, h_s(t) the saturated-air enthalpy at the water temperature t, and the air enthalpy rising through the fill from the entering value as h_a(t) = h_in + (L/G) cp (t - t_cold). Evaluate the integral numerically (Simpson's rule with at least 20 intervals, or an equivalent accuracy).

The fill's design characteristic is KaV/L = C_d (L/G)^-0.65 with C_d = C_DESIGN (fill design sheet). Each hour gives C = (KaV/L) (L/G)^0.65. A cell's capability is 100 x (median of C over its valid hours) / C_d, in percent.

## Valid hours

- The fan runs at 60 % speed or more.
- Wind at the met station 4.5 m/s or less (stronger wind disturbs the inlet flow and the cell's performance).
- The cell's present fill: hours since the last fill change only.

The capability reported for a cell describes it as it stands at the end of the period of record.
