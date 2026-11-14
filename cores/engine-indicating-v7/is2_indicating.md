# IS-2 Cylinder pressure indicating: calculation of results

Issue 5. This standard fixes how the group's test cells turn a session's cylinder pressure records into
results, so that results from different cells and engines can be set side by side.

## 1 Scope

Four-stroke reciprocating engines with a bore of 70 to 140 mm, a compression ratio of 9 to 18 and up to
6 cylinders, fired at 600 to 5,000 rpm and a manifold pressure of 0.3 to 2.6 bar absolute.

## 2 Crank angle and cylinder volume

Throughout, p is the pressure in the cylinder, absolute, and theta is the crank angle of that cylinder,
measured from its firing top dead centre, in degrees, positive after it.
With bore B, stroke S, connecting rod length L, crank radius a = S/2 and compression ratio r, the swept volume
is Vd = (pi/4) B^2 S and the cylinder volume is

    V(theta) = Vd/(r - 1) + (pi/4) B^2 [ a (1 - cos theta) + L - sqrt(L^2 - a^2 sin^2 theta) ]

## 3 The indicating system

A package gives counts at the indicating system's angles, theta_sys, on the indicating system's scale,
`bar_per_count` (see the cell package format). Four things stand between those and p and theta, and each is
put right before any result is taken.

- **Converter range.** Interference from the ignition drives single samples to an end of the converter's
  range. A sample of -32768 or 32767 counts is not a reading: it is replaced by the mean of the samples on
  either side of it.
- **Encoder index.** One crank angle encoder serves every cylinder of a cell, and its mark may stand off
  firing top dead centre by an index delta, the same for every cylinder: theta = theta_sys + delta. delta lies
  within 4 degrees either way.
- **Gain.** Each cylinder's transducer may give more or less than the scale assumes, by a gain g of its own,
  between 0.9 and 1.1: the pressure change a count stands for is `bar_per_count` / g.
- **Thermal shock.** While its diaphragm takes heat from the burning charge, a transducer reads low. The
  reading falls short of the pressure by s H, where

      H(t) = integral from inlet valve closing to t of q(t') exp(-(t - t') / tau) dt'

  is the heat the diaphragm holds, in J/m2; q = h (T - T_wall) is the heat flux density from the charge to
  the walls of section 7, taken as nil outside the closed part of the cycle, from inlet valve closing to
  exhaust valve opening; t is time, a degree of crank angle lasting 1/(6 n) s at n rpm; and tau = 3 ms. s is
  the transducer's own coefficient, in bar per kJ/m2, between 0 and 0.15. H is worked out from the pressure,
  not from the reading.

So a cylinder's reading is its counts times `bar_per_count` / g, set to its level by section 4, and the
pressure is p = reading + s H. delta, and g and s of every cylinder, are found from the package's own records
by section 9.

## 4 Pressure level

A piezoelectric transducer gives pressure changes, not pressure. From 180 to 170 degrees before top dead
centre the inlet valve is open and the cylinder is at manifold pressure. Each cycle's level is set so that its
mean pressure over those ten degrees equals the point's manifold pressure p_man.

## 5 Charge

From inlet valve closing (theta_ivc) to exhaust valve opening (theta_evo) the cylinder is closed. Its charge is
an ideal gas with R = 287 J/(kg K) and mass

    m = p_man V(theta_ivc) / (R T_ivc)

with T_ivc the point's charge temperature at inlet valve closing. The charge temperature at any angle is
T = p V / (m R).

## 6 Ratio of specific heats

    unburned charge   gamma_u = 1.375 - 6.99e-5 T
    burned charge     gamma_b = 1.330 - 4.50e-5 T
    charge            gamma   = (1 - x) gamma_u + x gamma_b

with T in K and x the burned fraction of section 8.

## 7 Heat transfer to the walls

The heat passing from the charge to the walls per unit time is h A (T - T_wall), with Hohenberg's coefficient

    h = 130 V^-0.06 p^0.8 T^-0.4 (c_m + 1.4)^0.8     W/(m^2 K)

where V is in m^3, p in bar, T in K and c_m = 2 S n / 60 is the mean piston speed in m/s at n rpm; the wall
area is A = (pi/2) B^2 + 4 V / B; and T_wall is the point's wall temperature. With these constants the
correlation gives the wall heat of the group's engines.

## 8 Heat release

Between theta_ivc and theta_evo the gross heat released by combustion over a step of crank angle is

    dQ = gamma/(gamma - 1) p dV + 1/(gamma - 1) V dp + dQ_wall

with dQ_wall the wall heat of section 7 over the step. Q(theta) is its sum from theta_ivc. The burned fraction
is x(theta) = Q(theta) / Q(theta_evo), taken as 0 where it is below 0 and as 1 where it is above 1. Since
gamma depends on x, the calculation is repeated until Q(theta_evo) changes by less than 0.01 per cent.

## 9 The indicating system's state

For the engines and operating points of section 1, no charge has begun to burn from 10 degrees after inlet
valve closing to 40 degrees before top dead centre, and every charge has finished burning from 70 degrees
after top dead centre to 10 degrees before exhaust valve opening. On the first stretch Q (with x = 0) is nil,
and on the second Q (with x = 1) stays at the value it has reached. delta, and g and s of every cylinder, are
the values that make it so, all of them together. The records carry noise, so they are the values that bring
Q nearest to nil on the first stretch and nearest to constant on the second, by least squares, in the mean
cycles of the cycles that fired (section 10), every point and cylinder of the package at once.

## 10 Misfires

A cycle whose gross heat released, Q(theta_evo), is below a quarter of the median of the cycles of its point
and cylinder misfired. It is left out of every result of section 11 and of the mean cycles of section 9.

## 11 Results

For each cycle that fired:

- **Gross indicated mean effective pressure**: the integral of p dV from 180 degrees before to 180 degrees
  after top dead centre, divided by Vd.
- **Peak pressure and its angle**: a knocking cycle rings at the chamber's acoustic frequencies, and the
  ringing is not part of the peak. The pressure from 180 degrees before to 180 degrees after top dead centre
  is passed through a fourth-order Butterworth low-pass filter with a cut-off of 2.5 kHz, forwards and then
  backwards; the peak and its angle are the vertex of the parabola fitted by least squares to the filtered
  samples within 5 degrees of the highest filtered sample.
- **Angles of 10 and 50 per cent burned**: the angles at which x first reaches 0.1 and 0.5.
- **Gross heat released**: Q(theta_evo).

All but the peak are taken on the pressure as it is, unfiltered. The result for a point and cylinder is the
mean over the cycles of its record that fired.

## 12 Accuracy

Sums over the samples of a record are taken by a rule of second order or better. Results are issued to
0.3 degrees on angles, 1 per cent on peak pressure, 2 per cent on mean effective pressure and 3 per cent on
heat released.
