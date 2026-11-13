# RL-2 Rod-pumped wells: card analysis and setting tables

Issue 4. This standard fixes how a rod-pumped well is calculated from its dynamometer cards and how its
behaviour is calculated at other settings of its pumping unit. It states the physical model and what each result
means. How the equations are solved is left to the analyst.

## 1 Scope

Vertical wells with a sucker-rod string of one to three tapers of steel or fibreglass rods, a plunger pump at the
foot of the tubing and a beam pumping unit at the surface. Pump depths of 600 to 3,000 m, pumping speeds of 3 to
10 strokes a minute, polished rod strokes of 1.5 to 5 m.

SI units. Positions are measured upwards. Depth x is measured downwards from the polished rod. Loads in the rods
are tensions. g = 9.80665 m/s2.

## 2 The rod string

A rod element at depth x is displaced upwards by y(x, t) from where it rests when the string hangs still in the
well's liquid with no load on the pump and the polished rod at the bottom of its stroke. In each taper

    rho A d2y/dt2 = E A d2y/dx2 - c rho A dy/dt

and T(x, t) = -E A dy/dx is the tension in the rods above their tension at rest. At a change of taper y and T are
continuous. c is the viscous damping coefficient of the field, in 1/s, the same over the whole string.

| material   | E, GPa | rho, kg/m3 |
|------------|--------|------------|
| steel      | 200    | 8,000      |
| fibreglass | 50     | 2,400      |

The densities include the couplings and end fittings. A is the area of the rod body, pi d^2 / 4.

At rest the polished rod carries the weight of the rods in the liquid,

    W = sum over the tapers of A L g (rho - rho_l),

with rho_l the density of the field's liquid. In motion the polished rod load is PRL(t) = W + T(0, t).

## 3 The polished rod

The pumping unit moves the polished rod through

    y(0, t) = S [ (1 - cos q) / 2 + (k / 8) (1 - cos 2q) ],   q = 2 pi N t / 60,

where S is the polished rod stroke of the setting, N the pumping speed in strokes a minute and k the unit factor
of the well's pumping unit. The crank turns at constant speed.

## 4 The pump

The plunger, of area A_p = pi d_p^2 / 4, is the foot of the rod string, at the pump depth L. It works in a
barrel that is the foot of the tubing. The travelling valve is in the plunger, the standing valve at the foot of
the barrel. The plunger's position in the barrel is s = y_p - y_b, the plunger's position less the barrel's.

Above the plunger stands the tubing's liquid: p_d = p_t + rho_l g L, with p_t the tubing head pressure. Below
the standing valve is the pump intake pressure p_i, which is not on record. Under the plunger is the barrel
pressure p_b. The pump load, the tension at the foot of the rods, is

    F_p = T(L, t) = A_p (p_d - p_b),

so it is the fluid load F_o = A_p (p_d - p_i) when the barrel is at intake pressure and nothing when the
travelling valve is open.

The valves and the barrel:

1. While the plunger rises in the barrel the standing valve is open, the barrel is at p_i and takes in what the
   well gives: liquid first, up to the liquid supply of one stroke, then free gas. The liquid supply of a stroke
   is a column of height h_s = Q_s / (A_p N) in the barrel, with Q_s the liquid the well gives in a minute.
2. When the plunger stops rising the standing valve shuts. If the plunger has then risen S_p in the barrel from
   the lowest position of its stroke, the barrel holds liquid to a height h_l = min(S_p, h_s) and above it gas
   at p_i in a column S_p - h_l.
3. As the plunger comes down the gas is compressed at constant temperature: p_b times the length of the gas
   column is constant. The travelling valve opens when p_b reaches p_d, and from there down the pump load is
   nothing. A barrel that holds no gas is full of liquid, liquid does not compress, and its travelling valve
   opens as soon as the plunger starts down in the barrel.
4. If the plunger rises again before the travelling valve has opened, the gas expands by the same law, and the
   standing valve opens again when p_b is back at p_i.
5. When the plunger starts up from the bottom of its stroke the travelling valve shuts. The space left under the
   plunger is full of liquid, so the barrel pressure falls to p_i and the standing valve opens as soon as the
   plunger rises in the barrel.
6. While both valves are shut on liquid the plunger does not move in the barrel, and the pump load is whatever
   the rods and the tubing make it, between nothing and F_o.

A plunger that turns back in the barrel while the travelling valve is open and gas is still under it is outside
this standard. No well does so at any setting it is calculated at.

## 5 The tubing

The tubing hangs from the wellhead and carries the barrel at its foot. Whatever part of the fluid load is not on
the plunger is on the standing valve, and so on the tubing: F_o - F_p. Tubing that is free to stretch lengthens
under it, and the barrel goes down with it:

    y_b = -(F_o - F_p) L_f / (E_t A_t).

L_f is the length of tubing that is free to stretch, from the pump up to where the tubing is held: the anchor
where an anchor holds the tubing to the casing, the wellhead where none does. E_t = 200 GPa. The tubing's own
mass and motion are left out.

| tubing OD, mm | ID, mm |
|---------------|--------|
| 60.3          | 50.7   |
| 73.0          | 62.0   |
| 88.9          | 76.0   |

A_t is the area of the tubing wall.

## 6 What the cards give

A dynamometer card is the polished rod position and load through one stroke cycle of the well in steady
running at its found setting. Two things the calculation needs are on no record and are found from the cards:

- the fluid load F_o, and with it the pump intake pressure;
- the liquid supply Q_s.

A well whose cards show a gas column of less than 3 per cent of the plunger's stroke at the found setting is
found full. A well found full is taken to fill its barrel with liquid at every setting. For any other well the
liquid supply found is the same at every setting, and so is the intake pressure of every well.

The load cells repeat to about 0.15 kN and the position transducers to about 1 mm.

## 7 The setting table

For each setting, a polished rod stroke and a speed, the well is calculated in the steady cycle it settles to,
with the fluid load and liquid supply found from its cards. The results:

- plunger stroke, m: S_p of section 4, the rise of the plunger in the barrel from the lowest position of its
  stroke to where the standing valve shuts;
- liquid, m3/d: A_p h_l N times the 1,440 minutes of a day;
- peak polished rod load and minimum polished rod load, kN: the greatest and least PRL of the cycle.
