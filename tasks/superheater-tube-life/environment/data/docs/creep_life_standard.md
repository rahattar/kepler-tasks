# Plant standard PS-14: creep life consumption of superheater tubes

This standard gives the consumed creep life of a superheater tube at its hottest point, the crown of the outlet leg on the furnace side, as a life fraction (Robinson's rule) from its entry into service.

## Operating data

Use the days the unit was on line (load above zero). Load fraction L = load / 600 MW. Pressure P is the main steam pressure.

Outlet steam temperature of an element = its penthouse pad thermocouple reading - 3 K. The element's steam pickup DT is its outlet steam temperature minus the temperature of the inlet header that feeds it.

## Crown heat flux

The crown heat flux follows the element's pickup: q = Q0 (DT / DT0) L, with Q0 = 70 kW/m2 and DT0 = 62 K.

## Mid-wall temperature at the crown

T_mw = T_steam + q (Do/Di) (1/h_i + x/k_ox) + q h / (2 k_m)

- T_steam: outlet steam temperature of the element
- Do: outside diameter; Di = Do - 2h; h: wall thickness at the time
- h_i: steam-side film coefficient, 6000 W/m2K at full load, scaling with L^0.8
- x: steam-side oxide thickness at the time; k_ox = 0.6 W/mK
- k_m = 33 W/mK

## Steam-side oxide

The oxide grows parabolically with the temperature at its mid-thickness, T_ox = T_steam + q (Do/Di) (1/h_i + x/(2 k_ox)):

d(x^2)/dt = A exp(-Q / (R T_ox)),  x in um, t in hours on line, T_ox in K, Q = 200 kJ/mol, R = 8.314 J/mol K

| grade | A, um^2/h |
|---|---|
| T22 | 4.4e12 |
| T91 | 3.0e11 |

Oxide starts from zero on a new tube and after a chemical clean.

## Stress and rupture life

Hoop stress by the mean-diameter formula: sigma = P (Do - h) / (2 h).

Rupture life t_r (hours) from the Larson-Miller parameter LMP = T (20 + log10 t_r), T the mid-wall temperature in K. The plant's average rupture lines (log10 sigma linear in LMP):

| grade | LMP at 40 MPa | LMP at 100 MPa |
|---|---|---|
| T22 | 21051 | 19200 |
| T91 | 22801 | 21215 |

## Life fraction

Consumed life = sum over time on line of (hours / t_r) at the conditions of the time, from the tube's entry into service.
