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
q = pi D h (Tb - Tw) = pi D Uo (Tw - Ta). Uo is the line's outside coefficient, referred to the bore.

3.3 Inside film: h = Nu k / D, with
Nu = [ 3.66^3 + 0.7^3 + (1.077 Gz^(1/3) - 0.7)^3 ]^(1/3) (mu_b / mu_w)^0.14,
Gz = Re Pr D / x, Re = u D / v_b, Pr = v_b rho cp / k. Subscript b is at the local bulk temperature, w at
the local wall temperature.

3.4 Pressure gradient: - dp/dx = f rho u^2 / (2 D), with f = (64 / Re) (mu_w / mu_b)^0.5.

3.5 The pressure drop of the pipe is the integral of 3.4 from the inlet manifold to the outlet manifold, and
its outlet temperature is Tb there.

## 4 Pairs

A pair is two pipes that run side by side between the same two manifolds and are alike in bore, length,
covering and surroundings. The oil delivered to the inlet manifold divides between the two pipes. Both receive
it at the inlet temperature, and both have the pressure drop that stands between the manifolds.

## 5 Results

For each record of a line:

- **pressure drop**: the pressure at the inlet manifold less the pressure at the outlet manifold, in kPa;
- **outlet temperature**: the temperature of the oil leaving the outlet manifold, in degrees C; for a pair,
  of the two streams mixed.

Results are calculated to within 0.1 per cent of the pressure drop and 0.05 K.
