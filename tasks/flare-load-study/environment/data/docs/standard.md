# RP-7  Flare system relieving load

Issue 6, January 2026. Supersedes issue 5. Applies to the flare system of any process unit and to the load study
that establishes what each unit-wide contingency puts into it.

## 1 Scope and basis of study

A study under this standard establishes, for each contingency the unit admits, which relief devices discharge at
the same time, the total mass flow that arrives at the flare header, and the pressure that flow raises at the
header's inlet.

The study is made on the plant as it now stands, not as it was designed. The set pressure of a device is the one
it now carries. The flows, pressures, temperatures and duties are those the unit now runs at.

## 2 Contingencies to be studied

- `power_failure`: the loss of the normal electrical supply across the unit.
- `cooling_water_failure`: the loss of the cooling water supply.
- `instrument_air_failure`: the loss of instrument air across the unit.
- `fire_zone_a`, `fire_zone_b`, `fire_zone_c`: a pool fire in one fire zone. A fire is credible in one zone at a
  time and reaches only the items that stand in that zone.

## 3 Which devices discharge

A relief device discharges under a contingency when that contingency puts upon its item a cause the item's
service admits, and when nothing in section 7 or section 8 prevents it. The causes are those of section 4 and
the register lists which of them each item admits.

The chain from a contingency to a cause is to be followed through the unit's own records, not assumed:

- A loss of the normal electrical supply stops every driven machine the drive schedule puts on that supply, and
  nothing on the essential supply. Where the instrument air compressor is on the normal supply, a loss of power
  carries a loss of instrument air with it.
- A loss of cooling water stops the machines and exchangers the drive schedule shows to be cooled by water.
- A loss of instrument air puts every control valve in the failure position its data sheet gives. A valve that
  fails open admits its source to the item it feeds; a valve that fails closed isolates what it passes.
- The overhead cooling of a column is lost when the condenser serving it stops.
- A pump whose discharge is isolated delivers against a closed valve.

## 4 Causes and their relieving rates

### 4.1 Relieving pressure

    P1 = Pset * (1 + a) + 1.013      bar absolute

with Pset the set pressure in bar gauge and the accumulation a

- a = 0.21 for `fire`;
- a = 0.10 for every other cause.

Fluid properties are taken at the relieving pressure, and at the saturation temperature there where the
relieving fluid is a saturated vapour. Where the relieving fluid does not condense, the relieving temperature is
the item's normal operating temperature, the mean of the operating record, and its molar mass is that of the most
recent analysis of the stream. Property tables are interpolated linearly and held flat beyond their ends.

### 4.2 `fire`

The heat absorbed by a vessel in a pool fire is

    Q = 43.2 * F * Aw^0.82      kW

where the item stands in an area with drainage or impounding and prompt firefighting is available, and

    Q = 70.9 * F * Aw^0.82      kW

where it does not. Aw is the wetted area in m2.

The environment factor F is 1.0 for a bare or ordinarily lagged item. Where the item carries insulation certified
to remain in place in a fire,

    F = (k / t) * (904 - Tf) / 21000

with k the thermal conductivity of the insulation in W/m K, t its thickness in m, and Tf the relieving
temperature in C. Insulation without such a certificate earns no credit.

The wetted area is the outside surface of the item in contact with liquid at its highest normal operating level,
counted only up to 7.6 m above grade. Surface above that height is not included.

- Each 2:1 ellipsoidal head has an area of 1.084 * D^2, D the diameter in m.
- For a horizontal vessel with a liquid level h above the bottom of the shell, the wetted fraction of the shell
  and of each head is acos((R - h) / R) / pi, with R the shell radius.
- For a fractionating column, the wetted area is the shell in contact with the bottoms liquid, plus the bottom
  head, plus at each tray at or below 7.6 m above grade a band of shell equal in height to the tray liquid depth
  given in the column's data.

The relieving rate is

    W = 3600 * Q / L      kg/h

where L is the latent heat, at the relieving pressure, of the liquid the item holds, which the vessel data book
names. What relieves in a fire is the vapour boiled off that liquid, whatever the item passes in normal service,
so its latent heat, molar mass, ratio of specific heats and compressibility are all those of that liquid's vapour
at the relieving pressure, and the relieving temperature is the saturation temperature there.

### 4.3 `control_valve_failure`

The valve passes into the protected item, at the item's relieving pressure, the flow its full travel admits. The
upstream pressure is the set pressure of the relief device that protects the source of the stream.

    W = 3.16 * Kv * Fp * Y * sqrt(x * P1u * rho1)      kg/h

with

- Kv = Cv / 1.156, the valve coefficient at the travel in question;
- P1u the upstream pressure, kPa absolute, and rho1 the upstream density, kg/m3;
- x = min((P1u - P2) / P1u, Fk * xT), with P2 the downstream pressure, xT the valve's pressure drop ratio factor
  and Fk = k / 1.40;
- Y = 1 - x / (3 * Fk * xT).

The trim follows an equal percentage characteristic,

    Cv(h) = Cv_rated * R^(h - 1)

with h the fractional travel and R the rangeability on the valve's data sheet. The coefficient at full travel
shall be verified against the valve's own operating record; where the record and the data sheet disagree, the
record governs.

### 4.4 `cooling_failure`

With the overhead condenser of a column stopped and heat input continuing, the relieving rate is the vapour the
reboiler generates at the relieving temperature:

    Q = UA * (Ts - Tb)      kW
    W = 3600 * Q / L        kg/h

where the liquid the column holds is the one the vessel data book names for it, and

- Ts is the saturation temperature of the steam at the pressure of the header that supplies the reboiler, which
  the exchanger data gives, the steam valve being taken as fully open;
- Tb is the saturation temperature of that liquid at the relieving pressure;
- L is the latent heat of that same liquid at the relieving pressure, the mass the reboiler makes being its duty
  over the latent heat of what it is boiling;
- UA shall be established from the unit's operating record at the throughput the unit runs, as the mean over the
  record of the value each day's duty and temperature difference give.

What then leaves the top of the column and enters the header is the relieving fluid the register names, so it is
that fluid's molar mass, ratio of specific heats, compressibility and temperature at the relieving pressure that
the mixture of section 5 is made from.

### 4.5 `blocked_outlet`

A pump delivering against a closed discharge relieves the flow it passes at the relieving pressure, carried on
its own mass. The flow the pump delivers there is read from its performance as last tested, and section 7
settles whether it can reach the relieving pressure at all.

## 5 The load on the header

The load a contingency puts on the header is the sum of the rates of the devices that discharge under it. What
arrives is their mixture, whose properties are

- molar mass: the total mass divided by the total moles, the moles of each contribution being its mass over its
  own molar mass;
- ratio of specific heats, compressibility and temperature: the mass-weighted means of the contributions.

A device discharging liquid contributes its mass like any other, and enters the mixture with the molar mass of
the liquid it passes, a ratio of specific heats of 1.05, a compressibility of 1, and the temperature at which
that liquid is pumped.

## 6 The pressure at the header's inlet

The header runs from a blinded end at the unit limit to the stack base. Relief devices tie into it at the
distances the as-built isometrics give, and those tie-ins divide the header into lengths, whether or not the
device at a tie-in discharges under the contingency in hand. Flow runs towards the stack, so each length carries
the devices that tie in beyond it, and carries their mixture, taken as section 5 gives it. A length that carries
nothing adds nothing, the purge flow being neglected.

The loss along a length of header, and through the tip, follows

    dP = (f * L / D + sum K) * rho * v^2 / 2      Pa

with f = 0.018, L the length and D the bore in m, v the velocity of what that length carries, and the fitting
losses

| fitting | K |
|---|---|
| 90 degree elbow | 0.30 |
| tee, flow through run | 0.20 |

each fitting counted in the length its position falls in.

The pressure is worked out from the tip outwards, so that nothing has to be iterated:

1. the tip, carrying the whole load, with the mixture's density at atmospheric pressure and the tip's own loss
   coefficient and bore, gives the pressure at the stack base;
2. then each length of header in turn, from the stack base outwards, with the density of what that length
   carries taken at the pressure already reached at its downstream end.

The pressure at the header's inlet is the pressure reached at the blinded end, reported in bar gauge. A flare
header carries no isolation valve.

Where the loss coefficient of the tip or of a fitting is not on record for the item as installed, it is to be
established by test on that item, and not taken from the item it replaced.

## 7 Causes that need not be considered

A cause need not be considered where it cannot raise the pressure of the protected item to its relieving
pressure. For a pump delivering against a closed discharge this is settled by the pump's shutoff pressure in its
present condition, which is the condition it is in after the last work the maintenance log records on it.

## 8 Credit for instrumented protection

A cause may be set aside where a safety instrumented function prevents it and all of the following hold:

- the function is rated SIL 2 or better in the safety instrumented system register;
- it is proof tested at intervals of not more than 18 months;
- its initiating element is not the measurement used by the control function whose failure causes the cause;
- the system that carries the function still has the supply the drive schedule shows it on.

Where any of these does not hold, the cause stands.

## 9 The record of the study

For each contingency: the relief devices that discharge, the total load in kg/h, and the pressure at the header's
inlet in bar gauge.
