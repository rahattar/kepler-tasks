# GF-4: Face load distribution of spur gear pairs

Works standard, revision 3. It gives the load along the face width of a spur gear pair in service, from the
gears as inspected and the pair as mounted, at every point of the pair's duty record.

## 1. Scope and symbols

A pair is a pinion and a wheel of the same face width b (mm), meshing over the whole face. Position along the
face is x, in mm from the pinion's datum end (0 to b); the wheel's charts use the same x. One tooth pair
carries the whole load. The wheel and its shaft are taken as rigid.

- w(x): load intensity on the flanks in mesh, N per mm of face, never negative.
- F: the normal force on the pair, N. At a duty point of pinion torque T (N m), F = 2000 T / d_b, with d_b the
  pinion's base diameter (mm).
- c': mesh stiffness, N per mm of face per um of approach.
- A gear's flanks are named left (L) and right (R) as seen from its datum end with the tooth pointing up. Its
  working flank is the flank that carries the load in the pair's service rotation.

## 2. The flanks before load

A lead chart gives a flank's deviation from the true flank line along the face, in um, positive where the
flank has more material. A gear's lead curve f(x) is the mean, station by station, of the charts of its working
flank on the teeth charted, taken linearly between stations and constant beyond the first and last station.

Mounted, the working flanks stand apart before load by

    s(x) = -( f_pinion(x) + f_wheel(x) ) + m x / b          um, up to a constant

with m the mesh misalignment over the face, um: the amount by which the mounting opens the mesh at x = b
relative to x = 0. It is

    m = m_0 + k_T ( t_oil - t_ref )

with m_0 the misalignment as mounted at the reference temperature t_ref, k_T the housing's thermal coefficient
(um per K) and t_oil the oil temperature at the duty point.

## 3. Deflection of the pinion body

Under the load the pinion body twists and bends, which moves its flank away from the wheel by

    u(x) = integral over the face of [ K_t(x, y) + K_b(x, y) ] w(y) dy          (mm; times 1000 for um)

- Torsion. The torque enters at the datum end. K_t(x, y) = r_b^2 min(x, y) / (G J), with r_b = d_b / 2,
  J = pi d^4 / 32 and d the body diameter.
- Bending, straddle mounting. The pinion is a beam of diameter d simply supported at two bearings a span L
  apart, the datum end at a distance a from the first bearing. With p = min(x, y) + a, q = max(x, y) + a and
  g = L - q:  K_b = g p ( L^2 - g^2 - p^2 ) / (6 E I L),  I = pi d^4 / 64.
- Bending, overhung mounting. The pinion is a beam built in at the bearing, the datum end a distance a beyond
  it. With p and q as above:  K_b = p^2 ( 3 q - p ) / (6 E I).

E = 206 000 MPa, G = 79 000 MPa.

## 4. The load along the face

At a force F the flanks approach by an amount D (um) and at every x

    w(x) / c' + 1000 u(x) + s(x) - D >= 0,        w(x) >= 0,

with one of the two equal to zero: where the flanks touch the first is zero, where they stand apart the load
is zero. The load balances the force: integral of w over the face = F. This fixes w(x) and D.

## 5. The mounting misalignment

m_0 is measured when the pair is assembled: the bores of the pinion's and the wheel's bearings are surveyed in
the housing at the reference temperature and their misalignment is taken onto the line of action of the
working flanks. The package gives it.

## 6. Results at each duty point

- **k_face**: the largest load intensity on the face over the mean, max w / (F / b).
- **sigma_H_MPa**: the contact stress there, Z sqrt( max w (u + 1) / (d_1 u) ), with Z the pair's stress
  constant (the package gives it, for w in N/mm and d_1 in mm), d_1 the pinion's pitch diameter (mm) and u the ratio.

The results are those of the continuous problem; a calculation on stations along the face is fine enough when
doubling the stations moves no result by more than 0.2 per cent.
