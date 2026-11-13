# IS-2 Cylinder pressure indicating: calculation of results

Issue 4. This standard fixes how the group's test cells turn a session's cylinder pressure records into
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

## 3 Pressure level

A piezoelectric transducer gives pressure changes, not pressure. From 180 to 170 degrees before top dead
centre the inlet valve is open and the cylinder is at manifold pressure. Each cycle's level is set so that its
mean pressure over those ten degrees equals the point's manifold pressure p_man.

## 4 Charge

From inlet valve closing (theta_ivc) to exhaust valve opening (theta_evo) the cylinder is closed. Its charge is
an ideal gas with R = 287 J/(kg K) and mass

    m = p_man V(theta_ivc) / (R T_ivc)

with T_ivc the point's charge temperature at inlet valve closing. The charge temperature at any angle is
T = p V / (m R).

## 5 Ratio of specific heats

    unburned charge   gamma_u = 1.375 - 6.99e-5 T
    burned charge     gamma_b = 1.330 - 4.50e-5 T
    charge            gamma   = (1 - x) gamma_u + x gamma_b

with T in K and x the burned fraction of section 7.

## 6 Heat transfer to the walls

The heat passing from the charge to the walls per unit time is h A (T - T_wall), with Hohenberg's coefficient

    h = 130 V^-0.06 p^0.8 T^-0.4 (c_m + 1.4)^0.8     W/(m^2 K)

where V is in m^3, p in bar, T in K and c_m = 2 S n / 60 is the mean piston speed in m/s at n rpm; the wall
area is A = (pi/2) B^2 + 4 V / B; and T_wall is the point's wall temperature. With these constants the
correlation gives the wall heat of the group's engines within 10 per cent.

## 7 Heat release

Between theta_ivc and theta_evo the gross heat released by combustion over a step of crank angle is

    dQ = gamma/(gamma - 1) p dV + 1/(gamma - 1) V dp + dQ_wall

with dQ_wall the wall heat of section 6 over the step. Q(theta) is its sum from theta_ivc. The burned fraction
is x(theta) = Q(theta) / Q(theta_evo), taken as 0 where it is below 0 and as 1 where it is above 1. Since
gamma depends on x, the calculation is repeated until Q(theta_evo) changes by less than 0.01 per cent.

## 8 Results

For each cycle:

- **Gross indicated mean effective pressure**: the integral of p dV from 180 degrees before to 180 degrees
  after top dead centre, divided by Vd.
- **Peak pressure and its angle**: the vertex of the parabola fitted by least squares to the samples within
  5 degrees of the cycle's highest sample.
- **Angles of 10 and 50 per cent burned**: the angles at which x first reaches 0.1 and 0.5.
- **Gross heat released**: Q(theta_evo).

The result for a point and cylinder is the mean over the cycles of its record.

## 9 Accuracy

Sums over the samples of a record are taken by a rule of second order or better. Results are issued to
0.3 degrees on angles, 1 per cent on peak pressure, 2 per cent on mean effective pressure and 3 per cent on
heat released.
