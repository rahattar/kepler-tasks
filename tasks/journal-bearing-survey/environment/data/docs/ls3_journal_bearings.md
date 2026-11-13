# LS-3 Hydrodynamic journal bearings: calculation of the operating point

## 1 Scope
Plain cylindrical journal bearings with axial oil grooves, steadily loaded and pressure fed: diameters of 40 to
600 mm, length to diameter ratios of 0.3 to 1.2, mineral oils of ISO VG 22 to 150, journal speeds to 12 000 rpm,
loads of 0.02 to 7 MPa on the projected area (load / (length x diameter)), oil inlet temperatures of 10 to
85 C, and loads up to 60 degrees either side of the downward vertical. Laminar and turbulent films are both
covered (section 5).

For one operating point the calculation gives the minimum film thickness, the attitude angle, the power loss,
the effective film temperature and the peak film pressure.

## 2 Geometry
- R is the journal radius, L the bearing length, c the radial clearance, omega the journal speed in rad/s.
- theta is the angle around the bearing, measured from the top of the bearing in the direction of rotation.
  z is the axial coordinate, zero at mid-length.
- The oil grooves are axial, at the angles theta given for the bearing.
- The load W on the journal acts toward theta_L = 180 deg + beta, where beta is the load angle: measured from the
  downward vertical, positive in the direction of rotation.
- Under load the journal centre sits a distance e = eps c from the bearing centre, toward theta = psi. The film
  thickness is h(theta) = c (1 - eps cos(theta - psi)), smallest at theta = psi: h_min = c (1 - eps).
- The attitude angle is phi = psi - theta_L, the angle from the load line to the line of centres in the direction
  of rotation.

## 3 Film pressure
The gauge pressure p(theta, z) in the film satisfies

    (1/R^2) d/dtheta( h^3 / (k_theta mu) dp/dtheta ) + d/dz( h^3 / (k_z mu) dp/dz ) = (omega / 2) dh/dtheta

with mu the oil's dynamic viscosity in the film and k_theta, k_z from section 5.

- p = 0 at both ends of the bearing, z = +L/2 and z = -L/2.
- p = 0 along every groove. A groove is taken as a line running the full length of the bearing; the supply
  pressure is small beside the film pressures and is taken as zero.
- The film cannot carry a pressure below zero. Where the equation would give one, the film is ruptured and p = 0.
  At the edge of a ruptured region the pressure and its gradient are both zero (the Reynolds condition). The film
  is whole again wherever the equation gives a positive pressure.

Put exactly: p >= 0 everywhere; the equation holds wherever p > 0; and wherever p = 0 inside the bearing, the left
side of the equation is not greater than the right side.

## 4 Equilibrium
The film carries the load. Integrated over the whole bearing surface (dA = R dtheta dz),

    integral of p cos(theta) dA = W cos(theta_L)        integral of p sin(theta) dA = W sin(theta_L)

These two conditions fix eps and psi.

## 5 Laminar and turbulent films
The mean Reynolds number of the film is Re = rho omega R c / mu, with rho the oil's density in the film.

- Laminar, Re not above 41.3 sqrt(R / c):   k_theta = k_z = 12,  C_f = 1.
- Turbulent, Re above 41.3 sqrt(R / c):

      k_theta = 12 + 0.0136 Re_h^0.90      k_z = 12 + 0.0043 Re_h^0.96      C_f = 1 + 0.0012 Re_h^0.94

  with the local Reynolds number Re_h = rho omega R h / mu, which varies around the bearing with h.

Where both states would satisfy this section at an operating point, the laminar one is taken.

## 6 Friction and power loss
The shear stress on the journal surface is

    tau = C_f mu omega R / h + (h / (2 R)) dp/dtheta

over the whole surface. In a ruptured region the clearance is taken as full of oil, so the first term stands
there and the second is zero. The power loss is P = omega R x (integral of tau dA).

## 7 Oil and film temperature
- Kinematic viscosity nu in mm2/s at temperature T in C:  log10( log10( nu + 0.7 ) ) = A - B log10( T + 273.15 ),
  with A and B fixed by the oil's viscosities at 40 C and 100 C.
- The oil's viscosities at 40 C and 100 C and its density at 15 C are those of the charge that was in the
  bearing's supply at the operating point, from the laboratory's analysis of that charge: its latest analysis
  where the charge has been analysed more than once, and the mean where more than one sample of the charge was
  analysed on that date. A grade's nominal figures are not used: charges as delivered differ from them by up to
  15 per cent.
- Density rho = rho_15 - 0.65 (T - 15) kg/m3. Specific heat c_p = 2000 J/(kg K). mu = rho nu.
- All of the power loss leaves with the oil. With Q the oil flow to the bearing and T_in its inlet temperature,
  the outlet temperature is T_out = T_in + P / (rho(T_in) c_p Q), and the effective film temperature is
  T_eff = (T_in + T_out) / 2.
- mu and rho in sections 3 to 6 are the oil's at T_eff. So T_eff, the film's state under section 5, the journal's
  position and the power loss have to be found together.

## 8 Convergence
A result is to LS-3 when a finer grid or tighter iteration would change the minimum film thickness, the power
loss and the peak pressure by less than 0.2 per cent each, the attitude angle by less than 0.1 degree and the
effective temperature by less than 0.05 K.

## 9 Results
| quantity | symbol | unit |
|---|---|---|
| minimum film thickness | h_min | um |
| attitude angle | phi | degrees |
| power loss | P | kW |
| effective film temperature | T_eff | C |
| peak film pressure, the largest p in the film | p_max | MPa |
