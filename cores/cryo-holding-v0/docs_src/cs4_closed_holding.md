# CS-4 Closed holding of liquid nitrogen tanks

## 1 Scope
The vertical vacuum-insulated tanks (perlite under vacuum) that hold liquid nitrogen at the works' depots,
closed for a holding period: at its start each tank is isolated from the recovery header and from draw-off,
and nothing is filled or drawn until the period ends. For each tank and each day of the period the calculation
gives the tank's pressure at the end of the day, the nitrogen its relief valve has vented since the start, and
its state.

## 2 Properties
2.1 Nitrogen is taken as saturated, from the table of Annex A (`n2_saturation.csv`): at temperature T, the
pressure p, the densities of the liquid and the vapour, and their specific enthalpies. A property at a
temperature between two rows is interpolated linearly in T; the saturation temperature at a pressure is
interpolated linearly in p.

2.2 The specific internal energy of liquid or vapour is u = h - p/rho, with p in kPa and rho in kg/m3 for u in
kJ/kg. The normal boiling point is 77.355 K, at 1.01325 bar.

## 3 Heat leak
3.1 The heat a tank takes in is Q = UA (T_a - T), in W, where T_a is the ambient temperature and T that of the
tank's contents. UA, in W/K, is the tank's heat leak; it does not depend on the contents or the pressure.

3.2 Vapour leaving a tank whose pressure is held steady carries off (1 - rho_v/rho_l) / (h_v - h_l) kg for each
J the tank takes in, the properties at the saturation temperature of that pressure.

3.3 In an NER test the tank is vented to the atmosphere, at 1.01325 bar, until it boils off at a steady rate.
The normal evaporation rate NER is the mass boiled off in a day, as a per cent of the mass of saturated liquid
at the normal boiling point that fills the tank's capacity. With 3.1 and 3.2 at the normal boiling point and the
ambient of the test, an NER gives the tank's UA.

3.4 The register holds each tank's NER from its acceptance test by the maker, with the ambient of that test.
Insulation ages in service, and its vacuum is not gauged in service. The insulation of sound tanks at a depot
ages alike: their heat leaks stand at one multiple of the heat leaks of their acceptance tests.

3.5 After work on a tank's insulation, its heat leak is known only from an NER test made since the work.

3.6 The tanks in service at a depot are connected to the recovery header and held at its pressure; their
boil-off goes through the header to the recovery compressor, whose meter gives the total for each day. A tank
in service boils off by 3.1 and 3.2 at the header pressure and the ambient of the day.

## 4 Contents
4.1 A tank's contents in kg are read from its gauge, a differential pressure transmitter across the liquid
whose chart is entered when the gauge is fitted. Fills are delivered by road tanker and ticketed from the
depot weighbridge, the tanker weighed in and out.

## 5 Closed holding
5.1 Each tank is closed at the start of the period with its contents at the close pressure, as saturated
liquid and vapour in equilibrium. Its volume is its capacity.

5.2 The contents stay saturated and in equilibrium throughout. While the tank is closed, with mass m, volume V
and so specific volume v = V/m, the internal energy of the contents rises each day by the day's heat,
UA (T_a - T) x 86,400 J, with that day's ambient and the temperature of the contents at the start of the day.
The state at the end of the day is the saturated state with that specific volume and that internal energy.

5.3 Once the pressure reaches the set pressure of the tank's relief valve, the valve holds it there and vents
vapour: the contents stay at the saturation temperature of the set pressure, and each day's heat vents
nitrogen by 3.2. On the day the set pressure is reached, the heat beyond what brings the contents to it vents.

5.4 A tank whose liquid would fill it before its set pressure is reached is full from the day it fills: its
pressure is that of saturated liquid at the specific volume v, and its records from that day carry that
pressure and the nitrogen vented until then.

## 6 Results
For each tank and each day of the period, counting the first day as 1: the pressure at the end of the day in
bar gauge (absolute less 1.01325); the nitrogen vented since the start, in kg; and the state, `closed`,
`venting` or `full`.

## Annex A
`n2_saturation.csv`: `T_K`, `p_bar` (absolute), `rho_l_kg_m3`, `rho_v_kg_m3`, `h_l_kJ_kg`, `h_v_kJ_kg`, from
77.0 K to 115.0 K in steps of 0.5 K.
