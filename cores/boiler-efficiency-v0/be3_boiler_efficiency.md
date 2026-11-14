# BE-3: Efficiency of a coal-fired boiler by the losses method

## 1 Scope
BE-3 gives, for each day a boiler runs, its efficiency on the higher heating value (HHV) and the coal it
fired, from the plant's hourly records. It covers pulverised-coal boilers firing one coal at a time from their
bunkers, with a regenerative air heater and the heat output metered at the boiler. The efficiency is found hour
by hour by the losses method (sections 3 to 6) and gathered into days (section 7).

The fuel, gas and air in sections 3 to 6 are those of the boiler as it ran: the coal being fired, and the flue
gas and the air themselves. A boiler's package holds the plant's readings and logs of them (section 2).

## 2 The records
- **Heat output**, MW, metered at the boiler. Taken as exact.
- **Flue gas at the air heater inlet**, dry basis, by volume: CO2 and CO by an infrared analyser, to 0.1 per
  cent CO2 and 10 ppm CO; O2 by two zirconia probes, A and B, each to 0.05 per cent O2.
- **Flue gas at the air heater outlet**: O2 by one probe, to 0.05 per cent O2, and the gas temperature, the mean
  of a grid, to 1 K.
- **Air entering the air heater**: temperature to 0.5 K, and specific humidity, kg of water per kg of dry air,
  to 3 per cent of its value.
- Each hourly row is the mean over the hour that starts at its time stamp.
- **Deliveries.** Each delivery of coal is analysed by the laboratory as received, which is also as fired:
  carbon, hydrogen, oxygen, nitrogen, sulphur, ash and moisture as mass fractions, and the HHV in kJ/kg.
- **Bunker log.** Every filling of the bunkers is logged with the hour from which the burners fire it and the
  delivery it was taken from. The hours from one entry up to the next are fired on that filling.
- **Fly ash.** One loss on ignition (LOI) a day, from a composite sample: the mass fraction of the fly ash that
  is unburnt carbon. It holds for every hour of its day.
- **Bottom ash.** One LOI for the boiler, in its `boiler.json`.

## 3 Combustion
Everything in this section is per kg of fuel fired, with C, H, O, N, S, ash and M the mass fractions of the
fuel's analysis.

Of the ash, 0.8 leaves the furnace as fly ash and 0.2 as bottom ash. The unburnt carbon is

    u = ash * (0.8 * LOI_fly / (1 - LOI_fly) + 0.2 * LOI_bottom / (1 - LOI_bottom))      kg

and the burnt carbon, hydrogen, sulphur, fuel oxygen and fuel nitrogen are, in kmol,

    n_C = (C - u) / 12.011    n_H2 = H / 2.016    n_S = S / 32.06    n_O2 = O / 31.998    n_N2 = N / 28.013

The theoretical oxygen is n_th = n_C + n_H2 / 2 + n_S - n_O2. Air is 0.2095 O2 and 0.7905 N2 by volume, so
3.773 kmol of N2 come with every kmol of O2.

With an excess air E (as a fraction of the theoretical air) and a share x of the burnt carbon leaving as CO,
the dry flue gas at the air heater inlet holds, in kmol,

    CO2  n_C (1 - x)        CO  n_C x        SO2  n_S
    O2   E n_th + n_C x / 2                  N2   3.773 (1 + E) n_th + n_N2

in all D = n_C + n_S + n_N2 + 3.773 n_th + n_C x / 2 + 4.773 E n_th. The volume fraction of each constituent is
its share of D. The share x follows from the gas's CO and CO2, x / (1 - x) = CO_ppm / (10^4 CO2_pct), and the
excess air from its CO2:

    E = (100 n_C (1 - x) / CO2_pct - (n_C + n_S + n_N2 + 3.773 n_th + n_C x / 2)) / (4.773 n_th)

The dry gas mass m_dg, in kg, is the sum of the constituents' amounts times their molar masses: 44.010 (CO2),
28.010 (CO), 64.060 (SO2), 31.998 (O2) and 28.013 (N2). The dry air supplied is m_a = 137.69 (1 + E) n_th kg.

## 4 Air heater
Air leaks into the gas across the air heater. As mass of air per unit mass of gas entering,

    L = 0.9 (O2_out - O2_in) / (20.95 - O2_out)

with O2_in the gas's O2 content at the inlet and O2_out at the outlet, in per cent. The gas temperature at the
outlet corrected to no leakage is

    T_g = T_out + L (c_a / c_g) (T_out - T_a)

with T_out the gas temperature at the outlet, T_a that of the air entering, c_a = 1.005 and c_g = 1.05 kJ/(kg K).

## 5 Losses
The reference temperature T_r is the temperature of the air entering, T_a. The losses, in kJ per kg of fuel:
- dry gas: m_dg * 1.02 * (T_g - T_r)
- water from the fuel's hydrogen and its moisture: (9 H + M) * (2501 + 1.88 T_g - 4.19 T_r)
- moisture in the air: m_a * w * 1.88 * (T_g - T_r), with w the air's specific humidity
- unburnt carbon: 33,700 u
- carbon monoxide: 10,110 * 28.010 n_C x
- sensible heat of the refuse: 0.84 * (mass) * (T - T_r), for the fly ash, 0.8 ash / (1 - LOI_fly) at T_g,
  and for the bottom ash, 0.2 ash / (1 - LOI_bottom) at 800 C

The radiation and unaccounted loss is a percentage of the heat input, read from the boiler's curve against its
load fraction (heat output over rated output): linear between the points, and the end value beyond either end.

Temperatures are in C.

## 6 Efficiency and fuel
The efficiency of an hour, in per cent, is

    eta = 100 - 100 * (sum of the losses of section 5, kJ/kg) / HHV - (radiation and unaccounted loss)

and the fuel fired is F = 1000 Q / (eta / 100 * HHV) kg/s, with Q the heat output in MW and HHV in kJ/kg.

## 7 Days
A day runs from midnight to midnight by the time stamps. Its efficiency is 100 * sum(Q) / sum(100 Q / eta) and
its coal fired is sum(3600 F) / 1000 tonnes, both over the day's hours with records. A day without hourly records
has no result.
