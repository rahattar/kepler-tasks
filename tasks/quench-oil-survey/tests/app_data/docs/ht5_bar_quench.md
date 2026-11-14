# HT-5 Oil quenching of round bars: calculation of the cooling of a load

## 1 Scope
Solid round steel bars of 16 to 120 mm diameter and at least four diameters long, of the steels of section 3,
taken from a furnace at 820 to 900 C and quenched whole in an oil bath at 40 to 90 C. The bar is at the furnace
temperature throughout when it enters the bath, and the bath stays at its temperature.

For one load the calculation gives five results (section 7) that the hardening shop works to: how fast the
centre of the bar passes through the transformation range, how far the surface runs ahead of it, and when the
bar can be taken out.

## 2 Conduction
- Heat flows radially only. T(r, t) is the temperature in C at radius r and time t after the bar enters the
  bath; R is the bar's radius.
- rho c_p(T) dT/dt = (1/r) d/dr ( r k(T) dT/dr ),  with dT/dr = 0 at r = 0.
- At the surface r = R:  -k(T) dT/dr = h(T_s) (T_s - T_bath),  where T_s = T(R, t) and h is the oil's heat
  transfer coefficient of section 4.
- At t = 0, T = T_furnace at every radius.

## 3 Steels
rho = 7800 kg/m3 for both. k in W/(m K) and c_p in J/(kg K) are linear between the temperatures tabulated and
constant below the first and above the last. The c_p tables carry the heat of transformation.

| steel | T, C | 20 | 300 | 600 | 800 | 900 |
|---|---|---|---|---|---|---|
| C45 | k | 50 | 44 | 34 | 26 | 26 |
| 42CrMo4 | k | 43 | 40 | 33 | 27 | 27 |

| steel | T, C | 20 | 300 | 600 | 720 | 800 | 900 |
|---|---|---|---|---|---|---|---|
| C45 | c_p | 470 | 560 | 750 | 900 | 650 | 650 |
| 42CrMo4 | c_p | 460 | 550 | 720 | 850 | 640 | 640 |

## 4 The oil's heat transfer coefficient
A quench oil is characterised by the laboratory's cooling-curve test of a sample: a standard probe is quenched
in the sample at 40 C, and the analysis reports three figures:

- CR_max, the probe's maximum cooling rate, in K/s
- T_CRmax, the probe temperature at which it occurs, in C
- CR_300, the probe's cooling rate at 300 C, in K/s

From them, with the probe constant K = 14 200 J/(m2 K):

- h_p = K CR_max / (T_CRmax - 40)   and   h_300 = K CR_300 / 260,   both in W/(m2 K).
- h(T_s) is linear in T_s between these points and constant outside them:

| T_s, C | 100 and below | 300 | T_CRmax | T_CRmax + 120 and above |
|---|---|---|---|---|
| h | 0.6 h_300 | h_300 | h_p | 0.15 h_p |

Above T_CRmax + 120 the bar is in its vapour blanket; the peak is nucleate boiling; below 300 C the oil cools
by convection.

## 5 Which oil
The three figures are those of the charge of oil that was in the tank when the load was quenched, from the
laboratory's analysis of that charge: its latest analysis where the charge has been analysed more than once,
and the mean where more than one sample of the charge was analysed on that date. An oil type's catalogue
figures are not used: charges as delivered differ from them by up to 15 per cent.

## 6 Convergence
A result is to HT-5 when a finer grid or shorter time steps would change each of the four results given in
seconds, K/s and K by less than 0.5 per cent, and the surface temperature of section 7 by less than 1 K.

## 7 Results
The centre is r = 0. t(T) is the time at which the centre first falls to the temperature T.

| quantity | name | unit |
|---|---|---|
| time for the centre to cool from 800 C to 500 C, t(500) - t(800) | t85_core | s |
| cooling rate of the centre through 700 C, 50 / ( t(675) - t(725) ) | cr700_core | K/s |
| largest difference between centre and surface temperature at any time | dT_max | K |
| surface temperature T_s at the time t(500) | ts_core500 | C |
| time for the centre to fall to 150 C, t(150) | t150_core | s |
