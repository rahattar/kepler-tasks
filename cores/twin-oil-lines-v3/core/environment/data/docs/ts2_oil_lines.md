# TS-2 Heated oil transfer lines

Terminal standard for the lines that carry heated fuel oil from a heater's outlet manifold to the manifold of
the plant it feeds.

## 1 Scope

TS-2 applies to steady flow in a level line of constant bore, covered or bare, where

- the flow is laminar: the Reynolds number on the bulk temperature is at most 2000 in every pipe;
- the oil is one of the site's oils table and behaves as 2.2 says at every temperature it reaches;
- the line is a single pipe, or a pair of pipes as section 4 describes.

Fittings, the pipe wall's own resistance to heat and the heat released by friction are neglected.

## 2 The oil

2.1 The density, the specific heat and the thermal conductivity are constant, as tabulated.

2.2 The kinematic viscosity follows ASTM D341 through the two tabulated points:
log10(log10(v + 0.7)) = A - B log10(T), with v in cSt (mm2/s) and T in kelvin. The dynamic viscosity is the
density times v.

## 3 One pipe

x is the distance from the inlet manifold, D the bore, m the mass flow in the pipe, u = 4 m / (pi D^2 rho) the
mean velocity. Tb(x) is the bulk temperature of the oil, Tw(x) the temperature of the pipe wall and Ta the
temperature of the surroundings.

3.1 Heat balance on the oil: m cp dTb/dx = - q, with Tb = the inlet temperature at x = 0.

3.2 The heat lost per unit length passes from the oil to the wall and from the wall to the surroundings:
q = pi D h (Tb - Tw) = pi D Uo (Tw - Ta). Uo is the outside coefficient of the pipe, referred to the bore.

3.3 Inside film: h = Nu k / D, with
Nu = [ 3.66^3 + 0.7^3 + (1.077 Gz^(1/3) - 0.7)^3 ]^(1/3) (mu_b / mu_w)^0.14,
Gz = Re Pr D / x, Re = u D / v_b, Pr = v_b rho cp / k. Subscript b is at the local bulk temperature, w at
the local wall temperature.

3.4 Pressure gradient: - dp/dx = f rho u^2 / (2 D), with f = (64 / Re) (mu_w / mu_b)^0.5.

3.5 The pressure drop of the pipe is the integral of 3.4 from the inlet manifold to the outlet manifold, and
its outlet temperature is Tb there.

## 4 Pairs

4.1 A pair is two pipes that run side by side between the same two manifolds, laid to the same bore and
length. Each has its own covering. The oil delivered to the inlet manifold divides between the two pipes. Both
receive it at the inlet temperature, and both have the pressure drop that stands between the manifolds.

4.2 More than one division of the oil can satisfy 4.1. Which of them a pair has follows from the one it had,
because oil shifts from the pipe with the higher pressure drop to the other. From one record to the next the
pair starts at the division of the earlier record, and under the conditions of the later record oil shifts
from the pipe that then has the higher pressure drop to the other until the two pressure drops are equal.

4.3 A line's run of records opens at a flow at which one division only satisfies 4.1.

## 5 Where the quantities come from

5.1 The lines register records the bore and the length each pipe was laid with. Pipes are not gauged in
service.

5.2 The outside coefficient of a pipe is a property of its covering as that covering stands. The terminal
measures it by a heat-loss survey of the pipe: with the line in steady service at its survey rating, the flow
through the pipe, the temperature of the oil where it enters the pipe and where it leaves it, and the
temperature of the surroundings are read. Uo is the value for which 3.1 to 3.3 give the temperature read where
the oil leaves the pipe.

5.3 A covering that has been renewed or repaired is not the covering that was surveyed before the work.

5.4 A survey reads a flow to within 0.2 per cent, an oil temperature to within 0.02 K and the temperature of
the surroundings to within 0.1 K.

5.5 A pipe's bore in service can be less than the bore it was laid with, where deposit has built up inside it;
the register and the work log do not record it. D in section 3 is the bore in service. The two pipes of a pair
have one pressure drop (4.1), so a survey that reads the oil delivered to a pair and the flow through one of its
pipes gives the pair's division, and a bore in service is the bore at which section 3 gives the two pipes one
pressure drop at the division read.

5.6 A covering can change with no work done on it. Where a pipe's outside coefficients from successive
campaigns differ by more than the accuracies of 5.4 allow, its covering is changing, and the coefficient of its
last survey is not the coefficient of the covering as it stands.

## 6 Results

For each record of a line:

- **pressure drop**: the pressure at the inlet manifold less the pressure at the outlet manifold, in kPa;
- **outlet temperature**: the temperature of the oil leaving the outlet manifold, in degrees C; for a pair,
  of the two streams mixed.

Results are calculated to within 0.1 per cent of the pressure drop and 0.05 K.
