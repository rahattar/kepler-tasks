# Plant rating standard RS-12: shell-and-tube coolers, oil shell side, cooling water tube side

A design is rated at the design case as one lumped exchanger per shell: properties of each stream at the mean of its
inlet and outlet temperature over the whole cooler; the wall temperature for the viscosity correction from the
resistance split between the oil film and the rest; the thermal duty from the effectiveness of N 1-2 shells in
series (counter-current between shells). Iterate the outlet temperatures to convergence.

## Fluid properties (T in degC)

Oil: density rho = rho15 (1 - 0.00065 (T - 15)) kg/m3; specific heat cp = 1000 (1.80 + 0.0036 T) J/kg K; thermal
conductivity k = 0.134 - 0.00007 T W/m K; kinematic viscosity by ASTM D341 through the oil's measured viscosities at
40 and 100 degC. rho15, nu40 and nu100 come from the oil analysis of the oil in service.

Cooling water: rho = 1000.6 - 0.0128 T^1.76 kg/m3; cp = 4180 J/kg K; k = 0.569 + 0.00188 T - 7.5e-6 T^2 W/m K;
mu = 2.414e-5 x 10^(247.8 / (T + 273.15 - 140)) Pa s.

## Shell side (Bell-Delaware, Taborek)

Geometry from the catalogue clearances: bundle outer limit Dotl = Ds - Lbb; Dctl = Dotl - do; crossflow area
Sm = Lbc (Lbb + Dctl (Pt - do) / Pt); baffle cut angles theta_ds = 2 acos(1 - 2 Bc), theta_ctl = 2 acos(Ds (1 - 2 Bc)
/ Dctl); Fw = (theta_ctl - sin theta_ctl) / 2 pi; Fc = 1 - 2 Fw; window area Sw = Ds^2/8 (theta_ds - sin theta_ds) -
Nt Fw pi do^2/4; leakage areas Ssb = pi Ds Lsb/2 (1 - theta_ds / 2 pi), Stb = pi/4 ((do + Ltb)^2 - do^2) Nt (1 - Fw);
bypass area Sb = Lbc (Ds - Dotl); rows crossed Ntcc = Ds (1 - 2 Bc) / Pp and Ntcw = 0.8 (Ds Bc - (Ds - Dctl)/2) / Pp,
with Pp = Pt cos 30 deg (30 deg layout) or Pt (90 deg layout).

Re = do m / (mu Sm). Ideal bank: ji = a1 (1.33 / (Pt/do))^a Re^a2 with a = a3 / (1 + 0.14 Re^a4); fi likewise with
b1..b4.

| layout | Re range | a1 | a2 | b1 | b2 |
|---|---|---|---|---|---|
| 30 | >= 1e4 | 0.321 | -0.388 | 0.372 | -0.123 |
| 30 | 1e3 - 1e4 | 0.321 | -0.388 | 0.486 | -0.152 |
| 30 | 1e2 - 1e3 | 0.593 | -0.477 | 4.570 | -0.476 |
| 30 | 10 - 1e2 | 1.360 | -0.657 | 45.10 | -0.973 |
| 30 | < 10 | 1.400 | -0.667 | 48.00 | -1.000 |
| 90 | >= 1e4 | 0.370 | -0.396 | 0.391 | -0.148 |
| 90 | 1e3 - 1e4 | 0.107 | -0.266 | 0.0815 | 0.022 |
| 90 | 1e2 - 1e3 | 0.408 | -0.460 | 6.0900 | -0.602 |
| 90 | 10 - 1e2 | 0.900 | -0.631 | 32.10 | -0.963 |
| 90 | < 10 | 0.970 | -0.667 | 35.00 | -1.000 |

a3, a4, b3, b4: 1.450, 0.519, 7.00, 0.500 (30 deg); 1.187, 0.370, 6.30, 0.378 (90 deg).

h_shell = ji cp (m/Sm) Pr^(-2/3) (mu/mu_w)^0.14 Jc Jl Jb Jr with Jc = 0.55 + 0.72 Fc; Jl = 0.44 (1 - rs) +
(1 - 0.44 (1 - rs)) exp(-2.2 rlm), rs = Ssb/(Ssb + Stb), rlm = (Ssb + Stb)/Sm; Jb = exp(-C Sb/Sm), C = 1.25 below
Re 100 and 1.35 above; Jr = 1 at Re 100 and above, (10/Nc)^0.18 at Re 20 and below with Nc = (Ntcc + Ntcw)(Nb + 1),
linear between.

Pressure drop: dPbi = 2 fi Ntcc (m/Sm)^2 / rho (mu_w/mu)^0.14; Rl = exp(-1.33 (1 + rs) rlm^p), p = 0.8 - 0.15 (1 + rs);
Rb = exp(-C' Sb/Sm), C' = 4.5 below Re 100 and 3.7 above; crossflow dPbi (Nb - 1) Rb Rl; ends 2 dPbi (1 + Ntcw/Ntcc)
Rb; windows, Re 100 and above, Nb (2 + 0.6 Ntcw) mw^2 / (2 rho) Rl with mw = m / sqrt(Sm Sw); windows, below Re 100,
Nb [26 mu mw / rho (Ntcw / (Pt - do) + Lbc / Dw^2) + mw^2 / rho] Rl with the window hydraulic diameter
Dw = 4 Sw / (pi do Nt Fw + Ds theta_ds). The shell side pressure drop is the sum of crossflow, ends and windows. The
number of baffles Nb is the tube length divided by the central spacing, rounded, minus one.

## Tube side

Velocity from the flow per pass; Re = rho v di / mu; Darcy f = (0.790 ln Re - 1.64)^-2; Nu by Gnielinski; pressure drop
per shell = passes (f L/di + 2.5) rho v^2 / 2.

## Overall

1/Uo = 1/h_shell + Rf_oil + do ln(do/di) / (2 kw) + Rf_cw do/di + do/(di h_tube), kw = 45 W/m K, area per shell
Nt pi do L.

Fouling resistances (TEMA): lube oil 0.000176 m2 K/W; cooling tower water, treated, 0.000176 m2 K/W at a tube
velocity above 0.9 m/s and 0.000352 m2 K/W at 0.9 m/s or below.
